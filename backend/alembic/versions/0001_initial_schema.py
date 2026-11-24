"""Initial PulseIQ enterprise intelligence schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-11-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("department", sa.String(length=120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "monitoring_topics",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("slug", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("keywords", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("excluded_keywords", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("data_source_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("time_range_days", sa.Integer(), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_monitoring_topics_slug", "monitoring_topics", ["slug"])
    op.create_index("ix_monitoring_topics_status", "monitoring_topics", ["status"])

    op.create_table(
        "data_sources",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("slug", sa.String(length=180), nullable=False),
        sa.Column("provider_type", sa.String(length=32), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("schedule_interval_minutes", sa.Integer(), nullable=False),
        sa.Column("rate_limit_per_min", sa.Integer(), nullable=False),
        sa.Column("last_cursor", sa.String(length=255), nullable=True),
        sa.Column("last_ingested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("health_status", sa.String(length=24), nullable=False),
        sa.Column("total_records_ingested", sa.Integer(), nullable=False),
        sa.Column("error_count_24h", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_data_sources_slug", "data_sources", ["slug"])
    op.create_index("ix_data_sources_provider_type", "data_sources", ["provider_type"])
    op.create_index("ix_data_sources_is_synthetic", "data_sources", ["is_synthetic"])

    op.create_table(
        "ingestion_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("monitoring_topic_id", sa.Integer(), nullable=True),
        sa.Column("job_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("records_fetched", sa.Integer(), nullable=False),
        sa.Column("records_inserted", sa.Integer(), nullable=False),
        sa.Column("records_duplicated", sa.Integer(), nullable=False),
        sa.Column("records_failed", sa.Integer(), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("cursor_before", sa.String(length=255), nullable=True),
        sa.Column("cursor_after", sa.String(length=255), nullable=True),
        sa.Column("error_log", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("triggered_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["data_sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["monitoring_topic_id"], ["monitoring_topics.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["triggered_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ingestion_jobs_source_id", "ingestion_jobs", ["source_id"])
    op.create_index("ix_ingestion_jobs_status", "ingestion_jobs", ["status"])
    op.create_index("ix_ingestion_jobs_created_at", "ingestion_jobs", ["created_at"])

    op.create_table(
        "raw_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("ingestion_job_id", sa.Integer(), nullable=True),
        sa.Column("external_id", sa.String(length=160), nullable=False),
        sa.Column("source_url", sa.String(length=512), nullable=True),
        sa.Column("author_handle_anonymized", sa.String(length=120), nullable=True),
        sa.Column("original_title", sa.String(length=400), nullable=True),
        sa.Column("original_text", sa.Text(), nullable=False),
        sa.Column("raw_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), nullable=False),
        sa.Column("provenance_label", sa.String(length=64), nullable=False),
        sa.Column("has_missing_fields", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["data_sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ingestion_job_id"], ["ingestion_jobs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_raw_records_source_id", "raw_records", ["source_id"])
    op.create_index("ix_raw_records_ingestion_job_id", "raw_records", ["ingestion_job_id"])
    op.create_index("ix_raw_records_external_id", "raw_records", ["external_id"])
    op.create_index("ix_raw_records_source_published", "raw_records", ["source_id", "published_at"])
    op.create_index("ix_raw_records_content_hash", "raw_records", ["content_hash"])
    op.create_index("ix_raw_records_published_at", "raw_records", ["published_at"])
    op.create_index("ix_raw_records_is_synthetic", "raw_records", ["is_synthetic"])

    op.create_table(
        "processed_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("raw_record_id", sa.Integer(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("detected_language", sa.String(length=16), nullable=False),
        sa.Column("language_confidence", sa.Float(), nullable=False),
        sa.Column("is_duplicate", sa.Boolean(), nullable=False),
        sa.Column("duplicate_of_id", sa.Integer(), nullable=True),
        sa.Column("similarity_score", sa.Float(), nullable=True),
        sa.Column("entities", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("extracted_keywords", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("processing_status", sa.String(length=24), nullable=False),
        sa.Column("processing_version", sa.String(length=32), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["raw_record_id"], ["raw_records.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["duplicate_of_id"], ["processed_records.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("raw_record_id"),
    )
    op.create_index("ix_processed_records_raw_record_id", "processed_records", ["raw_record_id"])
    op.create_index("ix_processed_records_detected_language", "processed_records", ["detected_language"])
    op.create_index("ix_processed_records_is_duplicate", "processed_records", ["is_duplicate"])
    op.create_index("ix_processed_records_processing_status", "processed_records", ["processing_status"])
    op.create_index("ix_processed_records_status_lang", "processed_records", ["processing_status", "detected_language"])
    op.create_index("ix_processed_records_processed_at", "processed_records", ["processed_at"])

    op.create_table(
        "topic_classifications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("processed_record_id", sa.Integer(), nullable=False),
        sa.Column("monitoring_topic_id", sa.Integer(), nullable=True),
        sa.Column("predicted_topic", sa.String(length=120), nullable=False),
        sa.Column("topic_category", sa.String(length=80), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("class_probabilities", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("model_name", sa.String(length=80), nullable=False),
        sa.Column("model_version", sa.String(length=32), nullable=False),
        sa.Column("is_overridden", sa.Boolean(), nullable=False),
        sa.Column("overridden_topic", sa.String(length=120), nullable=True),
        sa.Column("overridden_by", sa.Integer(), nullable=True),
        sa.Column("overridden_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("override_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["processed_record_id"], ["processed_records.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["monitoring_topic_id"], ["monitoring_topics.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["overridden_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("processed_record_id"),
    )
    op.create_index("ix_topic_classifications_processed_record_id", "topic_classifications", ["processed_record_id"])
    op.create_index("ix_topic_cls_monitoring_topic", "topic_classifications", ["monitoring_topic_id"])
    op.create_index("ix_topic_classifications_predicted_topic", "topic_classifications", ["predicted_topic"])
    op.create_index("ix_topic_classifications_confidence", "topic_classifications", ["confidence"])
    op.create_index("ix_topic_cls_effective", "topic_classifications", ["predicted_topic", "is_overridden"])

    op.create_table(
        "sentiment_classifications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("processed_record_id", sa.Integer(), nullable=False),
        sa.Column("predicted_sentiment", sa.String(length=24), nullable=False),
        sa.Column("sentiment_score", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("class_probabilities", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("model_name", sa.String(length=80), nullable=False),
        sa.Column("model_version", sa.String(length=32), nullable=False),
        sa.Column("is_overridden", sa.Boolean(), nullable=False),
        sa.Column("overridden_sentiment", sa.String(length=24), nullable=True),
        sa.Column("overridden_by", sa.Integer(), nullable=True),
        sa.Column("overridden_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("override_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["processed_record_id"], ["processed_records.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["overridden_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("processed_record_id"),
    )
    op.create_index("ix_sentiment_classifications_processed_record_id", "sentiment_classifications", ["processed_record_id"])
    op.create_index("ix_sentiment_classifications_predicted_sentiment", "sentiment_classifications", ["predicted_sentiment"])
    op.create_index("ix_sentiment_classifications_confidence", "sentiment_classifications", ["confidence"])
    op.create_index("ix_sentiment_cls_effective", "sentiment_classifications", ["predicted_sentiment", "is_overridden"])

    op.create_table(
        "clusters",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("monitoring_topic_id", sa.Integer(), nullable=True),
        sa.Column("topic_name", sa.String(length=120), nullable=False),
        sa.Column("cluster_label", sa.String(length=180), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("top_keywords", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("record_count", sa.Integer(), nullable=False),
        sa.Column("recent_24h_count", sa.Integer(), nullable=False),
        sa.Column("baseline_daily_avg", sa.Float(), nullable=False),
        sa.Column("avg_sentiment_score", sa.Float(), nullable=False),
        sa.Column("sentiment_breakdown", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("coherence_score", sa.Float(), nullable=False),
        sa.Column("trend_velocity", sa.Float(), nullable=False),
        sa.Column("growth_pct", sa.Float(), nullable=False),
        sa.Column("is_emerging", sa.Boolean(), nullable=False),
        sa.Column("embedding_backend", sa.String(length=64), nullable=False),
        sa.Column("time_window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("time_window_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("representative_record_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["monitoring_topic_id"], ["monitoring_topics.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_clusters_topic_name", "clusters", ["topic_name"])
    op.create_index("ix_clusters_is_emerging", "clusters", ["is_emerging"])

    op.create_table(
        "cluster_memberships",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("cluster_id", sa.Integer(), nullable=False),
        sa.Column("processed_record_id", sa.Integer(), nullable=False),
        sa.Column("distance_score", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["cluster_id"], ["clusters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["processed_record_id"], ["processed_records.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cluster_id", "processed_record_id", name="uq_cluster_membership"),
    )
    op.create_index("ix_cluster_memberships_cluster_id", "cluster_memberships", ["cluster_id"])
    op.create_index("ix_cluster_memberships_record", "cluster_memberships", ["processed_record_id"])

    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("location", sa.String(length=160), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("baseline_days", sa.Integer(), nullable=False),
        sa.Column("monitoring_topic_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("keywords", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_events_start_time", "events", ["start_time"])
    op.create_index("ix_events_end_time", "events", ["end_time"])

    op.create_table(
        "analyst_annotations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("processed_record_id", sa.Integer(), nullable=False),
        sa.Column("analyst_id", sa.Integer(), nullable=False),
        sa.Column("is_bookmarked", sa.Boolean(), nullable=False),
        sa.Column("is_verified", sa.Boolean(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("report_section_tag", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["processed_record_id"], ["processed_records.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["analyst_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("processed_record_id", "analyst_id", name="uq_annotation_record_analyst"),
    )
    op.create_index("ix_analyst_annotations_processed_record_id", "analyst_annotations", ["processed_record_id"])
    op.create_index("ix_analyst_annotations_analyst_id", "analyst_annotations", ["analyst_id"])
    op.create_index("ix_analyst_annotations_is_bookmarked", "analyst_annotations", ["is_bookmarked"])
    op.create_index("ix_analyst_annotations_is_verified", "analyst_annotations", ["is_verified"])

    op.create_table(
        "reports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("subtitle", sa.String(length=320), nullable=False),
        sa.Column("monitoring_topic_id", sa.Integer(), nullable=True),
        sa.Column("event_id", sa.Integer(), nullable=True),
        sa.Column("time_range_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("time_range_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("executive_summary", sa.Text(), nullable=False),
        sa.Column("sections", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("key_metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("evidence_record_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("methodology_notes", sa.Text(), nullable=False),
        sa.Column("data_limitations", sa.Text(), nullable=False),
        sa.Column("provenance_disclosure", sa.Text(), nullable=False),
        sa.Column("generated_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["monitoring_topic_id"], ["monitoring_topics.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["generated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reports_status", "reports", ["status"])
    op.create_index("ix_reports_created_at", "reports", ["created_at"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("actor_email", sa.String(length=255), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=64), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_actor_id", "audit_logs", ["actor_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_resource_type", "audit_logs", ["resource_type"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])

    op.create_table(
        "alerts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("category", sa.String(length=48), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=True),
        sa.Column("resource_id", sa.String(length=64), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_alerts_is_read", "alerts", ["is_read"])
    op.create_index("ix_alerts_created_at", "alerts", ["created_at"])


def downgrade() -> None:
    op.drop_table("alerts")
    op.drop_table("audit_logs")
    op.drop_table("reports")
    op.drop_table("analyst_annotations")
    op.drop_table("events")
    op.drop_table("cluster_memberships")
    op.drop_table("clusters")
    op.drop_table("sentiment_classifications")
    op.drop_table("topic_classifications")
    op.drop_table("processed_records")
    op.drop_table("raw_records")
    op.drop_table("ingestion_jobs")
    op.drop_table("data_sources")
    op.drop_table("monitoring_topics")
    op.drop_table("users")
