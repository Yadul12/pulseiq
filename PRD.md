# Product Requirements Document (PRD) — PulseIQ

## 1. Product Vision & Objective

PulseIQ is an enterprise public-data intelligence and trend-monitoring platform engineered for civic analysts, municipal policy researchers, infrastructure planners, and public affairs teams. Its purpose is to transform fragmented public discussion streams into structured, traceable, evidence-backed intelligence covering:

1. **Public Transit & Infrastructure**
2. **Government Services & Digital Access**
3. **Environmental & Climate Resilience**
4. **Public Policy & Housing Affordability**
5. **Community Issues & Civic Spaces**
6. **Public Events & Civic Gatherings**

### Non-Goals & Ethical Boundaries
- **No unauthorized scraping**: PulseIQ never scrapes platforms in violation of their terms of service.
- **No individual profiling or voter targeting**: PulseIQ operates strictly on aggregate public commentary and explicitly excludes individual political profiling, voter scoring, persuasion workflows, or personal tracking.
- **No deceptive synthetic labeling**: Whenever external credentials or endpoints are unavailable, synthetic fallback streams are prominently flagged at the source, record, UI, and report levels.
- **Not a chatbot or static sentiment dashboard**: Every chart drills down into auditable raw source records, model probabilities, and analyst verification tools.

---

## 2. Target Personas & RBAC Matrix

| Persona | Role Key | Primary Responsibilities |
| --- | --- | --- |
| **Intelligence Director** | `admin` | Governance oversight, audit review, user access, source adapter registration, report publication |
| **Senior Policy Analyst** | `senior_analyst` | Source configuration, event window analysis, reviewing analyst overrides, approving reports |
| **Monitoring Analyst** | `analyst` | Creating/managing monitoring topics, triggering ingestion, verifying evidence, overriding misclassifications, drafting reports |
| **Executive Stakeholder** | `viewer` | Viewing dashboards, exploring topics/events, reading published reports, downloading CSV/Markdown briefs |

---

## 3. Functional Requirements

### 3.1 Monitoring Workspace (`/topics`)
- Analysts create, edit, pause, resume, and archive monitoring topics containing: Name, Description, Civic Category, Include Keywords, Excluded Keywords, Permitted Data Sources, Default Time Window (days), Language filter, and Status (`active`, `paused`, `archived`).
- Analysts can trigger immediate incremental ingestion and re-clustering for any active topic.

### 3.2 Modular Data Ingestion (`/sources`)
- Provider adapters for Prepared CSV, Public RSS, Permitted Public JSON APIs, and Synthetic Event Streams.
- Cursor-based incremental sync, per-source rate limits, exponential backoff retries, duplicate tracking, and structured per-job error/warning logs.

### 3.3 Intelligence Modules
- **Overview Dashboard (`/`)**: Compact KPI strip (processed posts, unique sources, emerging clusters, aggregate tone, review backlog, ingestion health), topic activity time series, aggregate sentiment breakdown with non-polling caveat, emerging watchlist, and source health table.
- **Topic Explorer (`/explorer`)**: Semantic clusters with coherence and burst Z-score, keyword co-occurrence relationships, civic entities, daily volume/sentiment chart, side-by-side multi-topic comparison, and paginated representative source posts.
- **Live Monitoring (`/live`)**: Real-time backend activity feed via WebSockets (`/ws/live`) with SSE fallback (`/api/v1/live/stream`), pause/resume controls, topic/sentiment filters, and on-demand live batch ingestion.
- **Event Intelligence (`/events`)**: Custom civic event time-window definitions producing Before / During / After daily rate shifts, polarity deltas, topic volume changes, emerging log-odds keywords, and primary evidence tables.
- **Analyst Workspace (`/workspace`)**: Low-confidence review queue (`< 56%`), bookmarks, verified insights, override ledger, annotation & report section tagging, and filtered CSV export.
- **Insight Reports (`/reports`)**: Evidence-grounded report generation citing retrieved `[REC-<id>]` source records across Executive Summary, Topic Overview, Discussion Trends, Aggregate Sentiment, Key Themes, Representative Source Evidence, Methodology, Data Limitations, and Provenance Disclosure; exportable as Markdown and Evidence CSV.
- **Methodology & Reliability (`/methodology`)**: Live corpus telemetry, model registry, classification definitions, 10-stage pipeline transparency, and bias/sampling limitations.
- **Audit & Access (`/admin`)**: Immutable audit log and RBAC directory.

---

## 4. Non-Functional Requirements

- **Traceability**: Raw source text (`raw_records`) and processed pipeline outputs (`processed_records`) are stored in separate normalized PostgreSQL tables linked via foreign key.
- **Scale & Performance**: Handles >= 50,000 persisted records cleanly with indexed SQL queries, server-side pagination, and sub-second dashboard aggregation.
- **Visual Design**: Deep navy collapsible navigation (`#0B1628`), neutral analytical workspace (`#F4F6F9`), crisp white surfaces, restrained indigo accents, muted green/amber/red sentiment tokens, tabular numerals, compact tables, and responsive layouts with loading, empty, error, and success states.
