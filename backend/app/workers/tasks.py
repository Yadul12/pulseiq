"""Celery background tasks for scheduled ingestion, async processing, and cluster recomputation."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import delete, select

from app.core.database import SessionLocal
from app.ingestion.service import execute_ingestion_job
from app.models.models import (
    Cluster,
    ClusterMembership,
    DataSource,
    MonitoringTopic,
    ProcessedRecord,
    RawRecord,
    SentimentClassification,
    TopicClassification,
)
from app.nlp.pipeline import get_cluster_engine
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.workers.tasks.run_source_ingestion",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def run_source_ingestion(
    self,
    source_id: int,
    monitoring_topic_id: Optional[int] = None,
    job_type: str = "manual",
    batch_size: int = 18,
) -> dict:
    db = SessionLocal()
    try:
        source = db.get(DataSource, source_id)
        if not source:
            return {"status": "error", "detail": f"DataSource {source_id} not found"}
        topic = db.get(MonitoringTopic, monitoring_topic_id) if monitoring_topic_id else None
        job = execute_ingestion_job(
            db=db,
            source=source,
            monitoring_topic=topic,
            job_type=job_type,
            batch_size=batch_size,
            publish_live=True,
        )
        return {
            "job_id": job.id,
            "status": job.status,
            "records_inserted": job.records_inserted,
            "records_duplicated": job.records_duplicated,
        }
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.scheduled_incremental_ingestion")
def scheduled_incremental_ingestion() -> dict:
    """Periodically poll the stalest enabled source so Live Monitoring receives continuous real backend updates."""
    db = SessionLocal()
    try:
        source = db.scalar(
            select(DataSource)
            .where(DataSource.is_enabled.is_(True))
            .order_by(DataSource.last_ingested_at.asc().nullsfirst())
            .limit(1)
        )
        if not source:
            return {"status": "skipped", "reason": "no enabled sources"}
        job = execute_ingestion_job(
            db=db,
            source=source,
            job_type="scheduled",
            batch_size=6,
            publish_live=True,
        )
        logger.info("Scheduled ingestion job #%s (%s): +%d records", job.id, source.slug, job.records_inserted)
        return {"job_id": job.id, "source": source.slug, "inserted": job.records_inserted}
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.recompute_clusters_and_trends")
def recompute_clusters_and_trends(monitoring_topic_id: Optional[int] = None) -> dict:
    """Re-run Stage 8 (semantic clustering) & Stage 9 (Z-score emerging trend detection)."""
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        cluster_engine = get_cluster_engine()

        topic_stmt = select(MonitoringTopic).where(MonitoringTopic.status != "archived")
        if monitoring_topic_id:
            topic_stmt = topic_stmt.where(MonitoringTopic.id == monitoring_topic_id)
        topics = list(db.scalars(topic_stmt).all())

        updated_clusters = 0
        for mt in topics:
            rows = db.execute(
                select(
                    ProcessedRecord.id,
                    ProcessedRecord.normalized_text,
                    RawRecord.published_at,
                    SentimentClassification.predicted_sentiment,
                    SentimentClassification.overridden_sentiment,
                    SentimentClassification.is_overridden,
                    SentimentClassification.sentiment_score,
                )
                .join(RawRecord, RawRecord.id == ProcessedRecord.raw_record_id)
                .join(TopicClassification, TopicClassification.processed_record_id == ProcessedRecord.id)
                .join(SentimentClassification, SentimentClassification.processed_record_id == ProcessedRecord.id)
                .where(
                    ProcessedRecord.is_duplicate.is_(False),
                    TopicClassification.monitoring_topic_id == mt.id,
                )
                .order_by(RawRecord.published_at.desc())
                .limit(3000)
            ).all()

            if not rows:
                continue

            recs = [
                {
                    "processed_record_id": r.id,
                    "normalized_text": r.normalized_text,
                    "sentiment": r.overridden_sentiment if (r.is_overridden and r.overridden_sentiment) else r.predicted_sentiment,
                    "sentiment_score": r.sentiment_score,
                    "published_at": r.published_at,
                }
                for r in rows
            ]
            built = cluster_engine.build_topic_clusters(mt.name, recs, n_clusters=3, now=now)

            # Replace existing clusters for this topic atomically
            db.execute(delete(Cluster).where(Cluster.monitoring_topic_id == mt.id))
            db.flush()

            for c_data in built:
                memberships = c_data.pop("memberships")
                cluster = Cluster(monitoring_topic_id=mt.id, **c_data)
                db.add(cluster)
                db.flush()
                memberships.sort(key=lambda x: x[1])
                if memberships:
                    db.execute(
                        ClusterMembership.__table__.insert(),
                        [
                            {
                                "cluster_id": cluster.id,
                                "processed_record_id": pid,
                                "distance_score": dist,
                            }
                            for pid, dist in memberships[:350]
                        ],
                    )
                updated_clusters += 1

        db.commit()
        return {"status": "completed", "clusters_updated": updated_clusters}
    finally:
        db.close()
