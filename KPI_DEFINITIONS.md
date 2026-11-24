# KPI & Analytical Metric Definitions — PulseIQ

Every metric surfaced in PulseIQ dashboards, Topic Explorer, Event Intelligence, Methodology telemetry, and Insight Reports follows a strict, auditable SQL/statistical definition.

---

## 1. Overview Dashboard KPIs

| KPI | Definition | SQL / Formula Basis |
| --- | --- | --- |
| **Processed Posts (Window)** | Total ingested records with a completed `processed_records` row whose `raw_records.published_at` falls within the selected trailing window (`24h`, `7d`, `30d`, `90d`, `All`). | `COUNT(processed_records.id)` filtered by `published_at >= now - days` and optional `source_id`. |
| **Deduplicated Posts** | Processed posts excluding exact and near-duplicate copies flagged in Stage 4. Used as the denominator for sentiment shares and trend charts to prevent syndication double-counting. | `COUNT(processed_records.id) WHERE is_duplicate = FALSE`. |
| **Unique Sources** | Count of distinct configured `data_sources` contributing at least one record in the active window. | `COUNT(DISTINCT raw_records.source_id)`. |
| **Emerging Clusters** | Count of semantic topic clusters currently exhibiting statistically significant 72-hour acceleration over their trailing 27-day daily baseline. | `COUNT(clusters.id) WHERE is_emerging = TRUE` ($Z \ge 1.75$, growth $\ge 30\%$, 72h count $\ge 12$). |
| **Aggregate Tone (Mean Polarity)** | Weighted mean of `sentiment_classifications.sentiment_score` across non-duplicate records in scope, ranging from `-1.00` (strongly negative) to `+1.00` (strongly positive). | `AVG(sentiment_score)` across deduplicated records. |
| **Review Backlog** | Count of records with `processing_status IN ('pending', 'needs_review')`, primarily low-confidence predictions (`< 0.56`) awaiting analyst verification. | `COUNT(processed_records.id) WHERE processing_status IN ('pending', 'needs_review')`. |
| **Ingestion Health** | Operational status across configured adapters: `error` if any source has `health_status = 'error'`, `degraded` if any source experienced transient retries/fallbacks, otherwise `healthy`. | Aggregated from `data_sources.health_status`. |
| **Synthetic Share (%)** | Percentage of records in the active window flagged `raw_records.is_synthetic = TRUE`. Explicitly disclosed on Overview and inside every Insight Report. | `100 * COUNT(is_synthetic = TRUE) / COUNT(*)`. |

---

## 2. Topic Explorer & Clustering KPIs

| Metric | Definition |
| --- | --- |
| **Cluster Coherence** | Mean cosine similarity between cluster member embeddings and the L2-normalized cluster centroid (`0.35`–`0.96`). Higher values denote tighter topical cohesion. |
| **Trend Velocity (Z-Score)** | Modified Z-score of 72h daily velocity vs 27-day trailing baseline daily mean and dispersion. |
| **Growth vs Baseline (%)** | `((recent_72h / 3.0) - baseline_daily_avg) / max(baseline_daily_avg, 0.5) * 100`. |
| **Keyword Co-Occurrence** | Number of distinct non-duplicate records in scope containing both keyword $A$ and keyword $B$ among their extracted salient keywords. |

---

## 3. Event Intelligence KPIs

| Metric | Definition |
| --- | --- |
| **Before / During / After Daily Rate** | Total deduplicated records in each phase divided by the phase duration in days (`baseline_days`, `event_days`, `baseline_days`). |
| **Volume Lift (%)** | Percentage change in daily discussion rate from Pre-Event Baseline to Event Window: `((during_rate - before_rate) / max(before_rate, 0.1)) * 100`. |
| **Sentiment Shift ($\Delta$)** | Difference between During-Event mean polarity and Pre-Event mean polarity (`during_avg_sentiment - before_avg_sentiment`). |
| **Theme Lift Ratio** | Smoothed relative prevalence ratio of keyword frequency during the event window vs before the event window. |

---

## 4. Analytical Reliability KPIs (`/methodology`)

| Metric | Definition |
| --- | --- |
| **Duplicate Rate (%)** | Share of all processed records identified as exact (`SHA-256`) or near-duplicate (`shingle`) copies. |
| **Missing Metadata Rate (%)** | Share of raw records where source title, anonymized handle, or geographic metadata was absent on ingestion (`has_missing_fields = TRUE`). |
| **Review Queue Share (%)** | Share of processed records routed to `needs_review` due to topic or sentiment confidence `< 0.56`. |
| **Human Override Count** | Total topic and sentiment classifications explicitly corrected by analysts with recorded audit reasons. |
