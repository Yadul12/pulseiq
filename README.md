# PulseIQ — Enterprise Social Intelligence & Public-Data Trend Monitoring Platform

PulseIQ is an enterprise-grade public-data intelligence, NLP trend-monitoring, and evidence-backed reporting platform built for civic, policy, infrastructure, and public-operations analysts.

It monitors public discussions across **public events**, **government services**, **infrastructure issues**, **public policies**, **environmental concerns**, and **community issues** using permitted public APIs, public RSS feeds, prepared CSV datasets, and clearly labelled synthetic datasets — **without unauthorized scraping or individual political profiling**.

---

## Core Capabilities

- **Monitoring Workspace**: Define, edit, pause, and archive monitoring topics with include/exclude keyword rules, source bindings, language filters, and time windows.
- **Modular Ingestion Architecture**: Provider adapters for Prepared CSV (`CSVAdapter`), Public RSS (`RSSAdapter`), Permitted Public JSON APIs (`PublicAPIAdapter`), and Synthetic Event Streams (`SyntheticStreamAdapter`), complete with incremental cursor tracking, token-bucket rate-limiting, exponential backoff retry, and full diagnostic error logs.
- **10-Stage NLP Intelligence Pipeline**: Real Python + Pandas + Scikit-learn pipeline separating immutable original source records from processed outputs — supporting normalisation, multilingual language detection (`en`, `es`, `fr`, `de`, `pt`), exact & near-duplicate detection, calibrated topic & 4-class sentiment classification, civic entity extraction, semantic clustering (optional `sentence-transformers` or deterministic `TF-IDF + TruncatedSVD` dense embeddings + `MiniBatchKMeans`), and modified Z-score emerging-topic burst detection.
- **Real-Time Live Monitoring**: WebSocket (`/ws/live`) and Server-Sent Events (`/api/v1/live/stream`) powered by Redis Pub/Sub and Celery background tasks.
- **Event Intelligence**: Define civic event time windows and evaluate Before / During / After volume rates, polarity shifts, topic surges, log-odds emerging themes, and traceable primary evidence.
- **Analyst Workspace & Human-in-the-Loop Governance**: Confidence-routed review queue (`< 56%`), bookmarking, evidence verification, classification overrides (preserving original predictions with mandatory justification and immutable audit logs), and streaming CSV exports.
- **Grounded Insight Reports**: Structured executive briefings citing exact `[REC-<id>]` source records retrieved from PostgreSQL, complete with Methodology, Data Limitations, Provenance Disclosure, Markdown export, and Evidence Pack CSV export.

---

## Architecture & Stack

| Layer | Technologies |
| --- | --- |
| **Frontend** | React 18, TypeScript, Vite, Tailwind CSS, React Router v6, TanStack Query v5, Recharts, Lucide Icons, Nginx |
| **Backend** | FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL 16, Redis 7, Celery (Worker + Beat), WebSockets & SSE, PyJWT + bcrypt RBAC |
| **NLP & Data** | Python 3.12, Pandas, NumPy, Scikit-learn, SciPy, optional Sentence-Transformers |
| **Reproducible Corpus** | 52,000 synthetic public discussion records (`data/synthetic_public_discussions_52k.csv.gz`) with 4 realistic multi-day spikes, ~3.2% duplicates, ~4.5% missing fields, 5 languages, and ~4.5% classification edge cases |

---

## Quick Start (Docker Compose)

```bash
docker compose up --build -d
```

On first startup, the backend container automatically:
1. Runs Alembic migrations (`alembic upgrade head`).
2. Generates and exports the reproducible 52,000-record synthetic civic corpus into `data/synthetic_public_discussions_52k.csv.gz` and `data/prepared_civic_consultations_sample.csv`.
3. Processes all 52,000 records through the real scikit-learn NLP pipeline and persists raw records, processed records, topic/sentiment classifications, semantic clusters, civic events, analyst annotations, overrides, alerts, and grounded reports in PostgreSQL.

### Service Endpoints

| Service | URL |
| --- | --- |
| **PulseIQ Web Console** | http://localhost:3080 |
| **FastAPI Backend & OpenAPI Docs** | http://localhost:8080/docs |
| **Health Telemetry** | http://localhost:8080/api/v1/health |
| **PostgreSQL 16** | `localhost:5480` (`pulseiq` / `pulseiq_secret_2026`) |
| **Redis 7** | `localhost:6390` |

### Pre-Seeded Role-Based Accounts

| Role | Email | Password | Permissions |
| --- | --- | --- | --- |
| **Admin / Lead Analyst** | `lead.analyst@pulseiq.gov` | `PulseIQ!2026` | Full platform, sources, topics, overrides, reports, audit |
| **Senior Analyst** | `senior.analyst@pulseiq.gov` | `PulseIQ!2026` | Sources, topics, events, overrides, reports |
| **Analyst** | `analyst@pulseiq.gov` | `PulseIQ!2026` | Topics, ingestion runs, overrides, annotations, reports |
| **Viewer** | `viewer@pulseiq.gov` | `PulseIQ!2026` | Read-only dashboards, explorer, events, reports, CSV export |

---

## Documentation Suite

- [PRD.md](./PRD.md) — Product Requirements Document & ethical guardrails
- [ARCHITECTURE.md](./ARCHITECTURE.md) — System architecture, data model, RBAC, and real-time design
- [DATA_PIPELINE.md](./DATA_PIPELINE.md) — Modular ingestion adapters, retry/rate-limit rules, and 52k corpus design
- [NLP_METHODOLOGY.md](./NLP_METHODOLOGY.md) — 10-stage NLP pipeline, calibration, clustering, and burst detection
- [KPI_DEFINITIONS.md](./KPI_DEFINITIONS.md) — Mathematical definitions for every dashboard & report metric
- [DATA_LIMITATIONS.md](./DATA_LIMITATIONS.md) — Sampling caveats, bias disclosure, synthetic provenance, and non-polling policy
- [ACCEPTANCE_TESTS.md](./ACCEPTANCE_TESTS.md) — Automated verification suite and end-to-end analyst acceptance walk-through
