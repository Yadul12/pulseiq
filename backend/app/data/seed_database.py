"""Idempotent enterprise database seeder for PulseIQ.

Seeds:
- 4 RBAC users (Admin / Lead Analyst, Senior Analyst, Analyst, Viewer)
- 8 modular Data Sources (CSV, RSS, Permitted API, Synthetic Stream)
- 6 core civic Monitoring Topics
- 52,000 realistic synthetic public discussion records processed through the real 10-stage NLP pipeline
- Semantic Topic Clusters & Emerging Trend Detection metrics
- 3 realistic Civic Events aligned to dataset discussion spikes
- Realistic Ingestion Job logs (including a historical partial retry and transient RSS error)
- Initial Analyst Annotations, verified insights, classification overrides, and audit logs
- 2 grounded Evidence-Backed Insight Reports
- Actionable Notification Centre alerts
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.data.generate_dataset import SOURCES_CATALOG, export_reproducible_datasets, generate_synthetic_records
from app.models.models import (
    Alert,
    AnalystAnnotation,
    AuditLog,
    Cluster,
    ClusterMembership,
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
from app.nlp.pipeline import (
    PIPELINE_VERSION,
    SENTIMENT_MODEL_NAME,
    TOPIC_MODEL_NAME,
    get_cluster_engine,
    get_nlp_pipeline,
)
from app.nlp.training_data import CIVIC_TOPICS, TOPIC_CATEGORY_MAP

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("pulseiq.seed")


INITIAL_MONITORING_TOPICS = [
    {
        "name": "Public Transit & Infrastructure",
        "slug": "public-transit-infrastructure",
        "description": "Monitors commuter rail reliability, bridge maintenance, bus electrification, late-night bus corridors, and arterial road conditions.",
        "category": "Infrastructure",
        "keywords": ["transit", "bridge", "metro", "bus", "pothole", "commute", "fare", "substation", "stormwater"],
        "excluded_keywords": ["sports franchise", "celebrity gossip"],
        "time_range_days": 30,
        "language": "all",
        "status": "active",
    },
    {
        "name": "Government Services & Digital Access",
        "slug": "government-services-digital-access",
        "description": "Tracks resident experience across digital permit portals, licensing queues, 311 ticketing responsiveness, and public library digital access.",
        "category": "Government Services",
        "keywords": ["permit portal", "licensing", "311", "library", "tax filing", "municipal", "kiosk", "digital"],
        "excluded_keywords": ["commercial coupon"],
        "time_range_days": 30,
        "language": "all",
        "status": "active",
    },
    {
        "name": "Environmental & Climate Resilience",
        "slug": "environmental-climate-resilience",
        "description": "Monitors air quality advisories, urban heatwave cooling centers, river water quality, tree canopy initiatives, and curbside composting.",
        "category": "Environment",
        "keywords": ["air quality", "heatwave", "cooling center", "water quality", "tree canopy", "composting", "recycling", "runoff"],
        "excluded_keywords": ["indoor air conditioning ad"],
        "time_range_days": 30,
        "language": "all",
        "status": "active",
    },
    {
        "name": "Public Policy & Housing Affordability",
        "slug": "public-policy-housing-affordability",
        "description": "Follows public consultation around zoning reform, affordable housing trust projects, rent stabilization, and municipal capital budgets.",
        "category": "Public Policy",
        "keywords": ["zoning", "affordable housing", "rent", "budget hearing", "tenant", "reassessment", "council"],
        "excluded_keywords": ["luxury resort"],
        "time_range_days": 60,
        "language": "all",
        "status": "active",
    },
    {
        "name": "Community Issues & Civic Spaces",
        "slug": "community-issues-civic-spaces",
        "description": "Captures neighborhood discussions on park safety lighting, crosswalk visibility, sanitation reliability, youth centers, and food co-ops.",
        "category": "Community",
        "keywords": ["park", "crosswalk", "streetlamp", "sanitation", "playground", "youth", "food co-op", "noise"],
        "excluded_keywords": ["amusement theme park"],
        "time_range_days": 30,
        "language": "all",
        "status": "active",
    },
    {
        "name": "Public Events & Civic Gatherings",
        "slug": "public-events-civic-gatherings",
        "description": "Evaluates crowd logistics, transit detours, accessibility, and resident sentiment around civic festivals, marathons, town halls, and drills.",
        "category": "Public Events",
        "keywords": ["civic festival", "marathon", "town hall", "preparedness drill", "winter storm", "farmers market", "parade"],
        "excluded_keywords": ["private wedding"],
        "time_range_days": 30,
        "language": "all",
        "status": "active",
    },
]


def seed_database() -> None:
    settings = get_settings()
    t0 = time.time()
    db: Session = SessionLocal()
    try:
        existing_raw = db.scalar(select(func.count(RawRecord.id))) or 0
        if existing_raw >= 50000:
            logger.info("PulseIQ database already seeded with %s raw records. Skipping re-seed.", f"{existing_raw:,}")
            return

        now = datetime.now(timezone.utc)
        logger.info("Starting PulseIQ enterprise seed (%s synthetic records)...", f"{settings.SEED_RECORD_COUNT:,}")

        # 1. Seed Users
        users_spec = [
            ("lead.analyst@pulseiq.gov", "Elena Vance", "PulseIQ!2026", "admin", "Civic Intelligence Directorate"),
            ("senior.analyst@pulseiq.gov", "Marcus Chen", "PulseIQ!2026", "senior_analyst", "Infrastructure & Policy Desk"),
            ("analyst@pulseiq.gov", "Priya Nair", "PulseIQ!2026", "analyst", "Public Sentiment & Events Unit"),
            ("viewer@pulseiq.gov", "David Kowalski", "PulseIQ!2026", "viewer", "Executive Policy Briefing"),
        ]
        user_by_email: dict[str, User] = {}
        for email, name, pw, role, dept in users_spec:
            u = db.scalar(select(User).where(User.email == email))
            if not u:
                u = User(
                    email=email,
                    full_name=name,
                    hashed_password=hash_password(pw),
                    role=role,
                    department=dept,
                    is_active=True,
                )
                db.add(u)
                db.flush()
            user_by_email[email] = u

        lead_user = user_by_email["lead.analyst@pulseiq.gov"]
        senior_user = user_by_email["senior.analyst@pulseiq.gov"]
        analyst_user = user_by_email["analyst@pulseiq.gov"]

        # 2. Seed Data Sources
        source_by_slug: dict[str, DataSource] = {}
        for s in SOURCES_CATALOG:
            ds = db.scalar(select(DataSource).where(DataSource.slug == s["slug"]))
            if not ds:
                ds = DataSource(
                    name=s["name"],
                    slug=s["slug"],
                    provider_type=s["provider_type"],
                    description=s["description"],
                    config=s["config"],
                    is_synthetic=s["is_synthetic"],
                    is_enabled=True,
                    schedule_interval_minutes=s["schedule_interval_minutes"],
                    rate_limit_per_min=s["rate_limit_per_min"],
                    last_ingested_at=now - timedelta(minutes=12),
                    health_status="degraded" if s["slug"] == "regional-civic-desk-rss" else "healthy",
                    error_count_24h=1 if s["slug"] == "regional-civic-desk-rss" else 0,
                )
                db.add(ds)
                db.flush()
            source_by_slug[s["slug"]] = ds

        all_source_ids = [ds.id for ds in source_by_slug.values()]

        # 3. Seed Monitoring Topics
        topic_by_name: dict[str, MonitoringTopic] = {}
        for mt_spec in INITIAL_MONITORING_TOPICS:
            mt = db.scalar(select(MonitoringTopic).where(MonitoringTopic.slug == mt_spec["slug"]))
            if not mt:
                mt = MonitoringTopic(
                    name=mt_spec["name"],
                    slug=mt_spec["slug"],
                    description=mt_spec["description"],
                    category=mt_spec["category"],
                    keywords=mt_spec["keywords"],
                    excluded_keywords=mt_spec["excluded_keywords"],
                    data_source_ids=all_source_ids,
                    time_range_days=mt_spec["time_range_days"],
                    language=mt_spec["language"],
                    status=mt_spec["status"],
                    created_by=lead_user.id,
                )
                db.add(mt)
                db.flush()
            topic_by_name[mt.name] = mt

        # 4. Generate 52,000 reproducible synthetic records & export CSV archive
        records = generate_synthetic_records(total_count=settings.SEED_RECORD_COUNT, now=now)
        archive_path, sample_csv_path = export_reproducible_datasets(settings.DATA_DIR, records)
        logger.info("Exported reproducible archive (%s) and prepared CSV (%s)", archive_path, sample_csv_path)

        # Create initial backfill ingestion jobs per source
        backfill_jobs: dict[str, IngestionJob] = {}
        for slug, ds in source_by_slug.items():
            job = IngestionJob(
                source_id=ds.id,
                job_type="backfill",
                status="completed",
                records_fetched=0,
                records_inserted=0,
                records_duplicated=0,
                records_failed=0,
                retry_count=0,
                cursor_before="0",
                cursor_after=None,
                error_log=[],
                started_at=now - timedelta(minutes=25),
                completed_at=now - timedelta(minutes=18),
                triggered_by=lead_user.id,
            )
            db.add(job)
            db.flush()
            backfill_jobs[slug] = job

        # Add one realistic historical partial retry job & one RSS transient error job
        rss_source = source_by_slug["regional-civic-desk-rss"]
        db.add(
            IngestionJob(
                source_id=rss_source.id,
                job_type="scheduled",
                status="partial",
                records_fetched=42,
                records_inserted=38,
                records_duplicated=3,
                records_failed=1,
                retry_count=2,
                cursor_before="rss-2026-11-24T12:00Z",
                cursor_after="rss-2026-11-24T14:00Z",
                error_log=[
                    {
                        "timestamp": (now - timedelta(hours=3)).isoformat(),
                        "level": "WARNING",
                        "code": "UPSTREAM_TIMEOUT_FALLBACK",
                        "message": "External RSS feed timed out after 5s (attempt 2/3); switched cleanly to clearly labelled synthetic fallback provider.",
                    }
                ],
                started_at=now - timedelta(hours=3, minutes=2),
                completed_at=now - timedelta(hours=3),
                triggered_by=None,
            )
        )
        open311_source = source_by_slug["open311-public-feedback-api"]
        db.add(
            IngestionJob(
                source_id=open311_source.id,
                job_type="scheduled",
                status="completed",
                records_fetched=64,
                records_inserted=59,
                records_duplicated=5,
                records_failed=0,
                retry_count=1,
                cursor_before="open311-cur-10410",
                cursor_after="open311-cur-10474",
                error_log=[
                    {
                        "timestamp": (now - timedelta(hours=1)).isoformat(),
                        "level": "INFO",
                        "code": "RATE_LIMIT_BACKOFF",
                        "message": "Rate limit 429 encountered; backed off 1.5s and completed batch cleanly.",
                    }
                ],
                started_at=now - timedelta(hours=1, minutes=1),
                completed_at=now - timedelta(hours=1),
                triggered_by=None,
            )
        )
        db.commit()

        # 5. Process all 52,000 records through the real NLP pipeline & bulk-insert in fast chunks
        pipeline = get_nlp_pipeline()
        chunk_size = 4000
        seen_hashes: dict[str, int] = {}
        seen_shingles: dict[str, int] = {}
        source_counts: dict[str, int] = {slug: 0 for slug in source_by_slug}
        source_dups: dict[str, int] = {slug: 0 for slug in source_by_slug}

        cluster_feed_by_topic: dict[str, list[dict[str, Any]]] = {t: [] for t in CIVIC_TOPICS}
        low_conf_record_ids: list[int] = []
        high_conf_record_ids: list[int] = []

        for start_i in range(0, len(records), chunk_size):
            batch = records[start_i : start_i + chunk_size]
            texts = [r["original_text"] for r in batch]
            nlp_res = pipeline.process_batch(
                texts,
                existing_hashes=seen_hashes,
                existing_shingles=seen_shingles,
            )

            # Insert RawRecords using Core INSERT ... RETURNING id for maximum speed
            raw_payloads = []
            for r, ch in zip(batch, nlp_res.content_hashes):
                ds = source_by_slug[r["source_slug"]]
                job = backfill_jobs[r["source_slug"]]
                source_counts[r["source_slug"]] += 1
                raw_payloads.append(
                    {
                        "source_id": ds.id,
                        "ingestion_job_id": job.id,
                        "external_id": r["external_id"],
                        "source_url": r["source_url"],
                        "author_handle_anonymized": r["author_handle_anonymized"],
                        "original_title": r["original_title"],
                        "original_text": r["original_text"],
                        "raw_metadata": r["raw_metadata"],
                        "published_at": datetime.fromisoformat(r["published_at"]),
                        "ingested_at": now,
                        "content_hash": ch,
                        "is_synthetic": True,
                        "provenance_label": r["provenance_label"],
                        "has_missing_fields": r["has_missing_fields"],
                    }
                )

            raw_ids = list(
                db.scalars(
                    RawRecord.__table__.insert().returning(RawRecord.id),
                    raw_payloads,
                )
            )

            # Insert ProcessedRecords
            proc_payloads = []
            for idx in range(len(batch)):
                if nlp_res.is_duplicates[idx]:
                    source_dups[batch[idx]["source_slug"]] += 1
                dup_ref = nlp_res.duplicate_of_indices[idx]
                resolved_dup_id = dup_ref if (dup_ref is not None and dup_ref > 0) else None
                proc_payloads.append(
                    {
                        "raw_record_id": raw_ids[idx],
                        "normalized_text": nlp_res.normalized_texts[idx],
                        "detected_language": nlp_res.languages[idx],
                        "language_confidence": nlp_res.language_confidences[idx],
                        "is_duplicate": nlp_res.is_duplicates[idx],
                        "duplicate_of_id": resolved_dup_id,
                        "similarity_score": nlp_res.similarity_scores[idx],
                        "entities": nlp_res.entities_list[idx],
                        "extracted_keywords": nlp_res.keywords_list[idx],
                        "processing_status": nlp_res.processing_statuses[idx],
                        "processing_version": PIPELINE_VERSION,
                        "error_message": None,
                        "processed_at": now,
                        "created_at": now,
                    }
                )

            proc_ids = list(
                db.scalars(
                    ProcessedRecord.__table__.insert().returning(ProcessedRecord.id),
                    proc_payloads,
                )
            )

            # Register real processed_record IDs in seen maps for subsequent chunks
            from app.nlp.pipeline import compute_shingle_signature

            for idx, pid in enumerate(proc_ids):
                ch = nlp_res.content_hashes[idx]
                if ch not in seen_hashes:
                    seen_hashes[ch] = pid
                nt = nlp_res.normalized_texts[idx]
                if len(nt) > 45:
                    sh = compute_shingle_signature(nt)
                    if sh not in seen_shingles:
                        seen_shingles[sh] = pid

            # Insert TopicClassifications & SentimentClassifications
            topic_cls_payloads = []
            sent_cls_payloads = []
            for idx, pid in enumerate(proc_ids):
                ptopic = nlp_res.predicted_topics[idx]
                mt = topic_by_name.get(ptopic)
                topic_cls_payloads.append(
                    {
                        "processed_record_id": pid,
                        "monitoring_topic_id": mt.id if mt else None,
                        "predicted_topic": ptopic,
                        "topic_category": nlp_res.topic_categories[idx],
                        "confidence": nlp_res.topic_confidences[idx],
                        "class_probabilities": nlp_res.topic_probabilities[idx],
                        "model_name": TOPIC_MODEL_NAME,
                        "model_version": "1.0.0",
                        "is_overridden": False,
                        "overridden_topic": None,
                        "overridden_by": None,
                        "overridden_at": None,
                        "override_reason": None,
                        "created_at": now,
                    }
                )
                sent_cls_payloads.append(
                    {
                        "processed_record_id": pid,
                        "predicted_sentiment": nlp_res.predicted_sentiments[idx],
                        "sentiment_score": nlp_res.sentiment_scores[idx],
                        "confidence": nlp_res.sentiment_confidences[idx],
                        "class_probabilities": nlp_res.sentiment_probabilities[idx],
                        "model_name": SENTIMENT_MODEL_NAME,
                        "model_version": "1.0.0",
                        "is_overridden": False,
                        "overridden_sentiment": None,
                        "overridden_by": None,
                        "overridden_at": None,
                        "override_reason": None,
                        "created_at": now,
                    }
                )

                # Collect non-duplicate records for clustering & trend computation
                if not nlp_res.is_duplicates[idx]:
                    pub_dt = datetime.fromisoformat(batch[idx]["published_at"])
                    if ptopic in cluster_feed_by_topic:
                        cluster_feed_by_topic[ptopic].append(
                            {
                                "processed_record_id": pid,
                                "normalized_text": nlp_res.normalized_texts[idx],
                                "sentiment": nlp_res.predicted_sentiments[idx],
                                "sentiment_score": nlp_res.sentiment_scores[idx],
                                "published_at": pub_dt,
                            }
                        )
                    if nlp_res.processing_statuses[idx] == "needs_review" and len(low_conf_record_ids) < 40:
                        low_conf_record_ids.append(pid)
                    elif nlp_res.sentiment_confidences[idx] >= 0.70 and len(high_conf_record_ids) < 60:
                        high_conf_record_ids.append(pid)

            db.execute(TopicClassification.__table__.insert(), topic_cls_payloads)
            db.execute(SentimentClassification.__table__.insert(), sent_cls_payloads)
            db.commit()
            logger.info("Processed & persisted %s / %s records...", f"{min(start_i + chunk_size, len(records)):,}", f"{len(records):,}")

        # Update backfill job & source totals
        for slug, ds in source_by_slug.items():
            cnt = source_counts[slug]
            dups = source_dups[slug]
            ds.total_records_ingested = cnt
            ds.last_cursor = f"SYN-BACKFILL-{cnt}"
            ds.last_ingested_at = now - timedelta(minutes=12)
            job = backfill_jobs[slug]
            job.records_fetched = cnt
            job.records_inserted = cnt
            job.records_duplicated = dups
            job.cursor_after = ds.last_cursor
        db.commit()

        # 6. Run Stage 8 & 9 Semantic Clustering & Emerging Trend Detection per Topic
        logger.info("Running semantic clustering & Z-score trend detection across 6 civic topics...")
        cluster_engine = get_cluster_engine()
        emerging_clusters: list[Cluster] = []
        for topic_name, topic_recs in cluster_feed_by_topic.items():
            mt = topic_by_name.get(topic_name)
            # Sample up to 3,500 most recent records per topic for ultra-fast crisp clustering while preserving exact recent counts
            sample_recs = topic_recs[-3500:] if len(topic_recs) > 3500 else topic_recs
            built = cluster_engine.build_topic_clusters(topic_name, sample_recs, n_clusters=3, now=now)
            for c_data in built:
                memberships = c_data.pop("memberships")
                cluster = Cluster(
                    monitoring_topic_id=mt.id if mt else None,
                    **c_data,
                )
                db.add(cluster)
                db.flush()
                if cluster.is_emerging:
                    emerging_clusters.append(cluster)
                # Persist top 400 closest memberships per cluster for drill-down traceability
                memberships.sort(key=lambda x: x[1])
                mem_payload = [
                    {
                        "cluster_id": cluster.id,
                        "processed_record_id": pid,
                        "distance_score": dist,
                    }
                    for pid, dist in memberships[:400]
                ]
                if mem_payload:
                    db.execute(ClusterMembership.__table__.insert(), mem_payload)
        db.commit()

        # 7. Seed 3 realistic Civic Events aligned with the dataset spikes
        transit_mt = topic_by_name["Public Transit & Infrastructure"]
        gov_mt = topic_by_name["Government Services & Digital Access"]
        env_mt = topic_by_name["Environmental & Climate Resilience"]

        events_spec = [
            Event(
                title="Harbor Bridge Emergency Lane Closure",
                description="Multi-day emergency structural resurfacing and lane restriction along Harbor Bridge affecting metropolitan commuter corridors and Route 14 Express buses.",
                event_type="Infrastructure Incident",
                location="Harbor Bridge & Eastside Corridor",
                start_time=now - timedelta(days=46),
                end_time=now - timedelta(days=41),
                baseline_days=7,
                monitoring_topic_ids=[transit_mt.id],
                keywords=["harbor bridge", "lane closure", "detour", "congestion", "route 14"],
                status="completed",
                created_by=lead_user.id,
            ),
            Event(
                title="Municipal Digital Permit Portal Launch",
                description="Citywide launch of the modernized online permit and business licensing portal replacing paper filing workflows across regional departments.",
                event_type="Public Service Rollout",
                location="Citywide Digital Portal",
                start_time=now - timedelta(days=29),
                end_time=now - timedelta(days=24),
                baseline_days=7,
                monitoring_topic_ids=[gov_mt.id],
                keywords=["permit portal", "licensing", "upload", "bilingual", "turnaround"],
                status="completed",
                created_by=senior_user.id,
            ),
            Event(
                title="Riverview Air Quality & Heatwave Advisory",
                description="Sustained extreme heatwave and regional smoke plume prompting air quality advisories and extended municipal Cooling Center Network operations.",
                event_type="Environmental Advisory",
                location="Riverview District & Metro Basin",
                start_time=now - timedelta(days=15),
                end_time=now - timedelta(days=11),
                baseline_days=7,
                monitoring_topic_ids=[env_mt.id],
                keywords=["heatwave", "air quality", "cooling center", "smoke", "riverview"],
                status="completed",
                created_by=lead_user.id,
            ),
        ]
        for ev in events_spec:
            db.add(ev)
        db.commit()

        # 8. Seed realistic Analyst Annotations & Classification Overrides (Human-in-the-Loop)
        section_tags = [
            "Executive Finding",
            "Emerging Risk",
            "Public Service Feedback",
            "Policy Sentiment",
            "Counter-Evidence",
        ]
        notes_pool = [
            "Verified firsthand resident observation citing concrete transit delay intervals.",
            "Representative evidence of bilingual accessibility gap during peak advisory hours.",
            "Sarcastic phrasing initially scored uncertain by linear classifier; corrected after manual reading.",
            "Strong indicator of localized infrastructure bottleneck corroborated across three sources.",
            "Balanced mixed feedback useful for executive briefing nuance.",
        ]
        for idx, pid in enumerate(high_conf_record_ids[:16]):
            analyst = [lead_user, senior_user, analyst_user][idx % 3]
            db.add(
                AnalystAnnotation(
                    processed_record_id=pid,
                    analyst_id=analyst.id,
                    is_bookmarked=idx % 2 == 0,
                    is_verified=idx % 3 != 2,
                    note=notes_pool[idx % len(notes_pool)],
                    tags=["verified-evidence", "q4-briefing"] if idx % 2 == 0 else ["watch-item"],
                    report_section_tag=section_tags[idx % len(section_tags)],
                )
            )

        # Apply 12 authentic analyst overrides on low-confidence records
        for idx, pid in enumerate(low_conf_record_ids[:12]):
            scls = db.scalar(select(SentimentClassification).where(SentimentClassification.processed_record_id == pid))
            if scls:
                corrected = "negative" if scls.predicted_sentiment != "negative" else "mixed"
                scls.is_overridden = True
                scls.overridden_sentiment = corrected
                scls.overridden_by = senior_user.id
                scls.overridden_at = now - timedelta(hours=idx + 2)
                scls.override_reason = "Corrected sarcastic/nuanced civic phrasing after human analyst review."
                db.add(
                    AuditLog(
                        actor_id=senior_user.id,
                        actor_email=senior_user.email,
                        action="sentiment.override",
                        resource_type="processed_record",
                        resource_id=str(pid),
                        details={
                            "predicted": scls.predicted_sentiment,
                            "overridden": corrected,
                            "reason": scls.override_reason,
                        },
                    )
                )
        db.commit()

        # 9. Seed 2 Grounded Intelligence Reports
        from app.services.report_service import generate_grounded_report

        generate_grounded_report(
            db=db,
            title="Metropolitan Transit & Late-Night Corridor Pulse Assessment",
            subtitle="90-Day Aggregate Public Discussion Intelligence & Emerging Risk Brief",
            monitoring_topic_id=transit_mt.id,
            event_id=None,
            time_range_start=now - timedelta(days=30),
            time_range_end=now,
            actor=lead_user,
            status="published",
        )
        generate_grounded_report(
            db=db,
            title="Riverview Heatwave & Air Quality Post-Event Intelligence Brief",
            subtitle="Before-and-After Public Response & Cooling Center Reach Assessment",
            monitoring_topic_id=env_mt.id,
            event_id=events_spec[2].id,
            time_range_start=now - timedelta(days=22),
            time_range_end=now - timedelta(days=8),
            actor=senior_user,
            status="reviewed",
        )

        # 10. Seed Actionable Notification Centre Alerts
        alerts_to_add = [
            Alert(
                severity="warning",
                category="trend_spike",
                title="Emerging Surge: Transit Fare & Late-Night Bus Corridor",
                message="72-hour discussion volume exceeded 30-day rolling baseline (Z-score > 2.0) with elevated negative sentiment around overnight route cuts.",
                resource_type="monitoring_topic",
                resource_id=str(transit_mt.id),
                is_read=False,
            ),
            Alert(
                severity="warning",
                category="ingestion_error",
                title="RSS Adapter Transient Timeout (Auto-Fallback Active)",
                message="Regional Civic Desk Feed experienced an upstream timeout on attempt 2/3 and switched safely to the clearly labelled synthetic fallback provider.",
                resource_type="data_source",
                resource_id=str(rss_source.id),
                is_read=False,
            ),
            Alert(
                severity="info",
                category="review_queue",
                title="Low-Confidence Classification Review Queue Ready",
                message="Multilingual and sarcastic civic posts below 0.56 confidence have been routed to Analyst Workspace for verification.",
                resource_type="workspace",
                resource_id="needs_review",
                is_read=False,
            ),
        ]
        for al in alerts_to_add:
            db.add(al)

        db.add(
            AuditLog(
                actor_id=lead_user.id,
                actor_email=lead_user.email,
                action="system.seed_completed",
                resource_type="platform",
                resource_id="pulseiq",
                details={
                    "records_seeded": len(records),
                    "sources": len(source_by_slug),
                    "topics": len(topic_by_name),
                    "emerging_clusters": len(emerging_clusters),
                },
            )
        )
        db.commit()
        elapsed = time.time() - t0
        logger.info("PulseIQ seed completed in %.1fs (%s records persisted & analyzed).", elapsed, f"{len(records):,}")
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
