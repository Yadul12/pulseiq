"""Overview Dashboard, Global Search, Alerts, Methodology Telemetry, and Audit Logs."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import (
    Alert,
    AnalystAnnotation,
    AuditLog,
    Cluster,
    DataSource,
    Event,
    IngestionJob,
    MonitoringTopic,
    ProcessedRecord,
    RawRecord,
    Report,
    SentimentClassification,
    TopicClassification,
    User,
)
from app.nlp.pipeline import PIPELINE_VERSION, SENTIMENT_MODEL_NAME, TOPIC_MODEL_NAME, get_cluster_engine

router = APIRouter(tags=["Overview & Intelligence Telemetry"])


def _eff_sentiment_expr():
    return case(
        (
            SentimentClassification.is_overridden.is_(True),
            func.coalesce(SentimentClassification.overridden_sentiment, SentimentClassification.predicted_sentiment),
        ),
        else_=SentimentClassification.predicted_sentiment,
    )


def _eff_topic_expr():
    return case(
        (
            TopicClassification.is_overridden.is_(True),
            func.coalesce(TopicClassification.overridden_topic, TopicClassification.predicted_topic),
        ),
        else_=TopicClassification.predicted_topic,
    )


@router.get("/overview")
def get_overview_dashboard(
    days: int = Query(default=30, ge=1, le=365),
    source_id: Optional[int] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)

    base_filters = [RawRecord.published_at >= cutoff]
    if source_id is not None:
        base_filters.append(RawRecord.source_id == source_id)

    total_processed = (
        db.scalar(
            select(func.count(ProcessedRecord.id))
            .join(RawRecord, RawRecord.id == ProcessedRecord.raw_record_id)
            .where(*base_filters)
        )
        or 0
    )
    non_dup_processed = (
        db.scalar(
            select(func.count(ProcessedRecord.id))
            .join(RawRecord, RawRecord.id == ProcessedRecord.raw_record_id)
            .where(*base_filters, ProcessedRecord.is_duplicate.is_(False))
        )
        or 0
    )
    total_all_time = db.scalar(select(func.count(ProcessedRecord.id))) or 0

    unique_sources = (
        db.scalar(
            select(func.count(func.distinct(RawRecord.source_id))).where(*base_filters)
        )
        or 0
    )
    processing_backlog = (
        db.scalar(
            select(func.count(ProcessedRecord.id)).where(
                ProcessedRecord.processing_status.in_(["pending", "needs_review"])
            )
        )
        or 0
    )
    verified_insights = (
        db.scalar(
            select(func.count(AnalystAnnotation.id)).where(AnalystAnnotation.is_verified.is_(True))
        )
        or 0
    )
    synthetic_count = (
        db.scalar(
            select(func.count(RawRecord.id)).where(*base_filters, RawRecord.is_synthetic.is_(True))
        )
        or 0
    )

    # Aggregate sentiment distribution
    eff_sent = _eff_sentiment_expr()
    sent_rows = db.execute(
        select(eff_sent.label("sentiment"), func.count(ProcessedRecord.id), func.avg(SentimentClassification.sentiment_score))
        .join(ProcessedRecord, ProcessedRecord.id == SentimentClassification.processed_record_id)
        .join(RawRecord, RawRecord.id == ProcessedRecord.raw_record_id)
        .where(*base_filters, ProcessedRecord.is_duplicate.is_(False))
        .group_by(eff_sent)
    ).all()
    sentiment_dist = {"positive": 0, "neutral": 0, "mixed": 0, "negative": 0}
    weighted_sent = 0.0
    for s_label, cnt, avg_s in sent_rows:
        if s_label in sentiment_dist:
            sentiment_dist[s_label] = int(cnt)
        weighted_sent += float(avg_s or 0.0) * int(cnt)
    avg_sentiment_score = round(weighted_sent / max(non_dup_processed, 1), 4)

    # Topic activity over time (daily buckets by effective topic)
    eff_topic = _eff_topic_expr()
    is_sqlite = db.bind is not None and db.bind.dialect.name == "sqlite"
    day_expr = (
        func.strftime("%Y-%m-%d", RawRecord.published_at)
        if is_sqlite
        else func.date_trunc("day", RawRecord.published_at)
    )
    trend_rows = db.execute(
        select(day_expr.label("day"), eff_topic.label("topic"), func.count(ProcessedRecord.id).label("cnt"))
        .join(ProcessedRecord, ProcessedRecord.id == TopicClassification.processed_record_id)
        .join(RawRecord, RawRecord.id == ProcessedRecord.raw_record_id)
        .where(*base_filters, ProcessedRecord.is_duplicate.is_(False))
        .group_by(day_expr, eff_topic)
        .order_by(day_expr.asc())
    ).all()

    daily_map: dict[str, dict[str, int | str]] = {}
    topic_totals: Counter[str] = Counter()
    for day_dt, topic_name, cnt in trend_rows:
        d_str = str(day_dt)[:10] if isinstance(day_dt, str) else day_dt.strftime("%Y-%m-%d")
        if d_str not in daily_map:
            daily_map[d_str] = {"date": d_str, "total": 0}
        daily_map[d_str][topic_name] = int(cnt)
        daily_map[d_str]["total"] = int(daily_map[d_str]["total"]) + int(cnt)
        topic_totals[topic_name] += int(cnt)

    top_topic_names = [t for t, _ in topic_totals.most_common(6)]
    activity_series = []
    for d_str in sorted(daily_map.keys()):
        row = {"date": d_str, "total": daily_map[d_str]["total"]}
        for t in top_topic_names:
            row[t] = int(daily_map[d_str].get(t, 0))
        activity_series.append(row)

    # Emerging clusters & watchlist (exclude clusters from archived topics)
    active_topic_ids = select(MonitoringTopic.id).where(MonitoringTopic.status != "archived")
    clusters = list(
        db.scalars(
            select(Cluster)
            .where(or_(Cluster.monitoring_topic_id.is_(None), Cluster.monitoring_topic_id.in_(active_topic_ids)))
            .order_by(Cluster.is_emerging.desc(), Cluster.trend_velocity.desc())
            .limit(10)
        ).all()
    )
    emerging_count = sum(1 for c in clusters if c.is_emerging)

    # Ingestion health across sources
    sources = list(db.scalars(select(DataSource).order_by(DataSource.total_records_ingested.desc())).all())
    healthy_sources = sum(1 for s in sources if s.health_status == "healthy")
    degraded_sources = sum(1 for s in sources if s.health_status == "degraded")
    error_sources = sum(1 for s in sources if s.health_status == "error")

    # Language breakdown
    lang_rows = db.execute(
        select(ProcessedRecord.detected_language, func.count(ProcessedRecord.id))
        .join(RawRecord, RawRecord.id == ProcessedRecord.raw_record_id)
        .where(*base_filters, ProcessedRecord.is_duplicate.is_(False))
        .group_by(ProcessedRecord.detected_language)
        .order_by(func.count(ProcessedRecord.id).desc())
    ).all()

    return {
        "window_days": days,
        "kpis": {
            "total_processed_posts": int(total_processed),
            "total_all_time_records": int(total_all_time),
            "unique_non_duplicate_posts": int(non_dup_processed),
            "unique_sources": int(unique_sources),
            "total_configured_sources": len(sources),
            "emerging_topics_count": emerging_count,
            "processing_backlog": int(processing_backlog),
            "verified_insights_count": int(verified_insights),
            "avg_sentiment_score": avg_sentiment_score,
            "synthetic_share_pct": round((synthetic_count / max(total_processed, 1)) * 100.0, 1),
            "ingestion_health": {
                "status": "error" if error_sources else ("degraded" if degraded_sources else "healthy"),
                "healthy": healthy_sources,
                "degraded": degraded_sources,
                "error": error_sources,
            },
        },
        "sentiment_distribution": sentiment_dist,
        "topic_names": top_topic_names,
        "topic_activity_over_time": activity_series,
        "topic_totals": [{"topic": t, "count": int(c)} for t, c in topic_totals.most_common(8)],
        "emerging_watchlist": [
            {
                "id": c.id,
                "monitoring_topic_id": c.monitoring_topic_id,
                "topic_name": c.topic_name,
                "cluster_label": c.cluster_label,
                "record_count": c.record_count,
                "recent_24h_count": c.recent_24h_count,
                "baseline_daily_avg": c.baseline_daily_avg,
                "trend_velocity": c.trend_velocity,
                "growth_pct": c.growth_pct,
                "is_emerging": c.is_emerging,
                "avg_sentiment_score": c.avg_sentiment_score,
                "sentiment_breakdown": c.sentiment_breakdown,
                "top_keywords": c.top_keywords[:5],
            }
            for c in clusters[:8]
        ],
        "ingestion_sources": [
            {
                "id": s.id,
                "name": s.name,
                "provider_type": s.provider_type,
                "is_synthetic": s.is_synthetic,
                "is_enabled": s.is_enabled,
                "health_status": s.health_status,
                "total_records_ingested": s.total_records_ingested,
                "error_count_24h": s.error_count_24h,
                "last_ingested_at": s.last_ingested_at.isoformat() if s.last_ingested_at else None,
            }
            for s in sources
        ],
        "language_breakdown": [{"language": lang, "count": int(cnt)} for lang, cnt in lang_rows],
        "analytical_caveat": (
            "Metrics reflect aggregate volume and classifier-estimated tone across configured public and clearly labelled "
            "synthetic data sources. Aggregate sentiment is not a scientific measure of population-level public opinion."
        ),
    }


@router.get("/search")
def global_search(
    q: str = Query(min_length=2, max_length=120),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pattern = f"%{q.strip()}%"
    topics = list(
        db.scalars(
            select(MonitoringTopic)
            .where(or_(MonitoringTopic.name.ilike(pattern), MonitoringTopic.description.ilike(pattern)))
            .limit(5)
        ).all()
    )
    events = list(
        db.scalars(
            select(Event)
            .where(or_(Event.title.ilike(pattern), Event.description.ilike(pattern), Event.location.ilike(pattern)))
            .limit(5)
        ).all()
    )
    reports = list(
        db.scalars(
            select(Report)
            .where(or_(Report.title.ilike(pattern), Report.executive_summary.ilike(pattern)))
            .limit(5)
        ).all()
    )
    rec_rows = db.execute(
        select(
            ProcessedRecord.id,
            ProcessedRecord.normalized_text,
            RawRecord.original_title,
            RawRecord.published_at,
            TopicClassification.predicted_topic,
            SentimentClassification.predicted_sentiment,
        )
        .join(RawRecord, RawRecord.id == ProcessedRecord.raw_record_id)
        .join(TopicClassification, TopicClassification.processed_record_id == ProcessedRecord.id)
        .join(SentimentClassification, SentimentClassification.processed_record_id == ProcessedRecord.id)
        .where(or_(ProcessedRecord.normalized_text.ilike(pattern), RawRecord.original_title.ilike(pattern)))
        .order_by(RawRecord.published_at.desc())
        .limit(8)
    ).all()

    return {
        "query": q,
        "topics": [{"id": t.id, "name": t.name, "status": t.status, "category": t.category} for t in topics],
        "events": [{"id": e.id, "title": e.title, "event_type": e.event_type, "location": e.location} for e in events],
        "reports": [{"id": r.id, "title": r.title, "status": r.status} for r in reports],
        "records": [
            {
                "id": r.id,
                "title": r.original_title,
                "excerpt": r.normalized_text[:150],
                "topic": r.predicted_topic,
                "sentiment": r.predicted_sentiment,
                "published_at": r.published_at.isoformat(),
            }
            for r in rec_rows
        ],
    }


@router.get("/alerts")
def list_alerts(
    unread_only: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(Alert).order_by(Alert.created_at.desc()).limit(30)
    if unread_only:
        stmt = stmt.where(Alert.is_read.is_(False))
    alerts = list(db.scalars(stmt).all())
    unread_count = db.scalar(select(func.count(Alert.id)).where(Alert.is_read.is_(False))) or 0
    return {
        "unread_count": int(unread_count),
        "items": [
            {
                "id": a.id,
                "severity": a.severity,
                "category": a.category,
                "title": a.title,
                "message": a.message,
                "resource_type": a.resource_type,
                "resource_id": a.resource_id,
                "is_read": a.is_read,
                "created_at": a.created_at.isoformat(),
            }
            for a in alerts
        ],
    }


@router.patch("/alerts/{alert_id}/read")
def mark_alert_read(
    alert_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    alert = db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.is_read = True
    db.commit()
    return {"id": alert.id, "is_read": True}


@router.post("/alerts/read-all")
def mark_all_alerts_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    alerts = list(db.scalars(select(Alert).where(Alert.is_read.is_(False))).all())
    for a in alerts:
        a.is_read = True
    db.commit()
    return {"marked_read": len(alerts)}


@router.get("/methodology")
def get_methodology_telemetry(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    total_raw = db.scalar(select(func.count(RawRecord.id))) or 0
    synthetic_raw = db.scalar(select(func.count(RawRecord.id)).where(RawRecord.is_synthetic.is_(True))) or 0
    missing_raw = db.scalar(select(func.count(RawRecord.id)).where(RawRecord.has_missing_fields.is_(True))) or 0
    total_proc = db.scalar(select(func.count(ProcessedRecord.id))) or 0
    dup_proc = db.scalar(select(func.count(ProcessedRecord.id)).where(ProcessedRecord.is_duplicate.is_(True))) or 0
    needs_review = (
        db.scalar(select(func.count(ProcessedRecord.id)).where(ProcessedRecord.processing_status == "needs_review")) or 0
    )
    topic_overrides = (
        db.scalar(select(func.count(TopicClassification.id)).where(TopicClassification.is_overridden.is_(True))) or 0
    )
    sent_overrides = (
        db.scalar(select(func.count(SentimentClassification.id)).where(SentimentClassification.is_overridden.is_(True)))
        or 0
    )
    avg_topic_conf = db.scalar(select(func.avg(TopicClassification.confidence))) or 0.0
    avg_sent_conf = db.scalar(select(func.avg(SentimentClassification.confidence))) or 0.0

    lang_rows = db.execute(
        select(ProcessedRecord.detected_language, func.count(ProcessedRecord.id))
        .group_by(ProcessedRecord.detected_language)
        .order_by(func.count(ProcessedRecord.id).desc())
    ).all()

    prov_rows = db.execute(
        select(RawRecord.provenance_label, func.count(RawRecord.id))
        .group_by(RawRecord.provenance_label)
        .order_by(func.count(RawRecord.id).desc())
    ).all()

    cluster_engine = get_cluster_engine()

    return {
        "pipeline_version": PIPELINE_VERSION,
        "models": {
            "topic_classifier": {"name": TOPIC_MODEL_NAME, "version": "1.0.0", "avg_confidence": round(float(avg_topic_conf), 3)},
            "sentiment_classifier": {"name": SENTIMENT_MODEL_NAME, "version": "1.0.0", "avg_confidence": round(float(avg_sent_conf), 3)},
            "embedding_clustering": {"backend": cluster_engine.embedding_backend, "algorithm": "MiniBatchKMeans + c-TF-IDF"},
            "trend_detection": {"algorithm": "Modified Z-score (72h rate vs 27-day rolling baseline)", "emerging_threshold_z": 1.75},
        },
        "corpus_telemetry": {
            "total_raw_records": int(total_raw),
            "total_processed_records": int(total_proc),
            "synthetic_records": int(synthetic_raw),
            "synthetic_pct": round((synthetic_raw / max(total_raw, 1)) * 100.0, 2),
            "duplicate_records": int(dup_proc),
            "duplicate_rate_pct": round((dup_proc / max(total_proc, 1)) * 100.0, 2),
            "missing_field_records": int(missing_raw),
            "missing_field_rate_pct": round((missing_raw / max(total_raw, 1)) * 100.0, 2),
            "needs_review_queue": int(needs_review),
            "needs_review_pct": round((needs_review / max(total_proc, 1)) * 100.0, 2),
            "topic_overrides": int(topic_overrides),
            "sentiment_overrides": int(sent_overrides),
            "language_distribution": [{"language": l, "count": int(c)} for l, c in lang_rows],
            "provenance_breakdown": [{"label": p, "count": int(c)} for p, c in prov_rows],
        },
        "classification_definitions": {
            "positive": "Explicit approval, constructive satisfaction, or verified service improvement reported in public commentary.",
            "neutral": "Factual advisories, schedules, procedural announcements, or non-evaluative civic data notices.",
            "mixed": "Balanced statements expressing both acknowledged progress and unresolved operational or equity concerns.",
            "negative": "Dissatisfaction, service disruption reports, safety hazards, or policy objections.",
        },
        "limitations": [
            "Non-Scientific Opinion Proxy: Ingested public discussions over-represent digitally active and highly motivated contributors; aggregate sentiment must never be cited as representative public polling.",
            "Sarcasm & Pragmatic Ambiguity: Linear TF-IDF models can misclassify ironic phrasing (e.g., 'Great job closing the only bridge...'). Confidence calibration routes ambiguous items (< 0.56) to Analyst Workspace for human review.",
            "Multilingual Performance Gap: Non-English civic commentary (es, fr, de, pt) exhibits slightly lower classifier confidence and benefits from bilingual analyst verification.",
            "Synthetic Dataset Disclosure: Where external API credentials or live municipal feeds are unavailable, PulseIQ runs clearly labelled synthetic adapters and never presents synthetic records as live social media.",
            "Privacy & Ethical Boundary: PulseIQ operates strictly on aggregate public civic discussions. Individual political profiling, voter persuasion, micro-targeting, and unauthorized scraping are architecturally prohibited.",
        ],
    }


@router.get("/audit-logs")
def list_audit_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=5, le=100),
    action: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(AuditLog)
    count_stmt = select(func.count(AuditLog.id))
    if action:
        stmt = stmt.where(AuditLog.action.ilike(f"%{action}%"))
        count_stmt = count_stmt.where(AuditLog.action.ilike(f"%{action}%"))
    total = db.scalar(count_stmt) or 0
    rows = list(
        db.scalars(
            stmt.order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        ).all()
    )
    return {
        "total": int(total),
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": a.id,
                "actor_email": a.actor_email,
                "action": a.action,
                "resource_type": a.resource_type,
                "resource_id": a.resource_id,
                "details": a.details,
                "ip_address": a.ip_address,
                "created_at": a.created_at.isoformat(),
            }
            for a in rows
        ],
    }
