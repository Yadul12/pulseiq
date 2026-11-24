from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

JSONB = JSON().with_variant(PG_JSONB(), "postgresql")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="analyst")  # admin, senior_analyst, analyst, viewer
    department: Mapped[str] = mapped_column(String(120), nullable=False, default="Public Policy Intelligence")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class MonitoringTopic(Base):
    __tablename__ = "monitoring_topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(160), nullable=False, unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    category: Mapped[str] = mapped_column(String(80), nullable=False, default="Public Policy")
    keywords: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    excluded_keywords: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    data_source_ids: Mapped[list[int]] = mapped_column(JSONB, nullable=False, default=list)
    time_range_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    language: Mapped[str] = mapped_column(String(16), nullable=False, default="all")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active", index=True)  # active, paused, archived
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class DataSource(Base):
    __tablename__ = "data_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(180), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(180), nullable=False, unique=True, index=True)
    provider_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # csv, rss, public_api, synthetic_stream
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    schedule_interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    rate_limit_per_min: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    last_cursor: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_ingested_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    health_status: Mapped[str] = mapped_column(String(24), nullable=False, default="healthy")  # healthy, degraded, error, idle
    total_records_ingested: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count_24h: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False, index=True)
    monitoring_topic_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("monitoring_topics.id", ondelete="SET NULL"), nullable=True, index=True
    )
    job_type: Mapped[str] = mapped_column(String(32), nullable=False, default="incremental")  # scheduled, manual, incremental, backfill
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="queued", index=True)  # queued, running, completed, partial, failed
    records_fetched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_inserted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_duplicated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cursor_before: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    cursor_after: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    error_log: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    triggered_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)

    source: Mapped["DataSource"] = relationship("DataSource")


