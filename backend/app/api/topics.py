"""Monitoring Topics CRUD, Topic Explorer Clusters/Keyword Relationships/Comparison."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from itertools import combinations
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, record_audit_log, require_role
from app.ingestion.service import execute_ingestion_job
from app.models.models import (
    Cluster,
    DataSource,
    MonitoringTopic,
    ProcessedRecord,
    RawRecord,
    SentimentClassification,
    TopicClassification,
    User,
)
from app.schemas.schemas import MonitoringTopicCreate, MonitoringTopicUpdate, RunIngestionRequest
from app.workers.tasks import recompute_clusters_and_trends, run_source_ingestion

router = APIRouter(tags=["Monitoring Topics & Explorer"])


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "topic"


@router.get("/topics")
def list_monitoring_topics(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(MonitoringTopic).order_by(MonitoringTopic.created_at.desc())
    if status_filter and status_filter != "all":
        stmt = stmt.where(MonitoringTopic.status == status_filter)
    topics = list(db.scalars(stmt).all())

    now = datetime.now(timezone.utc)
    cutoff_24h = now - timedelta(hours=24)

    # Aggregate counts & avg sentiment per monitoring_topic_id cleanly in one query
    stats_rows = db.execute(
        select(
            TopicClassification.monitoring_topic_id,
            func.count(ProcessedRecord.id).label("total_cnt"),
            func.avg(SentimentClassification.sentiment_score).label("avg_sent"),
            func.sum(case((RawRecord.published_at >= cutoff_24h, 1), else_=0)).label("recent_24h"),
        )
        .join(ProcessedRecord, ProcessedRecord.id == TopicClassification.processed_record_id)
        .join(RawRecord, RawRecord.id == ProcessedRecord.raw_record_id)
        .join(SentimentClassification, SentimentClassification.processed_record_id == ProcessedRecord.id)
        .where(ProcessedRecord.is_duplicate.is_(False), TopicClassification.monitoring_topic_id.is_not(None))
        .group_by(TopicClassification.monitoring_topic_id)
    ).all()
    stats_map = {
        int(r.monitoring_topic_id): {
            "record_count": int(r.total_cnt),
            "avg_sentiment": round(float(r.avg_sent or 0.0), 3),
            "recent_24h_count": int(r.recent_24h or 0),
        }
        for r in stats_rows
    }

    emerging_topic_ids = set(
        db.scalars(
            select(Cluster.monitoring_topic_id).where(
                Cluster.is_emerging.is_(True), Cluster.monitoring_topic_id.is_not(None)
            )
        ).all()
    )

    return [
        {
            "id": t.id,
            "name": t.name,
            "slug": t.slug,
            "description": t.description,
            "category": t.category,
            "keywords": t.keywords,
            "excluded_keywords": t.excluded_keywords,
            "data_source_ids": t.data_source_ids,
            "time_range_days": t.time_range_days,
            "language": t.language,
            "status": t.status,
            "created_at": t.created_at.isoformat(),
            "updated_at": t.updated_at.isoformat(),
            "record_count": stats_map.get(t.id, {}).get("record_count", 0),
            "recent_24h_count": stats_map.get(t.id, {}).get("recent_24h_count", 0),
            "avg_sentiment": stats_map.get(t.id, {}).get("avg_sentiment", 0.0),
            "has_emerging_trend": t.id in emerging_topic_ids,
        }
        for t in topics
    ]


@router.post("/topics", status_code=status.HTTP_201_CREATED)
def create_monitoring_topic(
    payload: MonitoringTopicCreate,
    request: Request,
    current_user: User = Depends(require_role("analyst")),
    db: Session = Depends(get_db),
):
    slug = _slugify(payload.name)
    existing = db.scalar(
        select(MonitoringTopic).where((MonitoringTopic.name == payload.name) | (MonitoringTopic.slug == slug))
    )
    if existing:
        raise HTTPException(status_code=409, detail=f"Monitoring topic '{payload.name}' already exists.")

    source_ids = payload.data_source_ids
    if not source_ids:
        source_ids = list(db.scalars(select(DataSource.id).where(DataSource.is_enabled.is_(True))).all())

    topic = MonitoringTopic(
        name=payload.name.strip(),
        slug=slug,
        description=payload.description.strip(),
        category=payload.category,
        keywords=[k.strip() for k in payload.keywords if k.strip()],
        excluded_keywords=[k.strip() for k in payload.excluded_keywords if k.strip()],
        data_source_ids=source_ids,
        time_range_days=payload.time_range_days,
        language=payload.language,
        status=payload.status,
        created_by=current_user.id,
    )
    db.add(topic)
    db.flush()

    record_audit_log(
        db=db,
        action="monitoring_topic.created",
        resource_type="monitoring_topic",
        resource_id=str(topic.id),
        details={"name": topic.name, "keywords": topic.keywords},
        actor=current_user,
        request=request,
    )
    db.commit()
    db.refresh(topic)
    return {
        "id": topic.id,
        "name": topic.name,
        "slug": topic.slug,
        "description": topic.description,
        "category": topic.category,
        "keywords": topic.keywords,
        "excluded_keywords": topic.excluded_keywords,
        "data_source_ids": topic.data_source_ids,
        "time_range_days": topic.time_range_days,
        "language": topic.language,
        "status": topic.status,
        "created_at": topic.created_at.isoformat(),
        "updated_at": topic.updated_at.isoformat(),
    }


@router.patch("/topics/{topic_id}")
def update_monitoring_topic(
    topic_id: int,
    payload: MonitoringTopicUpdate,
    request: Request,
    current_user: User = Depends(require_role("analyst")),
    db: Session = Depends(get_db),
):
    topic = db.get(MonitoringTopic, topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Monitoring topic not found.")

    updates = payload.model_dump(exclude_unset=True)
    for field, val in updates.items():
        if field == "name" and val:
            topic.name = val.strip()
            topic.slug = _slugify(val)
        elif field in ("keywords", "excluded_keywords") and val is not None:
            setattr(topic, field, [k.strip() for k in val if k.strip()])
        else:
            setattr(topic, field, val)

    record_audit_log(
        db=db,
        action="monitoring_topic.updated",
        resource_type="monitoring_topic",
        resource_id=str(topic.id),
        details={"updated_fields": list(updates.keys()), "status": topic.status},
        actor=current_user,
        request=request,
    )
    db.commit()
    db.refresh(topic)
    return {
        "id": topic.id,
        "name": topic.name,
        "slug": topic.slug,
        "description": topic.description,
        "category": topic.category,
        "keywords": topic.keywords,
        "excluded_keywords": topic.excluded_keywords,
        "data_source_ids": topic.data_source_ids,
        "time_range_days": topic.time_range_days,
        "language": topic.language,
        "status": topic.status,
        "updated_at": topic.updated_at.isoformat(),
    }


@router.post("/topics/{topic_id}/ingest")
def trigger_topic_ingestion(
    topic_id: int,
    payload: RunIngestionRequest = RunIngestionRequest(),
    current_user: User = Depends(require_role("analyst")),
    db: Session = Depends(get_db),
):
    """Ingest fresh records for a monitoring topic, run NLP stages, and refresh topic clusters."""
    topic = db.get(MonitoringTopic, topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Monitoring topic not found.")
    if topic.status == "archived":
        raise HTTPException(status_code=400, detail="Cannot ingest into an archived monitoring topic.")

    source = None
    if topic.data_source_ids:
        source = db.scalar(
            select(DataSource).where(DataSource.id.in_(topic.data_source_ids), DataSource.is_enabled.is_(True)).limit(1)
        )
    if not source:
        source = db.scalar(select(DataSource).where(DataSource.is_enabled.is_(True)).limit(1))
    if not source:
        raise HTTPException(status_code=400, detail="No enabled data sources configured.")

    if payload.use_celery:
        task = run_source_ingestion.delay(source.id, topic.id, "manual", payload.batch_size)
        return {"mode": "queued", "task_id": task.id, "source_id": source.id, "topic_id": topic.id}

    job = execute_ingestion_job(
        db=db,
        source=source,
        monitoring_topic=topic,
        job_type="manual",
        triggered_by=current_user,
        batch_size=payload.batch_size,
        publish_live=True,
    )
    # Refresh clusters & trend detection synchronously for this topic so analyst immediately sees updated trends
    recompute_clusters_and_trends(monitoring_topic_id=topic.id)

    return {
        "mode": "completed",
        "job_id": job.id,
        "status": job.status,
        "source_name": source.name,
        "records_fetched": job.records_fetched,
        "records_inserted": job.records_inserted,
        "records_duplicated": job.records_duplicated,
    }


@router.post("/topics/{topic_id}/recluster")
def recluster_topic(
    topic_id: int,
    current_user: User = Depends(require_role("analyst")),
    db: Session = Depends(get_db),
):
    topic = db.get(MonitoringTopic, topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Monitoring topic not found.")
    res = recompute_clusters_and_trends(monitoring_topic_id=topic_id)
    return {"topic_id": topic_id, **res}


@router.get("/explorer/overview")
def get_topic_explorer(
    topic_id: Optional[int] = Query(default=None),
    days: int = Query(default=30, ge=1, le=365),
    source_id: Optional[int] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns topic clusters, keyword co-occurrence relationships, volume trends, and sentiment splits."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)

    active_topic_ids = select(MonitoringTopic.id).where(MonitoringTopic.status != "archived")
    cluster_stmt = (
        select(Cluster)
        .where((Cluster.monitoring_topic_id.is_(None)) | (Cluster.monitoring_topic_id.in_(active_topic_ids)))
        .order_by(Cluster.is_emerging.desc(), Cluster.trend_velocity.desc())
    )
    if topic_id:
        cluster_stmt = select(Cluster).where(Cluster.monitoring_topic_id == topic_id).order_by(
            Cluster.is_emerging.desc(), Cluster.trend_velocity.desc()
        )
    clusters = list(db.scalars(cluster_stmt.limit(24)).all())

    # Query recent records in scope for keyword co-occurrence, trends, and sentiment
    rec_stmt = (
        select(
            ProcessedRecord.id,
            ProcessedRecord.extracted_keywords,
            ProcessedRecord.entities,
            RawRecord.published_at,
            SentimentClassification.predicted_sentiment,
            SentimentClassification.overridden_sentiment,
            SentimentClassification.is_overridden,
            SentimentClassification.sentiment_score,
        )
        .join(RawRecord, RawRecord.id == ProcessedRecord.raw_record_id)
        .join(TopicClassification, TopicClassification.processed_record_id == ProcessedRecord.id)
        .join(SentimentClassification, SentimentClassification.processed_record_id == ProcessedRecord.id)
        .where(ProcessedRecord.is_duplicate.is_(False), RawRecord.published_at >= cutoff)
    )
    if topic_id:
        rec_stmt = rec_stmt.where(TopicClassification.monitoring_topic_id == topic_id)
    if source_id:
        rec_stmt = rec_stmt.where(RawRecord.source_id == source_id)

    rows = db.execute(rec_stmt.order_by(RawRecord.published_at.desc()).limit(6000)).all()

    kw_freq: Counter[str] = Counter()
    pair_freq: Counter[tuple[str, str]] = Counter()
    entity_freq: Counter[tuple[str, str]] = Counter()
    sent_dist = {"positive": 0, "neutral": 0, "mixed": 0, "negative": 0}
    daily: dict[str, dict[str, int | float]] = defaultdict(
        lambda: {"volume": 0, "positive": 0, "neutral": 0, "mixed": 0, "negative": 0, "score_sum": 0.0}
    )

    for r in rows:
        eff_sent = r.overridden_sentiment if (r.is_overridden and r.overridden_sentiment) else r.predicted_sentiment
        sent_dist[eff_sent] = sent_dist.get(eff_sent, 0) + 1
        d = r.published_at.strftime("%Y-%m-%d")
        daily[d]["volume"] += 1
        daily[d][eff_sent] += 1
        daily[d]["score_sum"] += float(r.sentiment_score)

        kws = sorted(set(k.lower() for k in (r.extracted_keywords or []) if len(k) >= 3))[:6]
        for k in kws:
            kw_freq[k] += 1
        for a, b in combinations(kws, 2):
            pair_freq[(a, b)] += 1

        for ent in (r.entities or []):
            if isinstance(ent, dict) and ent.get("text"):
                entity_freq[(ent["text"], ent.get("type", "ENTITY"))] += 1

    volume_trends = [
        {
            "date": d,
            "volume": int(v["volume"]),
            "positive": int(v["positive"]),
            "neutral": int(v["neutral"]),
            "mixed": int(v["mixed"]),
            "negative": int(v["negative"]),
            "avg_sentiment": round(float(v["score_sum"]) / max(int(v["volume"]), 1), 3),
        }
        for d, v in sorted(daily.items())
    ]

    keyword_nodes = [{"term": k, "count": int(c)} for k, c in kw_freq.most_common(16)]
    keyword_edges = [
        {"source": a, "target": b, "co_occurrences": int(cnt)}
        for (a, b), cnt in pair_freq.most_common(18)
    ]

    return {
        "clusters": [
            {
                "id": c.id,
                "monitoring_topic_id": c.monitoring_topic_id,
                "topic_name": c.topic_name,
                "cluster_label": c.cluster_label,
                "summary": c.summary,
                "top_keywords": c.top_keywords,
                "record_count": c.record_count,
                "recent_24h_count": c.recent_24h_count,
                "baseline_daily_avg": c.baseline_daily_avg,
                "avg_sentiment_score": c.avg_sentiment_score,
                "sentiment_breakdown": c.sentiment_breakdown,
                "coherence_score": c.coherence_score,
                "trend_velocity": c.trend_velocity,
                "growth_pct": c.growth_pct,
                "is_emerging": c.is_emerging,
                "embedding_backend": c.embedding_backend,
                "representative_record_ids": c.representative_record_ids,
            }
            for c in clusters
        ],
        "volume_trends": volume_trends,
        "sentiment_distribution": sent_dist,
        "keyword_nodes": keyword_nodes,
        "keyword_relationships": keyword_edges,
        "top_entities": [
            {"text": text, "type": etype, "count": int(cnt)}
            for (text, etype), cnt in entity_freq.most_common(12)
        ],
    }


@router.get("/explorer/compare")
def compare_topics(
    topic_ids: str = Query(description="Comma-separated monitoring topic IDs, e.g. 1,2,3"),
    days: int = Query(default=30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        ids = [int(x.strip()) for x in topic_ids.split(",") if x.strip()][:4]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="topic_ids must be comma-separated integers.") from exc
    if not ids:
        raise HTTPException(status_code=400, detail="Provide at least one topic_id.")

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    topics = list(db.scalars(select(MonitoringTopic).where(MonitoringTopic.id.in_(ids))).all())
    topic_map = {t.id: t for t in topics}

    rows = db.execute(
        select(
            TopicClassification.monitoring_topic_id,
            RawRecord.published_at,
            RawRecord.source_id,
            ProcessedRecord.extracted_keywords,
            SentimentClassification.predicted_sentiment,
            SentimentClassification.overridden_sentiment,
            SentimentClassification.is_overridden,
            SentimentClassification.sentiment_score,
        )
        .join(ProcessedRecord, ProcessedRecord.id == TopicClassification.processed_record_id)
        .join(RawRecord, RawRecord.id == ProcessedRecord.raw_record_id)
        .join(SentimentClassification, SentimentClassification.processed_record_id == ProcessedRecord.id)
        .where(
            ProcessedRecord.is_duplicate.is_(False),
            RawRecord.published_at >= cutoff,
            TopicClassification.monitoring_topic_id.in_(ids),
        )
    ).all()

    agg: dict[int, dict] = {
        tid: {
            "count": 0,
            "score_sum": 0.0,
            "sent": Counter(),
            "sources": set(),
            "kws": Counter(),
        }
        for tid in ids
        if tid in topic_map
    }
    daily_combined: dict[str, dict[str, int | str]] = {}

    for r in rows:
        tid = int(r.monitoring_topic_id)
        if tid not in agg:
            continue
        tname = topic_map[tid].name
        eff_sent = r.overridden_sentiment if (r.is_overridden and r.overridden_sentiment) else r.predicted_sentiment
        agg[tid]["count"] += 1
        agg[tid]["score_sum"] += float(r.sentiment_score)
        agg[tid]["sent"][eff_sent] += 1
        agg[tid]["sources"].add(r.source_id)
        for k in (r.extracted_keywords or []):
            agg[tid]["kws"][k] += 1

        day = r.published_at.strftime("%Y-%m-%d")
        if day not in daily_combined:
            daily_combined[day] = {"date": day}
        daily_combined[day][tname] = int(daily_combined[day].get(tname, 0)) + 1

    summaries = []
    for tid, data in agg.items():
        cnt = max(data["count"], 1)
        summaries.append(
            {
                "topic_id": tid,
                "name": topic_map[tid].name,
                "category": topic_map[tid].category,
                "volume": data["count"],
                "unique_sources": len(data["sources"]),
                "avg_sentiment": round(data["score_sum"] / cnt, 3) if data["count"] else 0.0,
                "sentiment_pct": {
                    "positive": round(data["sent"].get("positive", 0) / cnt * 100.0, 1),
                    "neutral": round(data["sent"].get("neutral", 0) / cnt * 100.0, 1),
                    "mixed": round(data["sent"].get("mixed", 0) / cnt * 100.0, 1),
                    "negative": round(data["sent"].get("negative", 0) / cnt * 100.0, 1),
                },
                "top_keywords": [k for k, _ in data["kws"].most_common(6)],
            }
        )

    series = []
    topic_names = [topic_map[tid].name for tid in agg.keys()]
    for day in sorted(daily_combined.keys()):
        row: dict[str, int | str] = {"date": day}
        for tn in topic_names:
            row[tn] = int(daily_combined[day].get(tn, 0))
        series.append(row)

    return {
        "days": days,
        "topic_names": topic_names,
        "summaries": summaries,
        "daily_comparison": series,
    }
