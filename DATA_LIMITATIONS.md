# Data Limitations, Provenance & Ethical Policy — PulseIQ

## 1. Fundamental Analytical Caveat: Not Scientific Public Opinion Polling

**Aggregate public-discussion volume and automated sentiment MUST NOT be presented or interpreted as a scientifically representative measure of general population opinion.**

Public commentary streams suffer from systematic self-selection bias:
- Residents experiencing acute service disruptions (e.g., transit delays, portal timeouts, extreme heat) post at substantially higher rates than satisfied residents.
- Digitally connected, English-speaking, and civically organized communities are over-represented relative to older, lower-connectivity, or non-English-speaking populations.
- Accordingly, PulseIQ metrics measure **observable agenda salience and expressed tone within configured public channels**, serving as an early-warning diagnostic and qualitative evidence discovery tool rather than a statistical poll.

---

## 2. Synthetic Data Transparency & Provenance

In accordance with enterprise transparency standards:
1. **No Deceptive Simulation**: PulseIQ NEVER presents synthetic data as live social media commentary.
2. **Explicit Flagging**: Every synthetic or synthetic-fallback record carries `raw_records.is_synthetic = TRUE` and an explicit `provenance_label` (`SYNTHETIC_DATASET`, `PREPARED_CSV_SYNTHETIC`, `PUBLIC_RSS_SYNTHETIC_FALLBACK`, `PERMITTED_API_SYNTHETIC_FALLBACK`, or `SYNTHETIC_STREAM`).
3. **UI & Report Disclosure**: Provenance badges appear in every record table, Evidence Inspection Drawer, Overview header, Methodology telemetry page, and inside the mandatory `PROVENANCE DISCLOSURE` banner of every generated Insight Report.
4. **Reproducible Seeded Corpus**: The baseline 52,000-record dataset is deterministically seeded (`SEED = 42`) and archived in `data/synthetic_public_discussions_52k.csv.gz` for transparent auditing and reproducibility.

---

## 3. Known Data Quality & Coverage Limitations

- **Missing Source Fields**: Approximately 4.5% of baseline records omit original titles, anonymized handles, or district metadata (`has_missing_fields = TRUE`). Missing fields are explicitly preserved rather than fabricated.
- **Syndicated Duplicates**: Approximately 3.2% of ingested records are exact or `FWD:` near-duplicates. While deduplicated out of aggregate KPIs and clusters, raw copies remain auditable in `raw_records`.
- **Multilingual Coverage Disparity**: Approximately 86% of baseline corpus volume is English (`en`), with smaller representations in Spanish (`es`, ~6%), French (`fr`, ~4%), German (`de`, ~2.5%), and Portuguese (`pt`, ~1.5%). Automated linear models exhibit lower average confidence on non-English idiomatic phrasing.
- **Temporal & Source Skew**: Different configured adapters exhibit distinct sentiment baselines (for example, Open311 service feedback skews significantly more negative than neighborhood association bulletins). Analysts should inspect source filters before drawing cross-channel conclusions.

---

## 4. NLP Model Limitations

- **Sarcasm & Irony**: Bag-of-n-grams TF-IDF classifiers can misinterpret ironic praise (e.g., *"Great job closing the only bridge lane before the festival"*). PulseIQ mitigates this by lowering calibrated confidence when contrast/irony cues are present and routing low-confidence records to Analyst Workspace for human override.
- **Cross-Domain Overlap**: Civic issues frequently span multiple domains (e.g., municipal budget funding for transit electrification or stormwater drainage). Single-label primary topic classification captures the dominant domain while preserving full multi-class probabilities in the Evidence Drawer.
- **Gazetteer Scope in NER**: Deterministic civic entity extraction prevents generative hallucination but will not recognize newly coined hyper-local landmarks unless added to the civic entity gazetteer.

---

## 5. Ethical & Compliance Guardrails

- **Permitted Ingestion Only**: No scraping of websites or social platforms in violation of terms of service or authentication walls.
- **Privacy Redaction**: URLs, email addresses, and raw `@handles` are redacted during Stage 2 normalisation (`[URL]`, `[EMAIL]`, `[HANDLE]`), while source handles are stored in anonymized form.
- **Prohibited Uses**: Individual political profiling, voter persuasion, micro-targeting, and personal surveillance are out of scope and prohibited by product design.