class RawRecord(Base):
    __tablename__ = "raw_records"
    __table_args__ = (
        Index("ix_raw_records_source_published", "source_id", "published_at"),
        Index("ix_raw_records_content_hash", "content_hash"),
        Index("ix_raw_records_published_at", "published_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False, index=True)
    ingestion_job_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("ingestion_jobs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    external_id: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    author_handle_anonymized: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    original_title: Mapped[Optional[str]] = mapped_column(String(400), nullable=True)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    raw_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    provenance_label: Mapped[str] = mapped_column(String(64), nullable=False, default="SYNTHETIC_DATASET")
    has_missing_fields: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    source: Mapped["DataSource"] = relationship("DataSource")
    processed_record: Mapped[Optional["ProcessedRecord"]] = relationship(
        "ProcessedRecord", back_populates="raw_record", uselist=False
    )


class ProcessedRecord(Base):
    __tablename__ = "processed_records"
    __table_args__ = (
        Index("ix_processed_records_status_lang", "processing_status", "detected_language"),
        Index("ix_processed_records_processed_at", "processed_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    raw_record_id: Mapped[int] = mapped_column(
        ForeignKey("raw_records.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)
    detected_language: Mapped[str] = mapped_column(String(16), nullable=False, default="en", index=True)
    language_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.95)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    duplicate_of_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("processed_records.id", ondelete="SET NULL"), nullable=True
    )
    similarity_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    entities: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    extracted_keywords: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    processing_status: Mapped[str] = mapped_column(String(24), nullable=False, default="processed", index=True)  # pending, processed, needs_review, failed
    processing_version: Mapped[str] = mapped_column(String(32), nullable=False, default="pulseiq-nlp-v1.0")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    raw_record: Mapped["RawRecord"] = relationship("RawRecord", back_populates="processed_record")
    topic_classification: Mapped[Optional["TopicClassification"]] = relationship(
        "TopicClassification", back_populates="processed_record", uselist=False
    )
    sentiment_classification: Mapped[Optional["SentimentClassification"]] = relationship(
        "SentimentClassification", back_populates="processed_record", uselist=False
    )
    annotations: Mapped[list["AnalystAnnotation"]] = relationship(
        "AnalystAnnotation", back_populates="processed_record"
    )


class TopicClassification(Base):
    __tablename__ = "topic_classifications"
    __table_args__ = (
        Index("ix_topic_cls_effective", "predicted_topic", "is_overridden"),
        Index("ix_topic_cls_monitoring_topic", "monitoring_topic_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    processed_record_id: Mapped[int] = mapped_column(
        ForeignKey("processed_records.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    monitoring_topic_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("monitoring_topics.id", ondelete="SET NULL"), nullable=True
    )
    predicted_topic: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    topic_category: Mapped[str] = mapped_column(String(80), nullable=False, default="General Civic")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    class_probabilities: Mapped[dict[str, float]] = mapped_column(JSONB, nullable=False, default=dict)
    model_name: Mapped[str] = mapped_column(String(80), nullable=False, default="tfidf-logreg-civic-v1")
    model_version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0.0")
    is_overridden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    overridden_topic: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    overridden_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    overridden_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    override_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    processed_record: Mapped["ProcessedRecord"] = relationship("ProcessedRecord", back_populates="topic_classification")

    @property
    def effective_topic(self) -> str:
        return self.overridden_topic if self.is_overridden and self.overridden_topic else self.predicted_topic


class SentimentClassification(Base):
    __tablename__ = "sentiment_classifications"
    __table_args__ = (
        Index("ix_sentiment_cls_effective", "predicted_sentiment", "is_overridden"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    processed_record_id: Mapped[int] = mapped_column(
        ForeignKey("processed_records.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    predicted_sentiment: Mapped[str] = mapped_column(String(24), nullable=False, index=True)  # positive, neutral, mixed, negative
    sentiment_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    class_probabilities: Mapped[dict[str, float]] = mapped_column(JSONB, nullable=False, default=dict)
    model_name: Mapped[str] = mapped_column(String(80), nullable=False, default="tfidf-logreg-sentiment-v1")
    model_version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0.0")
    is_overridden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    overridden_sentiment: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    overridden_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    overridden_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    override_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    processed_record: Mapped["ProcessedRecord"] = relationship(
        "ProcessedRecord", back_populates="sentiment_classification"
    )

    @property
    def effective_sentiment(self) -> str:
        return self.overridden_sentiment if self.is_overridden and self.overridden_sentiment else self.predicted_sentiment


class Cluster(Base):
    __tablename__ = "clusters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    monitoring_topic_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("monitoring_topics.id", ondelete="SET NULL"), nullable=True, index=True
    )
    topic_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    cluster_label: Mapped[str] = mapped_column(String(180), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    top_keywords: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    record_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    recent_24h_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    baseline_daily_avg: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_sentiment_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    sentiment_breakdown: Mapped[dict[str, int]] = mapped_column(JSONB, nullable=False, default=dict)
    coherence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.72)
    trend_velocity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)  # Z-score
    growth_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    is_emerging: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    embedding_backend: Mapped[str] = mapped_column(String(64), nullable=False, default="tfidf-svd-dense-64d")
    time_window_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    time_window_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    representative_record_ids: Mapped[list[int]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ClusterMembership(Base):
    __tablename__ = "cluster_memberships"
    __table_args__ = (
        UniqueConstraint("cluster_id", "processed_record_id", name="uq_cluster_membership"),
        Index("ix_cluster_memberships_record", "processed_record_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cluster_id: Mapped[int] = mapped_column(ForeignKey("clusters.id", ondelete="CASCADE"), nullable=False, index=True)
    processed_record_id: Mapped[int] = mapped_column(
        ForeignKey("processed_records.id", ondelete="CASCADE"), nullable=False
    )
    distance_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, default="Infrastructure Incident")
    location: Mapped[str] = mapped_column(String(160), nullable=False, default="Metro Area")
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    baseline_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    monitoring_topic_ids: Mapped[list[int]] = mapped_column(JSONB, nullable=False, default=list)
    keywords: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class AnalystAnnotation(Base):
    __tablename__ = "analyst_annotations"
    __table_args__ = (
        UniqueConstraint("processed_record_id", "analyst_id", name="uq_annotation_record_analyst"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    processed_record_id: Mapped[int] = mapped_column(
        ForeignKey("processed_records.id", ondelete="CASCADE"), nullable=False, index=True
    )
    analyst_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    is_bookmarked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    report_section_tag: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    processed_record: Mapped["ProcessedRecord"] = relationship("ProcessedRecord", back_populates="annotations")
    analyst: Mapped["User"] = relationship("User")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    subtitle: Mapped[str] = mapped_column(String(320), nullable=False, default="")
    monitoring_topic_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("monitoring_topics.id", ondelete="SET NULL"), nullable=True, index=True
    )
    event_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("events.id", ondelete="SET NULL"), nullable=True, index=True
    )
    time_range_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    time_range_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft", index=True)  # draft, reviewed, published
    executive_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    sections: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    key_metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    evidence_record_ids: Mapped[list[int]] = mapped_column(JSONB, nullable=False, default=list)
    methodology_notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    data_limitations: Mapped[str] = mapped_column(Text, nullable=False, default="")
    provenance_disclosure: Mapped[str] = mapped_column(Text, nullable=False, default="")
    generated_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    actor_email: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    resource_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="info")  # info, warning, critical
    category: Mapped[str] = mapped_column(String(48), nullable=False, default="trend_spike")  # trend_spike, ingestion_error, backlog, review_queue
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    resource_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    resource_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
