"""Grounded Evidence-Backed Intelligence Report Generator.

Every analytical claim in generated summaries and sections cites concrete retrieved
`processed_record_id` references (`[REC-xxxxx]`) from PostgreSQL, alongside transparent
provenance disclosure and explicit NLP/sampling limitations.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import record_audit_log
from app.models.models import (
    AnalystAnnotation,
    Cluster,
    DataSource,
    Event,
    MonitoringTopic,
    ProcessedRecord,
    RawRecord,
    Report,
    SentimentClassification,
    TopicClassification,
    User,
)
from app.nlp.pipeline import PIPELINE_VERSION, SENTIMENT_MODEL_NAME, TOPIC_MODEL_NAME


def generate_grounded_report(
    db: Session,
    title: str,
    subtitle: str,
    time_range_start: datetime,
    time_range_end: datetime,
    monitoring_topic_id: Optional[int] = None,
    event_id: Optional[int] = None,
    actor: Optional[User] = None,
    status: str = "draft",
) -> Report:
    """Query verified records, clusters, and sentiment aggregates to produce a grounded report."""
    start = time_range_start if time_range_start.tzinfo else time_range_start.replace(tzinfo=timezone.utc)
    end = time_range_end if time_range_end.tzinfo else time_range_end.replace(tzinfo=timezone.utc)

    topic_obj = db.get(MonitoringTopic, monitoring_topic_id) if monitoring_topic_id else None
    event_obj = db.get(Event, event_id) if event_id else None

    stmt = (
        select(
            ProcessedRecord.id,
            ProcessedRecord.normalized_text,
            ProcessedRecord.detected_language,
            ProcessedRecord.extracted_keywords,
            ProcessedRecord.entities,
            ProcessedRecord.processing_status,
            RawRecord.original_title,
            RawRecord.original_text,
            RawRecord.published_at,
            RawRecord.is_synthetic,
            RawRecord.provenance_label,
            RawRecord.has_missing_fields,
            DataSource.name.label("source_name"),
            TopicClassification.predicted_topic,
            TopicClassification.overridden_topic,
            TopicClassification.is_overridden.label("topic_overridden"),
            TopicClassification.confidence.label("topic_confidence"),
            SentimentClassification.predicted_sentiment,
            SentimentClassification.overridden_sentiment,
            SentimentClassification.is_overridden.label("sent_overridden"),
            SentimentClassification.sentiment_score,
            SentimentClassification.confidence.label("sent_confidence"),
        )
        .join(RawRecord, RawRecord.id == ProcessedRecord.raw_record_id)
        .join(DataSource, DataSource.id == RawRecord.source_id)
        .join(TopicClassification, TopicClassification.processed_record_id == ProcessedRecord.id)
        .join(SentimentClassification, SentimentClassification.processed_record_id == ProcessedRecord.id)
        .where(
            ProcessedRecord.is_duplicate.is_(False),
            RawRecord.published_at >= start,
            RawRecord.published_at <= end,
        )
    )

    if monitoring_topic_id:
        stmt = stmt.where(TopicClassification.monitoring_topic_id == monitoring_topic_id)

    rows = db.execute(stmt.order_by(RawRecord.published_at.desc()).limit(15000)).all()

    total_records = len(rows)
    sent_counts: Counter[str] = Counter()
    lang_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    kw_counts: Counter[str] = Counter()
    entity_counts: Counter[str] = Counter()
    daily_trend: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"volume": 0, "positive": 0, "neutral": 0, "mixed": 0, "negative": 0, "score_sum": 0.0}
    )

    synthetic_count = 0
    missing_fields_count = 0
    overridden_count = 0
    sent_score_sum = 0.0
    conf_sum = 0.0

    for r in rows:
        eff_sent = r.overridden_sentiment if (r.sent_overridden and r.overridden_sentiment) else r.predicted_sentiment
        sent_counts[eff_sent] += 1
        lang_counts[r.detected_language] += 1
        source_counts[r.source_name] += 1
        sent_score_sum += float(r.sentiment_score)
        conf_sum += float(r.sent_confidence)
        if r.is_synthetic:
            synthetic_count += 1
        if r.has_missing_fields:
            missing_fields_count += 1
        if r.sent_overridden or r.topic_overridden:
            overridden_count += 1
        for kw in (r.extracted_keywords or []):
            kw_counts[kw] += 1
        for ent in (r.entities or []):
            if isinstance(ent, dict) and ent.get("text"):
                entity_counts[f"{ent['text']} ({ent.get('type', 'ENTITY')})"] += 1
        day = r.published_at.strftime("%Y-%m-%d")
        daily_trend[day]["volume"] += 1
        daily_trend[day][eff_sent] += 1
        daily_trend[day]["score_sum"] += float(r.sentiment_score)

    # Pull analyst-verified annotations in scope
    row_ids = [r.id for r in rows]
    verified_annotations: list[AnalystAnnotation] = []
    if row_ids:
        verified_annotations = list(
            db.scalars(
                select(AnalystAnnotation)
                .where(
                    AnalystAnnotation.processed_record_id.in_(row_ids[:5000]),
                    AnalystAnnotation.is_verified.is_(True),
                )
                .limit(20)
            ).all()
        )
    verified_id_set = {a.processed_record_id for a in verified_annotations}

    # Pull relevant clusters
    cluster_stmt = select(Cluster)
    if monitoring_topic_id:
        cluster_stmt = cluster_stmt.where(Cluster.monitoring_topic_id == monitoring_topic_id)
    clusters = list(db.scalars(cluster_stmt.order_by(Cluster.trend_velocity.desc()).limit(6)).all())

    # Select balanced, traceable evidence records (verified first, then high-confidence across sentiment classes)
    by_id = {r.id: r for r in rows}
    selected_evidence_ids: list[int] = []
    for vid in verified_id_set:
        if vid in by_id and vid not in selected_evidence_ids:
            selected_evidence_ids.append(vid)
        if len(selected_evidence_ids) >= 5:
            break

    for target_sent in ("negative", "positive", "mixed", "neutral"):
        cands = [
            r
            for r in rows
            if (r.overridden_sentiment if (r.sent_overridden and r.overridden_sentiment) else r.predicted_sentiment) == target_sent
            and r.id not in selected_evidence_ids
        ]
        cands.sort(key=lambda x: x.sent_confidence, reverse=True)
        for c in cands[:2]:
            selected_evidence_ids.append(c.id)
            if len(selected_evidence_ids) >= 12:
                break

    avg_sent = round(sent_score_sum / total_records, 4) if total_records else 0.0
    avg_conf = round(conf_sum / total_records, 3) if total_records else 0.0
    pos_pct = round((sent_counts.get("positive", 0) / max(total_records, 1)) * 100.0, 1)
    neg_pct = round((sent_counts.get("negative", 0) / max(total_records, 1)) * 100.0, 1)
    mix_pct = round((sent_counts.get("mixed", 0) / max(total_records, 1)) * 100.0, 1)
    neu_pct = round((sent_counts.get("neutral", 0) / max(total_records, 1)) * 100.0, 1)
    synth_pct = round((synthetic_count / max(total_records, 1)) * 100.0, 1)

    top_kws = [k for k, _ in kw_counts.most_common(8)]
    top_ents = [e for e, _ in entity_counts.most_common(6)]

    # Build grounded citations string
    cite_refs = [f"[REC-{rid}]" for rid in selected_evidence_ids[:4]]
    cite_str = ", ".join(cite_refs) if cite_refs else "[No records in window]"

    scope_label = topic_obj.name if topic_obj else (event_obj.title if event_obj else "All Monitored Civic Domains")
    peak_day = max(daily_trend.items(), key=lambda kv: kv[1]["volume"])[0] if daily_trend else "N/A"
    peak_vol = daily_trend[peak_day]["volume"] if peak_day in daily_trend else 0

    emerging_summary = (
        f"Emerging sub-theme '{clusters[0].cluster_label}' recorded a {clusters[0].growth_pct:+.1f}% "
        f"volume lift (Z={clusters[0].trend_velocity:+.2f})."
        if clusters and clusters[0].is_emerging
        else "Discussion velocity remained within normal rolling baseline bounds during the reporting period."
    )

    executive_summary = (
        f"Between {start.strftime('%Y-%m-%d')} and {end.strftime('%Y-%m-%d')}, PulseIQ analyzed {total_records:,} "
        f"deduplicated public-discussion records across {len(source_counts)} configured sources within scope "
        f"'{scope_label}'. Daily activity peaked on {peak_day} ({peak_vol:,} records). "
        f"Aggregate automated sentiment registered {neg_pct}% negative, {mix_pct}% mixed, {neu_pct}% neutral, "
        f"and {pos_pct}% positive (mean polarity {avg_sent:+.2f}; mean model confidence {avg_conf:.2f}), "
        f"incorporating {overridden_count} human analyst classification overrides and {len(verified_annotations)} "
        f"verified evidence annotations. {emerging_summary} "
        f"Key recurring themes centered on {', '.join(top_kws[:5]) if top_kws else 'general civic operations'}. "
        f"Representative primary source evidence is traced directly to retrieved records {cite_str}."
    )

    trend_series = [
        {
            "date": day,
            "volume": vals["volume"],
            "positive": vals["positive"],
            "neutral": vals["neutral"],
            "mixed": vals["mixed"],
            "negative": vals["negative"],
            "avg_sentiment": round(vals["score_sum"] / max(vals["volume"], 1), 3),
        }
        for day, vals in sorted(daily_trend.items())
    ]

    key_themes = [
        {
            "cluster_id": c.id,
            "label": c.cluster_label,
            "record_count": c.record_count,
            "trend_velocity": c.trend_velocity,
            "growth_pct": c.growth_pct,
            "is_emerging": c.is_emerging,
            "top_keywords": c.top_keywords,
            "summary": c.summary,
            "representative_record_ids": c.representative_record_ids[:3],
        }
        for c in clusters
    ]

    analyst_notes_section = [
        {
            "processed_record_id": a.processed_record_id,
            "section_tag": a.report_section_tag or "Analyst Finding",
            "note": a.note,
            "tags": a.tags,
        }
        for a in verified_annotations
        if a.note
    ]

    methodology_notes = (
        f"Records were processed through the {PIPELINE_VERSION} 10-stage pipeline: modular ingestion, "
        f"privacy-preserving normalization (raw original text archived separately), multilingual language detection, "
        f"exact & shingle near-duplicate filtering, calibrated TF-IDF + LogisticRegression topic classification "
        f"({TOPIC_MODEL_NAME}), 4-class sentiment scoring ({SENTIMENT_MODEL_NAME}), civic named-entity extraction, "
        f"semantic MiniBatchKMeans clustering, modified Z-score emerging-trend detection, and human-in-the-loop analyst "
        f"verification. Human overrides take precedence over model predictions while preserving full audit lineage."
    )

    data_limitations = (
        f"1. Non-Representative Sampling: Public discussion feeds reflect vocal civic participants and configured "
        f"channels, NOT scientifically sampled public opinion polling.\n"
        f"2. Synthetic Data Transparency: {synthetic_count:,} of {total_records:,} records ({synth_pct}%) in this report "
        f"originate from clearly labelled synthetic or synthetic-fallback datasets.\n"
        f"3. Missing Metadata: {missing_fields_count:,} records ({round(missing_fields_count / max(total_records, 1) * 100, 1)}%) "
        f"contained missing titles, anonymized handles, or district tags.\n"
        f"4. Classifier Uncertainty: Automated linear classifiers can misinterpret sarcasm, domain overlap, and non-English "
        f"idioms ({sum(v for k, v in lang_counts.items() if k != 'en'):,} non-English records in scope); predictions below 0.56 "
        f"confidence are explicitly routed for analyst review."
    )

    provenance_disclosure = (
        f"PROVENANCE DISCLOSURE: {synth_pct}% synthetic / prepared synthetic-fallback records "
        f"({synthetic_count:,}/{total_records:,}) across {len(source_counts)} sources. "
        f"No unauthorized platform scraping or individual voter/political profiling was performed."
    )

    report = Report(
        title=title,
        subtitle=subtitle,
        monitoring_topic_id=monitoring_topic_id,
        event_id=event_id,
        time_range_start=start,
        time_range_end=end,
        status=status,
        executive_summary=executive_summary,
        sections={
            "topic_overview": {
                "scope_name": scope_label,
                "description": topic_obj.description if topic_obj else (event_obj.description if event_obj else "Cross-domain public intelligence overview."),
                "keywords": topic_obj.keywords if topic_obj else top_kws,
                "top_entities": top_ents,
                "language_distribution": dict(lang_counts),
                "source_distribution": dict(source_counts),
            },
            "discussion_trends": {
                "peak_date": peak_day,
                "peak_volume": peak_vol,
                "daily_series": trend_series,
            },
            "aggregate_sentiment": {
                "avg_score": avg_sent,
                "avg_confidence": avg_conf,
                "breakdown": {
                    "positive": sent_counts.get("positive", 0),
                    "neutral": sent_counts.get("neutral", 0),
                    "mixed": sent_counts.get("mixed", 0),
                    "negative": sent_counts.get("negative", 0),
                },
                "percentages": {
                    "positive": pos_pct,
                    "neutral": neu_pct,
                    "mixed": mix_pct,
                    "negative": neg_pct,
                },
                "caveat": "Aggregate sentiment reflects automated lexical tone across ingested sources and must not be interpreted as a scientific opinion poll.",
            },
            "key_themes": key_themes,
            "analyst_verified_findings": analyst_notes_section,
        },
        key_metrics={
            "total_records": total_records,
            "unique_sources": len(source_counts),
            "avg_sentiment": avg_sent,
            "avg_confidence": avg_conf,
            "negative_pct": neg_pct,
            "positive_pct": pos_pct,
            "synthetic_pct": synth_pct,
            "analyst_overrides": overridden_count,
            "verified_evidence_count": len(verified_annotations),
        },
        evidence_record_ids=selected_evidence_ids,
        methodology_notes=methodology_notes,
        data_limitations=data_limitations,
        provenance_disclosure=provenance_disclosure,
        generated_by=actor.id if actor else None,
    )
    db.add(report)
    db.flush()

    record_audit_log(
        db=db,
        action="report.generated",
        resource_type="report",
        resource_id=str(report.id),
        details={
            "title": title,
            "monitoring_topic_id": monitoring_topic_id,
            "event_id": event_id,
            "records_analyzed": total_records,
            "evidence_citations": len(selected_evidence_ids),
        },
        actor=actor,
    )
    db.commit()
    db.refresh(report)
    return report
