# Data Ingestion & Processing Pipeline — PulseIQ

## 1. Modular Ingestion Architecture

All ingestion flows conform to a uniform `AdapterFetchResult` contract (`records`, `next_cursor`, `used_synthetic_fallback`, `retry_count`, `warnings`) executed inside `backend/app/ingestion/service.py`.

### Configured Provider Adapters

| Provider Type | Adapter Class | Behavior & Safeguards |
| --- | --- | --- |
| `csv` | `CSVAdapter` | Incrementally reads prepared `.csv` or `.csv.gz` datasets using a persisted row-offset cursor (`csv-row-<N>`). Emits clear diagnostic logs upon EOF or missing path. |
| `rss` | `RSSAdapter` | Parses permitted public RSS/Atom XML feeds via `httpx` + `xml.etree.ElementTree`, enforcing per-source `TokenBucketRateLimiter` and up to 3 retry attempts with backoff. Falls back transparently to `PUBLIC_RSS_SYNTHETIC_FALLBACK` when external feeds are offline or unconfigured. |
| `public_api` | `PublicAPIAdapter` | Consumes permitted public JSON endpoints (e.g., municipal Open311 dockets) with explicit HTTP `429` rate-limit backoff and retries. Falls back transparently to `PERMITTED_API_SYNTHETIC_FALLBACK` when API credentials/endpoints are absent. |
| `synthetic_stream` | `SyntheticStreamAdapter` | Generates clearly labelled synthetic civic records (`SYNTHETIC_STREAM`), optionally scoped to a `MonitoringTopic`'s keywords for reproducible live testing. |

### Reliability & Operational Controls
- **Scheduled Ingestion**: Celery Beat runs `scheduled_incremental_ingestion` every 3 minutes, rotating across the stalest enabled `DataSource` to keep the live feed active.
- **Incremental Cursors**: Every job logs `cursor_before` and `cursor_after` on `ingestion_jobs` and advances `data_sources.last_cursor`.
- **Duplicate Detection**: Every incoming record is hashed (`SHA-256` over normalized alphanumeric text) and fingerprinted with an order-insensitive 8-token shingle signature, checked against both prior database records and earlier records within the same batch.
- **Retry & Error Logging**: Transient failures increment `retry_count` and append structured JSON entries (`timestamp`, `level`, `code`, `message`) to `ingestion_jobs.error_log`. Unrecoverable failures mark the job `failed`, update `data_sources.health_status = 'error'`, and emit a `critical` alert in the Notification Centre.

---

## 2. End-to-End 10-Stage Data Flow

1. **Stage 1 — Ingestion**: Fetch batch via modular adapter; persist untouched raw text and metadata to `raw_records`.
2. **Stage 2 — Text Normalisation**: Unescape HTML, remove markup tags, redact URLs (`[URL]`), emails (`[EMAIL]`), and social handles (`[HANDLE]`) for privacy, collapse whitespace.
3. **Stage 3 — Language Detection**: Identify language (`en`, `es`, `fr`, `de`, `pt`) and record `language_confidence`.
4. **Stage 4 — Duplicate Detection**: Mark exact (`similarity = 1.0`) and near-duplicate (`similarity = 0.92`) records with `is_duplicate = True` and foreign-key `duplicate_of_id`.
5. **Stage 5 — Topic Classification**: Run calibrated scikit-learn TF-IDF + LogisticRegression model and apply active `MonitoringTopic` include/exclude keyword rules.
6. **Stage 6 — Sentiment Classification**: Run calibrated 4-class sentiment classifier (`positive`, `neutral`, `mixed`, `negative`), continuous polarity score `[-1, +1]`, and full class probabilities.
7. **Stage 7 — Entity & Keyword Extraction**: Extract typed civic entities (`AGENCY`, `LOCATION`, `INFRASTRUCTURE`, `POLICY_PROGRAM`, `EVENT`) and salient keywords/bigrams.
8. **Stage 8 — Semantic Clustering**: Embed non-duplicate topic texts into dense L2-normalized semantic space and cluster via `MiniBatchKMeans`, generating c-TF-IDF labels, coherence scores, and medoid evidence IDs.
9. **Stage 9 — Emerging Trend Detection**: Compute 72-hour daily rate vs trailing 27-day daily baseline modified Z-score and percentage lift; flag emerging clusters (`Z >= 1.75` and `growth >= 30%`).
10. **Stage 10 — Analyst Review & Audit**: Route records with topic or sentiment confidence `< 0.56` into `processing_status = 'needs_review'`; human overrides and verified annotations feed directly into Insight Reports and Audit Logs.

---

## 3. Reproducible 52,000-Record Synthetic Dataset

Generated deterministically (`SEED = 42`) by `backend/app/data/generate_dataset.py` and archived to `data/synthetic_public_discussions_52k.csv.gz` (plus a 60-row incremental sample at `data/prepared_civic_consultations_sample.csv`).

### Embedded Realism Properties
- **Volume**: **52,000** records distributed across 90 days across 8 distinct sources with varied sentiment baselines, language distributions, and missingness rates.
- **4 Realistic Multi-Day Spikes**:
  1. *Harbor Bridge Emergency Lane Closure* (Days -46 to -41, Infrastructure surge, negative polarity shift)
  2. *Municipal Digital Permit Portal Launch* (Days -29 to -24, Government Services surge, positive/mixed split)
  3. *Riverview Air Quality & Heatwave Advisory* (Days -15 to -11, Environment surge, cooling center demand)
  4. *Transit Fare & Late-Night Bus Corridor Proposal* (Last 72 hours — active live emerging spike detected by Z-score velocity)
- **Syndicated Duplicates**: ~3.2% (~1,660 records) exact and `FWD:` near-duplicate copies.
- **Missing Fields**: ~4.5% records with missing titles, null anonymized handles, or null districts (`has_missing_fields = True`).
- **Multilingual Coverage**: ~86% English (`en`), ~6% Spanish (`es`), ~4% French (`fr`), ~2.5% German (`de`), ~1.5% Portuguese (`pt`).
- **Classification Edge Cases**: ~4.5% sarcastic or cross-domain posts intentionally included to trigger realistic classifier uncertainty and analyst correction workflows.
- **Provenance**: 100% of synthetic records carry `is_synthetic = True` and explicit provenance tags (`SYNTHETIC_DATASET`, `PREPARED_CSV_SYNTHETIC`, `PUBLIC_RSS_SYNTHETIC_FALLBACK`, `PERMITTED_API_SYNTHETIC_FALLBACK`).
