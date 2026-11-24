# System Architecture — PulseIQ

## 1. High-Level Topology

```
                        ┌─────────────────────────────────────────┐
                        │   Nginx Static + Reverse Proxy (:3080)  │
                        │   React 18 + TS + Vite + Tailwind SPA   │
                        └───────────┬──────────────────┬──────────┘
                         /api/v1/*  │                  │ /ws/live
                                    ▼                  ▼
                        ┌─────────────────────────────────────────┐
                        │     FastAPI Application (:8080/8000)    │
                        │  Auth/RBAC · REST APIs · WS & SSE Bus   │
                        └──────┬───────────────┬──────────────┬───┘
                               │               │              │
                     SQLAlchemy│               │Pub/Sub       │Task Dispatch
                               ▼               ▼              ▼
                 ┌───────────────────┐  ┌────────────┐  ┌──────────────────┐
                 │  PostgreSQL 16    │  │  Redis 7   │◀─┤ Celery Worker +  │
                 │  (:5480 / 5432)   │  │ (:6390)    │  │ Beat Scheduler   │
                 │  15 Domain Tables │  │ DB0: PubSub│  │ (Ingestion + NLP)│
                 └───────────────────┘  │ DB1: Broker│  └──────────────────┘
                                        │ DB2: Result│
                                        └────────────┘
```

---

## 2. Backend Module Structure (`backend/app/`)

- `core/config.py`: Pydantic Settings configuration (`DATABASE_URL`, `REDIS_URL`, `CELERY_*`, `JWT_*`, `ENABLE_SENTENCE_TRANSFORMERS`).
- `core/database.py`: SQLAlchemy 2.0 connection pool and session lifecycle.
- `core/security.py`: `bcrypt` password hashing, `PyJWT` HS256 token issuance/verification, hierarchical RBAC (`viewer < analyst < senior_analyst < admin`), and `record_audit_log`.
- `models/models.py`: 15 relational tables managed by Alembic (`alembic/versions/0001_initial_schema.py`).
- `nlp/training_data.py`: Independent curated civic training corpus for topic and sentiment models.
- `nlp/pipeline.py`: `CivicNLPPipeline` (Stages 2–7) and `SemanticClusterEngine` (Stages 8–9).
- `ingestion/adapters.py`: Pluggable `CSVAdapter`, `RSSAdapter`, `PublicAPIAdapter`, `SyntheticStreamAdapter` with `TokenBucketRateLimiter` and retry logging.
- `ingestion/service.py`: Transactional ingestion-to-NLP orchestrator that persists raw and processed layers separately and emits live events to Redis.
- `services/event_service.py`: Before / During / After civic event analytics and log-odds emerging theme computation.
- `services/report_service.py`: Evidence-grounded report compiler with traceable `[REC-<id>]` citations.
- `services/live_bus.py`: Redis Pub/Sub publisher (`pulseiq:live_events`).
- `workers/celery_app.py` & `workers/tasks.py`: Celery worker tasks with automatic exponential backoff retries and Celery Beat scheduled incremental ingestion + hourly cluster refresh.
- `api/*.py`: Modular FastAPI routers (`auth`, `overview`, `topics`, `records`, `sources`, `events`, `reports`, `live`).

---

## 3. Relational Data Model (15 Tables)

| Table | Purpose & Key Relationships |
| --- | --- |
| `users` | Enterprise accounts, hashed passwords, RBAC role (`admin`, `senior_analyst`, `analyst`, `viewer`), department |
| `monitoring_topics` | Topic scope definitions (keywords, excluded keywords, data source IDs, language, time window, status) |
| `data_sources` | Modular provider definitions, adapter config JSONB, rate limit, incremental cursor, health status, `is_synthetic` flag |
| `ingestion_jobs` | Execution ledger per run (fetched/inserted/duplicated/failed counts, retries, cursor before/after, JSONB `error_log`) |
| `raw_records` | **Immutable source layer**: original title/text, source URL, anonymized handle, `content_hash`, `is_synthetic`, `provenance_label`, `has_missing_fields` |
| `processed_records` | **NLP output layer** (1:1 FK to `raw_records`): normalized text, language + confidence, `is_duplicate` + `duplicate_of_id`, extracted entities & keywords, `processing_status` |
| `topic_classifications` | Predicted topic + confidence + probability distribution + analyst override fields (`is_overridden`, `overridden_topic`, `override_reason`) |
| `sentiment_classifications` | Predicted 4-class sentiment + continuous score `[-1, 1]` + confidence + probability distribution + analyst override fields |
| `clusters` | Semantic sub-theme clusters per topic with top c-TF-IDF keywords, coherence score, Z-score velocity, growth %, `is_emerging`, and medoid `representative_record_ids` |
| `cluster_memberships` | Normalized join mapping `processed_record_id` to `cluster_id` with cosine distance |
| `events` | Analyst-defined civic event windows (`start_time`, `end_time`, `baseline_days`, topic IDs, keywords) |
| `analyst_annotations` | Per-record bookmarks, verified insight flags, freeform briefing notes, tags, and report section assignments |
| `reports` | Persisted grounded intelligence reports (`executive_summary`, structured `sections` JSONB, `key_metrics`, `evidence_record_ids`, methodology, limitations, provenance disclosure) |
| `audit_logs` | Immutable governance trail of logins, configuration edits, ingestion runs, overrides, and report lifecycle events |
| `alerts` | Operational Notification Centre alerts for emerging spikes, adapter retries/errors, and review backlog notices |

---

## 4. Real-Time Streaming Design

1. When any ingestion job processes a batch (via manual UI trigger, API call, or Celery Beat schedule), `execute_ingestion_job` commits the records to PostgreSQL and publishes compact JSON event payloads to Redis channel `pulseiq:live_events`.
2. FastAPI exposes **both** a WebSocket endpoint (`/ws/live`) and a Server-Sent Events endpoint (`/api/v1/live/stream`) that subscribe asynchronously via `redis.asyncio`.
3. The React `LiveMonitoringPage` bootstraps from `GET /api/v1/live/recent`, establishes a primary WebSocket connection, and automatically falls back to SSE if WebSockets are blocked by an enterprise proxy.

---

## 5. Security & Governance Controls

- Passwords hashed with `bcrypt` (`gensalt(rounds=10)`).
- Stateless bearer JWT authentication (`HS256`) enforced on every intelligence endpoint.
- Role-based authorization decorators (`require_role("analyst")`, `require_role("senior_analyst")`) enforce write permissions server-side.
- Every mutating action writes to `audit_logs` within the same database transaction.
