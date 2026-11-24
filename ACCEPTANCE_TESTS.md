# Acceptance Tests & Verification Protocol — PulseIQ

## 1. End-to-End Analyst Acceptance Scenario

PulseIQ's flagship acceptance test verifies the complete operational intelligence lifecycle against the live PostgreSQL, Redis, FastAPI, and NLP pipeline stack:

1. **Authenticate with RBAC**: Analyst signs in via `POST /api/v1/auth/login` (and confirms `viewer` accounts are blocked with HTTP `403` on write endpoints).
2. **Create a Monitoring Topic**: Analyst creates a custom monitoring topic via `POST /api/v1/topics` with explicit include keywords, excluded keywords, language, time range, and permitted data sources.
3. **Ingest Records from Configured Source**: System executes `POST /api/v1/topics/{id}/ingest`, fetching fresh records through a modular adapter, recording an `IngestionJob` with cursors and counts, and emitting real-time events to Redis Pub/Sub.
4. **Process Through 10-Stage NLP Pipeline**: System stores raw text separately from processed normalized text, runs language detection, duplicate detection, topic classification, 4-class sentiment classification, civic entity extraction, semantic clustering, and modified Z-score trend detection.
5. **Identify Topic Trend & Clusters**: System confirms clusters and trend velocity are persisted and queryable via `GET /api/v1/explorer/overview?topic_id={id}` alongside the 52,000-record corpus emerging spikes.
6. **Review Source Evidence**: Analyst retrieves paginated matched records (`GET /api/v1/records?topic_id={id}`) and inspects dual-layer Raw vs Processed details (`GET /api/v1/records/{record_id}`), bookmarks and marks evidence as verified (`PUT /api/v1/records/{record_id}/annotation`).
7. **Correct Inaccurate Classification**: Analyst applies a verified sentiment/topic override with audit justification (`POST /api/v1/records/{record_id}/override`), verifies `effective_sentiment` reflects the override while `predicted_sentiment` remains preserved, and verifies the `classification.overridden` audit log entry.
8. **Generate Grounded Insight Report & Export**: Analyst generates a report (`POST /api/v1/reports/generate`), verifies grounded `[REC-<id>]` citations, provenance disclosure, methodology, and limitations (`GET /api/v1/reports/{id}`), and downloads both Markdown and Evidence CSV exports (`GET /api/v1/reports/{id}/export` and `GET /api/v1/records/export.csv`).

---

## 2. Automated Test Suite (`backend/tests/test_pulseiq.py`)

Run inside the running backend container (against live PostgreSQL 16 + Redis 7):

```bash
docker compose exec backend pytest -v
```

### Automated Test Coverage Matrix

| Test Case | Verifies |
| --- | --- |
| `test_health_and_52k_corpus_seeded` | PostgreSQL + Redis connectivity and >= 50,000 raw & processed records persisted with synthetic provenance flags, duplicates, missing fields, and 5 languages |
| `test_rbac_authentication_and_viewer_restriction` | JWT login for Admin, Analyst, and Viewer; Viewer receives HTTP 403 on write operations |
| `test_modular_ingestion_adapters_csv_rss_api_stream` | All 4 adapters (`csv`, `rss`, `public_api`, `synthetic_stream`) execute cleanly with incremental cursors, dedup, and transparent synthetic labels |
| `test_nlp_pipeline_stages_and_edge_cases` | Text normalization privacy redaction, multilingual detection (`en/es/fr/de/pt`), exact & near-duplicate detection, entity extraction, and low-confidence sarcasm flagging |
| `test_event_intelligence_before_during_after` | Custom event creation & Before/During/After comparison, volume lift, sentiment delta, emerging themes, and traceable evidence |
| `test_end_to_end_analyst_acceptance_workflow` | Complete 8-step analyst acceptance test: create topic -> ingest -> NLP process -> identify clusters/trends -> review evidence -> verify & override classification -> audit log check -> generate grounded report -> export Markdown & CSV |
| `test_websocket_live_stream_connection` | WebSocket `/ws/live` accepts authenticated connections and emits `connection.ready` telemetry |

---

## 3. Production Build & Visual Verification

1. **Frontend Strict TypeScript & Production Bundle**:
   ```bash
   cd frontend && npm run build
   ```
   (Also verified inside Docker multi-stage build `node:22-alpine` -> `nginx:1.27-alpine`).
2. **Full-Stack Container Health**:
   ```bash
   docker compose up --build -d
   docker compose ps
   ```
   Confirms `pulseiq-postgres`, `pulseiq-redis`, `pulseiq-backend`, `pulseiq-worker`, `pulseiq-beat`, and `pulseiq-frontend` are running and healthy.
3. **Live UI Verification**: Sign in at `http://localhost:3080`, verify Overview telemetry & charts, Monitoring Topics, Topic Explorer & comparison mode, Live Monitoring WebSocket indicator & live batch ingestion, Event Intelligence before/after charts, Analyst Workspace review queue & Evidence Drawer override, Insight Report viewer, Data Sources, Methodology, and Audit Logs.
