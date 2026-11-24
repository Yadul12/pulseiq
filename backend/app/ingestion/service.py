"""Orchestrates Stage 1 (Ingestion) through Stage 7 (NLP Processing) & Live Pub/Sub streaming."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import record_audit_log
from app.ingestion.adapters import get_adapter
from app.models.models import (
    Alert,
    DataSource,
    IngestionJob,
    MonitoringTopic,
    ProcessedRecord,
    RawRecord,
    SentimentClassification,
    TopicClassification,
    User,
)
from app.nlp.pipeline import (
    PIPELINE_VERSION,
    SENTIMENT_MODEL_NAME,
    TOPIC_MODEL_NAME,
    compute_shingle_signature,
    get_nlp_pipeline,
)
from app.services.live_bus import publish_live_event

logger = logging.getLogger(__name__)


def execute_ingestion_job(
    db: Session,
    source: DataSource,
    monitoring_topic: Optional[MonitoringTopic] = None,
    job_type: str = "manual",
    triggered_by: Optional[User] = None,
    batch_size: int = 18,
    publish_live: bool = True,
) -> IngestionJob:
    """Run an incremental ingestion job end-to-end through the 10-stage pipeline."""
    now = datetime.now(timezone.utc)
    job = IngestionJob(
        source_id=source.id,
        monitoring_topic_id=monitoring_topic.id if monitoring_topic else None,
        job_type=job_type,
        status="running",
        cursor_before=source.last_cursor,
        started_at=now,
        triggered_by=triggered_by.id if triggered_by else None,
        error_log=[],
    )
    db.add(job)
    db.flush()

    try:
        adapter = get_adapter(source.provider_type)
        fetch_res = adapter.fetch(source=source, batch_size=batch_size, topic=monitoring_topic)

        job.records_fetched = len(fetch_res.records)
        job.retry_count = fetch_res.retry_count
        job.error_log = list(fetch_res.warnings)

        if not fetch_res.records:
            job.status = "completed"
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
            return job

        # Load recent hashes & shingles for duplicate detection against existing corpus
        recent_rows = db.execute(
            select(ProcessedRecord.id, RawRecord.content_hash, ProcessedRecord.normalized_text)
            .join(RawRecord, RawRecord.id == ProcessedRecord.raw_record_id)
            .order_by(ProcessedRecord.id.desc())
            .limit(2000)
        ).all()
        existing_hashes: dict[str, int] = {}
        existing_shingles: dict[str, int] = {}
        for pid, ch, nt in recent_rows:
            if ch not in existing_hashes:
                existing_hashes[ch] = pid
            if nt and len(nt) > 45:
                sh = compute_shingle_signature(nt)
                if sh not in existing_shingles:
                    existing_shingles[sh] = pid

        pipeline = get_nlp_pipeline()
        texts = [r["original_text"] for r in fetch_res.records]
        nlp_res = pipeline.process_batch(
            texts,
            existing_hashes=existing_hashes,
            existing_shingles=existing_shingles,
        )

        active_topics = list(
            db.scalars(select(MonitoringTopic).where(MonitoringTopic.status != "archived")).all()
        )

        inserted = 0
        duplicated = 0
        batch_proc_ids: list[int] = []
        live_events_to_publish: list[dict] = []

        for idx, rec in enumerate(fetch_res.records):
            raw = RawRecord(
                source_id=source.id,
                ingestion_job_id=job.id,
                external_id=rec["external_id"],
                source_url=rec.get("source_url"),
                author_handle_anonymized=rec.get("author_handle_anonymized"),
                original_title=rec.get("original_title"),
                original_text=rec["original_text"],
                raw_metadata=rec.get("raw_metadata") or {},
                published_at=rec["published_at"],
                ingested_at=datetime.now(timezone.utc),
                content_hash=nlp_res.content_hashes[idx],
                is_synthetic=bool(rec.get("is_synthetic", True)),
                provenance_label=rec.get("provenance_label", "SYNTHETIC_STREAM"),
                has_missing_fields=bool(rec.get("has_missing_fields", False)),
            )
            db.add(raw)
            db.flush()

            dup_ref = nlp_res.duplicate_of_indices[idx]
            resolved_dup_id: Optional[int] = None
            if dup_ref is not None:
                if dup_ref > 0:
                    resolved_dup_id = dup_ref
                else:
                    local_pos = (-dup_ref) - 1
                    if 0 <= local_pos < len(batch_proc_ids):
                        resolved_dup_id = batch_proc_ids[local_pos]

            proc = ProcessedRecord(
                raw_record_id=raw.id,
                normalized_text=nlp_res.normalized_texts[idx],
                detected_language=nlp_res.languages[idx],
                language_confidence=nlp_res.language_confidences[idx],
                is_duplicate=nlp_res.is_duplicates[idx],
                duplicate_of_id=resolved_dup_id,
                similarity_score=nlp_res.similarity_scores[idx],
                entities=nlp_res.entities_list[idx],
                extracted_keywords=nlp_res.keywords_list[idx],
                processing_status=nlp_res.processing_statuses[idx],
                processing_version=PIPELINE_VERSION,
                processed_at=datetime.now(timezone.utc),
            )
            db.add(proc)
            db.flush()
            batch_proc_ids.append(proc.id)

            if monitoring_topic is not None:
                # Honor explicitly targeted monitoring topic when exclusions do not block the record
                lower_nt = proc.normalized_text.lower()
                excl = [ex.lower() for ex in (monitoring_topic.excluded_keywords or []) if ex]
                if not any(ex in lower_nt for ex in excl):
                    matched_mt_id = monitoring_topic.id
                else:
                    matched_mt_id = pipeline.match_monitoring_topic(
                        normalized_text=proc.normalized_text,
                        detected_language=proc.detected_language,
                        source_id=source.id,
                        predicted_topic=nlp_res.predicted_topics[idx],
                        monitoring_topics=active_topics,
                    )
            else:
                matched_mt_id = pipeline.match_monitoring_topic(
                    normalized_text=proc.normalized_text,
                    detected_language=proc.detected_language,
                    source_id=source.id,
                    predicted_topic=nlp_res.predicted_topics[idx],
                    monitoring_topics=active_topics,
                )

            effective_topic_name = (
                monitoring_topic.name
                if (monitoring_topic is not None and matched_mt_id == monitoring_topic.id)
                else nlp_res.predicted_topics[idx]
            )

            tcls = TopicClassification(
                processed_record_id=proc.id,
                monitoring_topic_id=matched_mt_id,
                predicted_topic=effective_topic_name,
                topic_category=(
                    monitoring_topic.category
                    if (monitoring_topic is not None and matched_mt_id == monitoring_topic.id)
                    else nlp_res.topic_categories[idx]
                ),
                confidence=nlp_res.topic_confidences[idx],
                class_probabilities=nlp_res.topic_probabilities[idx],
                model_name=TOPIC_MODEL_NAME,
                model_version="1.0.0",
            )
            scls = SentimentClassification(
                processed_record_id=proc.id,
                predicted_sentiment=nlp_res.predicted_sentiments[idx],
                sentiment_score=nlp_res.sentiment_scores[idx],
                confidence=nlp_res.sentiment_confidences[idx],
                class_probabilities=nlp_res.sentiment_probabilities[idx],
                model_name=SENTIMENT_MODEL_NAME,
                model_version="1.0.0",
            )
            db.add(tcls)
            db.add(scls)

            inserted += 1
            if proc.is_duplicate:
                duplicated += 1

            live_events_to_publish.append(
                {
                    "type": "record.processed",
                    "processed_record_id": proc.id,
                    "raw_record_id": raw.id,
                    "external_id": raw.external_id,
                    "source_id": source.id,
                    "source_name": source.name,
                    "provider_type": source.provider_type,
                    "is_synthetic": raw.is_synthetic,
                    "provenance_label": raw.provenance_label,
                    "published_at": raw.published_at.isoformat(),
                    "processed_at": proc.processed_at.isoformat(),
                    "title": raw.original_title,
                    "excerpt": proc.normalized_text[:240],
                    "language": proc.detected_language,
                    "topic": tcls.predicted_topic,
                    "monitoring_topic_id": tcls.monitoring_topic_id,
                    "topic_confidence": tcls.confidence,
                    "sentiment": scls.predicted_sentiment,
                    "sentiment_score": scls.sentiment_score,
                    "sentiment_confidence": scls.confidence,
                    "is_duplicate": proc.is_duplicate,
                    "processing_status": proc.processing_status,
                }
            )

        job.records_inserted = inserted
        job.records_duplicated = duplicated
        job.cursor_after = fetch_res.next_cursor
        job.status = "partial" if fetch_res.retry_count > 0 else "completed"
        job.completed_at = datetime.now(timezone.utc)

        source.last_cursor = fetch_res.next_cursor
        source.last_ingested_at = job.completed_at
        source.total_records_ingested = (source.total_records_ingested or 0) + inserted
        source.health_status = "degraded" if fetch_res.retry_count > 0 else "healthy"

        record_audit_log(
            db=db,
            action="ingestion.completed",
            resource_type="ingestion_job",
            resource_id=str(job.id),
            details={
                "source_slug": source.slug,
                "monitoring_topic_id": monitoring_topic.id if monitoring_topic else None,
                "inserted": inserted,
                "duplicated": duplicated,
                "used_synthetic_fallback": fetch_res.used_synthetic_fallback,
            },
            actor=triggered_by,
        )
        db.commit()

        if publish_live:
            for ev in live_events_to_publish:
                publish_live_event(ev)

        return job

    except Exception as exc:
        logger.exception("Ingestion job %s failed for source %s", job.id, source.slug)
        job.status = "failed"
        job.records_failed = max(job.records_failed, 1)
        job.completed_at = datetime.now(timezone.utc)
        job.error_log = [
            *(job.error_log or []),
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": "ERROR",
                "code": "INGESTION_EXCEPTION",
                "message": str(exc),
            },
        ]
        source.health_status = "error"
        source.error_count_24h = (source.error_count_24h or 0) + 1
        db.add(
            Alert(
                severity="critical",
                category="ingestion_error",
                title=f"Ingestion Failure: {source.name}",
                message=str(exc),
                resource_type="data_source",
                resource_id=str(source.id),
            )
        )
        db.commit()
        return job
