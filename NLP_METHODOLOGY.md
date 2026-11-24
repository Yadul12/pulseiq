# NLP Methodology & Analytical Reliability — PulseIQ

## 1. Design Philosophy

Enterprise public-intelligence systems must prioritize **interpretability, reproducibility, calibrated uncertainty, and human-in-the-loop accountability** over opaque black-box scoring. PulseIQ's NLP stack (`pulseiq-nlp-v1.0`) exposes model versions, class probability vectors, calibrated confidence scores, and analyst override history alongside every record.

---

## 2. Classification Models & Calibration

### 2.1 Topic Classification (`tfidf-logreg-civic-v1`)
- **Architecture**: Scikit-learn `Pipeline` pairing `TfidfVectorizer(ngram_range=(1,2), sublinear_tf=True, max_features=8000)` with multinomial `LogisticRegression(C=2.6, max_iter=1000, random_state=42)`.
- **Training Separation**: Trained on a curated multilingual civic corpus (`backend/app/nlp/training_data.py`) covering 6 core public domains, deliberately decoupled from synthetic record templates so out-of-sample evaluation produces realistic uncertainty rather than artificial 100% accuracy.
- **Monitoring Topic Binding**: After classification, `match_monitoring_topic()` evaluates analyst-defined `MonitoringTopic` rules (include keywords, excluded keywords, language filter, and bound data source IDs) so newly created analyst topics immediately capture matching public commentary.

### 2.2 Sentiment Classification (`tfidf-logreg-sentiment-v1`)
- **Classes**:
  - `positive`: Explicit approval, constructive satisfaction, or verified service improvement.
  - `neutral`: Factual advisories, schedules, procedural announcements, or non-evaluative notices.
  - `mixed`: Balanced commentary recognizing both progress and unresolved concerns.
  - `negative`: Service disruption reports, safety hazards, dissatisfaction, or policy objections.
- **Continuous Polarity Score**: Computed in `[-1.0, +1.0]` as `P(positive) - P(negative) + 0.04 * P(mixed)`, softly aligned with class boundaries.
- **Confidence Calibration & Sarcasm Penalty**: Calibrated from winning class probability and top-2 class margin. Explicit confidence penalties are applied when ironic/contrast cues (`"great job"`, `"truly inspiring"`, `"brilliant planning"`, `"although"`, `"however"`) or non-English tokens appear, ensuring uncertain predictions (`< 0.56`) surface automatically in the `needs_review` queue.

---

## 3. Entity & Keyword Extraction

- **Civic Named-Entity Recognition**: Deterministic gazetteer & pattern matcher extracting five entity classes (`AGENCY`, `LOCATION`, `INFRASTRUCTURE`, `POLICY_PROGRAM`, `EVENT`) with zero generative hallucination.
- **Keyword Extraction & Co-Occurrence**: Extracts salient unigrams and bigrams after multilingual stopword removal. In Topic Explorer, pairwise keyword co-occurrence matrices are computed dynamically across records in scope.

---

## 4. Semantic Embedding & Topic Clustering

- **Dual Embedding Backend**:
  - When `ENABLE_SENTENCE_TRANSFORMERS=true` and `sentence-transformers` is installed, PulseIQ encodes texts using `SentenceTransformer("all-MiniLM-L6-v2")` with L2 normalization.
  - In CPU-only / offline deterministic environments (`ENABLE_SENTENCE_TRANSFORMERS=false`, default for reproducible Docker builds), `SemanticClusterEngine` constructs L2-normalized 48-dimensional dense semantic vectors via `TfidfVectorizer(ngram_range=(1,2), sublinear_tf=True)` + `TruncatedSVD(n_components=48, random_state=42)` + `Normalizer`.
  - The exact backend used (`tfidf-svd-dense-48d` or `sentence-transformers:...`) is stored on every `clusters` row and displayed in `/methodology`.
- **Clustering**: `MiniBatchKMeans` partitions non-duplicate records per topic into cohesive sub-theme clusters.
- **Distinctive Labeling (`c-TF-IDF`)**: Cluster keywords are ranked by cluster term-frequency lift relative to the global topic corpus (`sub_mean - 0.55 * global_mean`).
- **Coherence & Medoid Evidence**: Intra-cluster mean cosine similarity measures coherence; the 8 records closest to each cluster centroid are persisted as `representative_record_ids`.

---

## 5. Emerging Trend & Event Detection

### 5.1 Modified Z-Score Burst Velocity (Overview & Topic Explorer)
For each cluster, let $R_{72h}$ be the daily record rate over the trailing 72 hours and let $\mu_{base}, \sigma_{base}$ be the mean and standard deviation of daily counts over the preceding 27 days:

$$Z = \frac{R_{72h} - \mu_{base}}{\max(\sigma_{base}, \sqrt{\max(\mu_{base}, 1)}, 1)}$$

A cluster is flagged `is_emerging = True` when $Z \ge 1.75$, percentage growth $\ge 30\%$, and trailing 72-hour volume $\ge 12$ deduplicated records.

### 5.2 Event Emerging Themes (Log-Odds Lift)
Inside Event Intelligence (`/events`), term lift compares smoothed keyword prevalence during the event window against the pre-event baseline window:

$$\text{Lift}(w) = \frac{(c_{\text{during}}(w) + 1) / (N_{\text{during}} + 10)}{(c_{\text{before}}(w) + 1) / (N_{\text{before}} + 10)}$$

---

## 6. Human-in-the-Loop Override Precedence

Whenever an analyst applies an override (`POST /api/v1/records/{id}/override`), original model predictions (`predicted_topic`, `predicted_sentiment`) remain preserved in PostgreSQL while `effective_topic` and `effective_sentiment` resolve to the analyst's verified correction across all dashboards, event comparisons, CSV exports, and reports. Every override requires a written justification and creates an immutable `audit_logs` entry.
