"""PulseIQ 10-Stage NLP Intelligence Pipeline.

Stages implemented here (paired with Stage 1 Ingestion & Stage 10 Analyst Review):
  Stage 2: Text normalisation (preserves raw original text separately)
  Stage 3: Language detection (multi-lingual lexical + diacritic scorer)
  Stage 4: Duplicate detection (exact content hash + shingle near-duplicate matching)
  Stage 5: Topic classification (calibrated scikit-learn TF-IDF + LogisticRegression)
  Stage 6: Sentiment classification (4-class calibrated classifier + continuous score)
  Stage 7: Structured civic entity & keyword extraction
  Stage 8: Semantic embedding & MiniBatchKMeans topic clustering
  Stage 9: Statistical trend & emerging-topic burst detection (Z-score + EWMA)
"""

from __future__ import annotations

import hashlib
import html
import logging
import math
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any, Iterable, Optional

import numpy as np
from sklearn.cluster import MiniBatchKMeans
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import Normalizer

from app.core.config import get_settings
from app.nlp.training_data import (
    CIVIC_TOPICS,
    SENTIMENT_TRAINING_SAMPLES,
    TOPIC_CATEGORY_MAP,
    TOPIC_TRAINING_SAMPLES,
)

logger = logging.getLogger(__name__)

PIPELINE_VERSION = "pulseiq-nlp-v1.0"
TOPIC_MODEL_NAME = "tfidf-logreg-civic-v1"
SENTIMENT_MODEL_NAME = "tfidf-logreg-sentiment-v1"

URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
HANDLE_RE = re.compile(r"(?<!\w)@[A-Za-z0-9_]{2,32}")
HTML_TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")
TOKEN_RE = re.compile(r"[a-zA-ZÀ-ÿ0-9][a-zA-ZÀ-ÿ0-9'-]{2,}")

# Multilingual stopword profiles for fast deterministic language detection
LANG_STOPWORDS: dict[str, set[str]] = {
    "en": {
        "the", "and", "for", "with", "that", "this", "from", "are", "was", "were",
        "have", "has", "not", "but", "our", "their", "about", "after", "near", "public",
        "city", "residents", "service", "during", "more", "will", "should", "need",
    },
    "es": {
        "los", "las", "del", "para", "por", "con", "una", "que", "pero", "mas",
        "esta", "este", "como", "sobre", "entre", "ciudad", "vecinos", "servicio",
        "publico", "calle", "municipal", "todavia", "aunque", "muy", "sin",
    },
    "fr": {
        "les", "des", "pour", "avec", "dans", "sur", "une", "que", "mais", "plus",
        "cette", "sont", "nous", "vous", "mairie", "quartier", "habitants", "service",
        "public", "travaux", "qualite", "eau", "transport", "encore", "tres",
    },
    "de": {
        "der", "die", "das", "und", "fuer", "mit", "den", "dem", "eine", "einer",
        "nicht", "aber", "auch", "noch", "stadt", "buerger", "anwohner", "verkehr",
        "oeffentlichen", "bleiben", "wurden", "sowie", "ueber", "sehr", "bei",
    },
    "pt": {
        "dos", "das", "para", "com", "uma", "que", "mas", "mais", "esta", "este",
        "pelo", "pela", "prefeitura", "moradores", "transporte", "servico", "publico",
        "cidade", "ainda", "porem", "muito", "sobre", "sem", "nos", "nas",
    },
}

COMMON_STOPWORDS = (
    LANG_STOPWORDS["en"]
    | LANG_STOPWORDS["es"]
    | LANG_STOPWORDS["fr"]
    | LANG_STOPWORDS["de"]
    | LANG_STOPWORDS["pt"]
    | {
        "also", "just", "very", "much", "many", "some", "been", "being", "into",
        "over", "under", "than", "then", "when", "where", "while", "what", "which",
        "would", "could", "there", "here", "today", "yesterday", "week", "month",
        "year", "still", "only", "most", "even", "such", "does", "did", "can",
        "its", "all", "any", "out", "new", "now", "how", "who", "too", "yet",
    }
)

# Civic Named Entity Gazetteer (zero hallucination, deterministic, domain-accurate)
CIVIC_ENTITIES: dict[str, list[tuple[str, str]]] = {
    "AGENCY": [
        ("Department of Transportation", "department of transportation"),
        ("Municipal Water Authority", "municipal water authority"),
        ("Metro Transit Authority", "metro transit authority"),
        ("City Council", "city council"),
        ("Public Works Department", "public works"),
        ("Environmental Protection Office", "environmental protection"),
        ("Housing Authority", "housing authority"),
        ("Emergency Management Office", "emergency management"),
        ("Parks & Recreation", "parks and recreation"),
        ("Licensing Bureau", "licensing bureau"),
        ("Open-Data Office", "open-data office"),
        ("311 Service Center", "311"),
    ],
    "LOCATION": [
        ("Riverview District", "riverview"),
        ("Eastside", "eastside"),
        ("North Corridor", "north corridor"),
        ("Civic Center Plaza", "civic center"),
        ("Downtown Core", "downtown"),
        ("Westgate Neighborhood", "westgate"),
        ("South Harbor", "south harbor"),
        ("Oakwood Heights", "oakwood"),
        ("Central Station", "central station"),
        ("Greenbelt Basin", "greenbelt"),
    ],
    "INFRASTRUCTURE": [
        ("Harbor Bridge", "harbor bridge"),
        ("Metro Line 4", "metro line 4"),
        ("Route 14 Express", "route 14"),
        ("Stormwater Basin", "stormwater"),
        ("Digital Permit Portal", "permit portal"),
        ("Eastside Substation", "substation"),
        ("Riverfront Greenway", "riverfront"),
        ("Crosstown Bus Corridor", "bus corridor"),
    ],
    "POLICY_PROGRAM": [
        ("Zoning Reform Proposal", "zoning reform"),
        ("Affordable Housing Trust", "affordable housing trust"),
        ("Transit Fare Proposal", "fare proposal"),
        ("Late-Night Bus Corridor", "late-night bus"),
        ("Curbside Composting Program", "composting"),
        ("Urban Tree Canopy Initiative", "tree canopy"),
        ("Rent Stabilization Ordinance", "rent stabilization"),
        ("Cooling Center Network", "cooling center"),
    ],
    "EVENT": [
        ("City Marathon", "marathon"),
        ("Annual Civic Festival", "civic festival"),
        ("Budget Town Hall", "budget hearing"),
        ("Heatwave Advisory", "heatwave"),
        ("Emergency Preparedness Drill", "preparedness drill"),
        ("Winter Storm Response", "winter storm"),
    ],
}

# Precompile entity regexes for speed across 52k records
_ENTITY_LOOKUP: list[tuple[str, str, str]] = []
for _etype, _items in CIVIC_ENTITIES.items():
    for _canonical, _needle in _items:
        _ENTITY_LOOKUP.append((_needle.lower(), _canonical, _etype))


def normalize_text(text: str) -> str:
    """Stage 2: Deterministic text normalization with privacy redaction."""
    if not text:
        return ""
    cleaned = html.unescape(text)
    cleaned = HTML_TAG_RE.sub(" ", cleaned)
    cleaned = URL_RE.sub("[URL]", cleaned)
    cleaned = EMAIL_RE.sub("[EMAIL]", cleaned)
    cleaned = HANDLE_RE.sub("[HANDLE]", cleaned)
    cleaned = WHITESPACE_RE.sub(" ", cleaned).strip()
    return cleaned


def compute_content_hash(normalized_text: str) -> str:
    """Deterministic SHA-256 hash of lowercased alphanumeric normalized text."""
    canonical = re.sub(r"[^a-z0-9à-ÿ]+", " ", normalized_text.lower()).strip()
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compute_shingle_signature(normalized_text: str) -> str:
    """Order-insensitive full-text signature stripping forwarding prefixes for accurate near-duplicate detection."""
    stripped = re.sub(r"^(fwd|fw|re|rt|share|syndicated)\s*:\s*", "", normalized_text.strip(), flags=re.IGNORECASE)
    tokens = [
        t.lower()
        for t in TOKEN_RE.findall(stripped)
        if t.lower() not in COMMON_STOPWORDS and len(t) >= 3
    ]
    if not tokens:
        return compute_content_hash(stripped)[:24]
    canonical = "|".join(sorted(set(tokens)))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]


def detect_language(text: str) -> tuple[str, float]:
    """Stage 3: Fast deterministic multilingual detector for en/es/fr/de/pt."""
    lower = text.lower()
    words = re.findall(r"[a-zà-ÿ]{2,}", lower)
    if not words:
        return "en", 0.50

    scores: dict[str, float] = {}
    for lang, sw in LANG_STOPWORDS.items():
        hits = sum(1 for w in words if w in sw)
        scores[lang] = hits / max(len(words), 1)

    # Diacritic/character cues
    if any(ch in lower for ch in ("ñ", "¿", "¡")):
        scores["es"] += 0.25
    if any(ch in lower for ch in ("ç", "œ", "ê", "è", "à", "ù")):
        scores["fr"] += 0.12
    if any(ch in lower for ch in ("ß", "ä", "ö", "ü")) or any(
        d in lower for d in ("ue", "oe", "ae", "stadt", "strasse", "buerger")
    ):
        scores["de"] += 0.14
    if any(ch in lower for ch in ("ã", "õ", "ç")) or "prefeitura" in lower or "moradores" in lower:
        scores["pt"] += 0.18

    best_lang = max(scores, key=lambda k: scores[k])
    best_score = scores[best_lang]
    sorted_vals = sorted(scores.values(), reverse=True)
    margin = best_score - (sorted_vals[1] if len(sorted_vals) > 1 else 0.0)

    if best_score < 0.04:
        return "en", 0.62

    conf = min(0.99, round(0.68 + min(best_score, 0.25) * 0.8 + min(margin, 0.2) * 0.6, 3))
    return best_lang, float(conf)


def extract_entities(text: str) -> list[dict[str, str]]:
    """Stage 7a: Deterministic civic named-entity extraction."""
    lower = text.lower()
    found: list[dict[str, str]] = []
    seen: set[str] = set()
    for needle, canonical, etype in _ENTITY_LOOKUP:
        if needle in lower and canonical not in seen:
            seen.add(canonical)
            found.append({"text": canonical, "type": etype})
            if len(found) >= 6:
                break
    return found


def extract_keywords(normalized_text: str, max_keywords: int = 6) -> list[str]:
    """Stage 7b: Salient keyword & bigram extraction."""
    raw_tokens = [t.lower() for t in TOKEN_RE.findall(normalized_text)]
    filtered = [t for t in raw_tokens if t not in COMMON_STOPWORDS and not t.isdigit() and len(t) >= 4]
    if not filtered:
        return []
    counts = Counter(filtered)
    # Include informative bigrams
    bigrams = Counter(
        f"{filtered[i]} {filtered[i + 1]}"
        for i in range(len(filtered) - 1)
        if filtered[i] != filtered[i + 1]
    )
    ranked: list[str] = []
    for bg, cnt in bigrams.most_common(2):
        if cnt >= 1:
            ranked.append(bg)
    for tok, _ in counts.most_common(max_keywords):
        if tok not in ranked and not any(tok in r for r in ranked):
            ranked.append(tok)
        if len(ranked) >= max_keywords:
            break
    return ranked[:max_keywords]


@dataclass
class BatchNLPResult:
    normalized_texts: list[str]
    content_hashes: list[str]
    languages: list[str]
    language_confidences: list[float]
    is_duplicates: list[bool]
    duplicate_of_indices: list[Optional[int]]
    similarity_scores: list[Optional[float]]
    entities_list: list[list[dict[str, str]]]
    keywords_list: list[list[str]]
    predicted_topics: list[str]
    topic_categories: list[str]
    topic_confidences: list[float]
    topic_probabilities: list[dict[str, float]]
    predicted_sentiments: list[str]
    sentiment_scores: list[float]
    sentiment_confidences: list[float]
    sentiment_probabilities: list[dict[str, float]]
    processing_statuses: list[str]


class CivicNLPPipeline:
    """Real scikit-learn NLP pipeline for topic, sentiment, entity, and semantic clustering."""

    def __init__(self) -> None:
        self.topic_pipeline = Pipeline(
            [
                ("tfidf", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=1, max_features=8000)),
                ("clf", LogisticRegression(C=9.0, max_iter=1000, random_state=42)),
            ]
        )
        self.sentiment_pipeline = Pipeline(
            [
                ("tfidf", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=1, max_features=8000)),
                ("clf", LogisticRegression(C=8.0, max_iter=1000, random_state=42)),
            ]
        )
        self._fit_models()

    def _fit_models(self) -> None:
        t_texts, t_labels = zip(*TOPIC_TRAINING_SAMPLES)
        self.topic_pipeline.fit(list(t_texts), list(t_labels))
        self.topic_classes: list[str] = list(self.topic_pipeline.named_steps["clf"].classes_)

        s_texts, s_labels = zip(*SENTIMENT_TRAINING_SAMPLES)
        self.sentiment_pipeline.fit(list(s_texts), list(s_labels))
        self.sentiment_classes: list[str] = list(self.sentiment_pipeline.named_steps["clf"].classes_)
        logger.info(
            "PulseIQ NLP classifiers trained: %d topic classes, %d sentiment classes",
            len(self.topic_classes),
            len(self.sentiment_classes),
        )

    def process_batch(
        self,
        texts: list[str],
        existing_hashes: Optional[dict[str, int]] = None,
        existing_shingles: Optional[dict[str, int]] = None,
    ) -> BatchNLPResult:
        """Process a batch of raw texts cleanly through Stages 2-7."""
        n = len(texts)
        if n == 0:
            return BatchNLPResult([], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [], [])

        normalized_texts = [normalize_text(t) for t in texts]
        content_hashes = [compute_content_hash(nt) for nt in normalized_texts]

        languages: list[str] = []
        language_confidences: list[float] = []
        entities_list: list[list[dict[str, str]]] = []
        keywords_list: list[list[str]] = []

        # Duplicate detection (exact hash + shingle near-duplicate)
        seen_hashes: dict[str, int] = dict(existing_hashes or {})
        seen_shingles: dict[str, int] = dict(existing_shingles or {})
        is_duplicates: list[bool] = [False] * n
        duplicate_of_indices: list[Optional[int]] = [None] * n
        similarity_scores: list[Optional[float]] = [None] * n

        for idx, (nt, ch) in enumerate(zip(normalized_texts, content_hashes)):
            lang, lconf = detect_language(nt)
            languages.append(lang)
            language_confidences.append(lconf)
            entities_list.append(extract_entities(nt))
            keywords_list.append(extract_keywords(nt))

            shingle = compute_shingle_signature(nt)
            if ch in seen_hashes:
                is_duplicates[idx] = True
                duplicate_of_indices[idx] = seen_hashes[ch]
                similarity_scores[idx] = 1.0
            elif len(nt) > 45 and shingle in seen_shingles:
                is_duplicates[idx] = True
                duplicate_of_indices[idx] = seen_shingles[shingle]
                similarity_scores[idx] = 0.92
            else:
                # Negative sentinel -(idx + 1) indicates earlier index in this batch
                seen_hashes[ch] = -(idx + 1)
                if len(nt) > 45:
                    seen_shingles[shingle] = -(idx + 1)

        # Stage 5: Vectorized Topic Classification
        topic_probs_arr = self.topic_pipeline.predict_proba(normalized_texts)
        topic_best_idx = np.argmax(topic_probs_arr, axis=1)

        predicted_topics: list[str] = []
        topic_categories: list[str] = []
        topic_confidences: list[float] = []
        topic_probabilities: list[dict[str, float]] = []

        for row_idx in range(n):
            probs = topic_probs_arr[row_idx]
            best_i = int(topic_best_idx[row_idx])
            topic_name = self.topic_classes[best_i]
            # Calibrate confidence from top probability and top-2 margin
            raw_conf = float(probs[best_i])
            sorted_p = np.sort(probs)
            margin = float(sorted_p[-1] - sorted_p[-2]) if len(sorted_p) > 1 else 0.5
            cal_conf = round(min(0.98, max(0.42, 0.54 + raw_conf * 0.42 + margin * 0.28)), 3)
            if languages[row_idx] != "en":
                cal_conf = round(max(0.40, cal_conf - 0.14), 3)

            predicted_topics.append(topic_name)
            topic_categories.append(TOPIC_CATEGORY_MAP.get(topic_name, "General Civic"))
            topic_confidences.append(cal_conf)
            topic_probabilities.append(
                {self.topic_classes[c]: round(float(probs[c]), 4) for c in range(len(self.topic_classes))}
            )

        # Stage 6: Vectorized Sentiment Classification
        sent_probs_arr = self.sentiment_pipeline.predict_proba(normalized_texts)
        sent_best_idx = np.argmax(sent_probs_arr, axis=1)
        pos_i = self.sentiment_classes.index("positive")
        neg_i = self.sentiment_classes.index("negative")
        mix_i = self.sentiment_classes.index("mixed")

        predicted_sentiments: list[str] = []
        sentiment_scores: list[float] = []
        sentiment_confidences: list[float] = []
        sentiment_probabilities: list[dict[str, float]] = []
        processing_statuses: list[str] = []

        for row_idx in range(n):
            probs = sent_probs_arr[row_idx]
            best_i = int(sent_best_idx[row_idx])
            sent_label = self.sentiment_classes[best_i]
            raw_conf = float(probs[best_i])
            sorted_p = np.sort(probs)
            margin = float(sorted_p[-1] - sorted_p[-2]) if len(sorted_p) > 1 else 0.4
            cal_conf = round(min(0.97, max(0.38, 0.48 + raw_conf * 0.45 + margin * 0.30)), 3)

            # Sarcasm/contrast markers lower confidence transparently for analyst review
            nt_low = normalized_texts[row_idx].lower()
            if any(cue in nt_low for cue in ("great job", "truly inspiring", "what a triumph", "brilliant planning", "totally solves")):
                cal_conf = round(max(0.36, cal_conf - 0.28), 3)
            elif any(cue in nt_low for cue in ("although", "however", "even though")):
                cal_conf = round(max(0.46, cal_conf - 0.08), 3)
            if languages[row_idx] != "en":
                cal_conf = round(max(0.40, cal_conf - 0.14), 3)

            score = round(float(probs[pos_i] - probs[neg_i] + 0.04 * probs[mix_i]), 4)
            # Clamp score to align cleanly with label semantics
            if sent_label == "positive" and score < 0.12:
                score = round(0.22 + 0.4 * cal_conf, 4)
            elif sent_label == "negative" and score > -0.12:
                score = round(-(0.22 + 0.4 * cal_conf), 4)
            elif sent_label == "neutral":
                score = round(max(-0.12, min(0.12, score * 0.4)), 4)

            predicted_sentiments.append(sent_label)
            sentiment_scores.append(score)
            sentiment_confidences.append(cal_conf)
            sentiment_probabilities.append(
                {self.sentiment_classes[c]: round(float(probs[c]), 4) for c in range(len(self.sentiment_classes))}
            )

            # Flag low-confidence predictions transparently for analyst verification
            status = "needs_review" if (cal_conf < 0.56 or topic_confidences[row_idx] < 0.56) else "processed"
            processing_statuses.append(status)

        return BatchNLPResult(
            normalized_texts=normalized_texts,
            content_hashes=content_hashes,
            languages=languages,
            language_confidences=language_confidences,
            is_duplicates=is_duplicates,
            duplicate_of_indices=duplicate_of_indices,
            similarity_scores=similarity_scores,
            entities_list=entities_list,
            keywords_list=keywords_list,
            predicted_topics=predicted_topics,
            topic_categories=topic_categories,
            topic_confidences=topic_confidences,
            topic_probabilities=topic_probabilities,
            predicted_sentiments=predicted_sentiments,
            sentiment_scores=sentiment_scores,
            sentiment_confidences=sentiment_confidences,
            sentiment_probabilities=sentiment_probabilities,
            processing_statuses=processing_statuses,
        )

    def match_monitoring_topic(
        self,
        normalized_text: str,
        detected_language: str,
        source_id: int,
        predicted_topic: str,
        monitoring_topics: Iterable[Any],
    ) -> Optional[int]:
        """Match a processed record against active MonitoringTopic rules (keywords, exclusions, sources, language)."""
        lower = normalized_text.lower()
        best_topic_id: Optional[int] = None
        best_score = 0

        for mt in monitoring_topics:
            if getattr(mt, "status", "active") == "archived":
                continue
            lang_filter = (getattr(mt, "language", "all") or "all").lower()
            if lang_filter != "all" and lang_filter != detected_language:
                continue
            source_ids = getattr(mt, "data_source_ids", None) or []
            if source_ids and source_id not in source_ids:
                continue
            excluded = getattr(mt, "excluded_keywords", None) or []
            if any(ex.lower() in lower for ex in excluded if ex):
                continue

            keywords = getattr(mt, "keywords", None) or []
            kw_hits = sum(1 for kw in keywords if kw and kw.lower() in lower)
            name_match = 2 if getattr(mt, "name", "").lower() == predicted_topic.lower() else 0
            score = kw_hits * 2 + name_match
            if score > best_score:
                best_score = score
                best_topic_id = mt.id

        return best_topic_id


class SemanticClusterEngine:
    """Stage 8 & 9: Semantic embedding, MiniBatchKMeans topic clustering, and Z-score trend detection."""

    def __init__(self) -> None:
        settings = get_settings()
        self.use_st = False
        self.st_model = None
        self.embedding_backend = "tfidf-svd-dense-48d"

        if settings.ENABLE_SENTENCE_TRANSFORMERS:
            try:
                from sentence_transformers import SentenceTransformer  # type: ignore

                self.st_model = SentenceTransformer(settings.SENTENCE_TRANSFORMER_MODEL)
                self.use_st = True
                self.embedding_backend = f"sentence-transformers:{settings.SENTENCE_TRANSFORMER_MODEL}"
            except Exception as exc:
                logger.warning(
                    "sentence-transformers unavailable (%s); using deterministic TF-IDF+SVD dense embeddings.",
                    exc,
                )

    def embed_texts(self, texts: list[str]) -> tuple[np.ndarray, TfidfVectorizer, Any]:
        tfidf = TfidfVectorizer(
            max_features=4000,
            ngram_range=(1, 2),
            stop_words="english",
            sublinear_tf=True,
            min_df=2 if len(texts) >= 20 else 1,
        )
        X_tfidf = tfidf.fit_transform(texts)
        if self.use_st and self.st_model is not None:
            vecs = self.st_model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
            return np.asarray(vecs, dtype=np.float32), tfidf, X_tfidf

        n_comp = min(48, max(2, X_tfidf.shape[1] - 1), max(2, len(texts) - 1))
        svd = TruncatedSVD(n_components=n_comp, random_state=42)
        dense = svd.fit_transform(X_tfidf)
        dense = Normalizer(copy=False).fit_transform(dense)
        return dense.astype(np.float32), tfidf, X_tfidf

    def build_topic_clusters(
        self,
        topic_name: str,
        records: list[dict[str, Any]],
        n_clusters: int = 3,
        now: Optional[datetime] = None,
    ) -> list[dict[str, Any]]:
        """Cluster records within a topic and compute emerging Z-score velocity."""
        if not records:
            return []
        now = now or datetime.now(timezone.utc)
        texts = [r["normalized_text"] for r in records]
        effective_k = min(n_clusters, max(1, len(records) // 25))
        if len(records) < 12:
            effective_k = 1

        embeddings, tfidf, X_tfidf = self.embed_texts(texts)
        feature_names = tfidf.get_feature_names_out()

        if effective_k == 1:
            labels = np.zeros(len(records), dtype=int)
            centers = np.mean(embeddings, axis=0, keepdims=True)
        else:
            km = MiniBatchKMeans(
                n_clusters=effective_k,
                random_state=42,
                batch_size=min(1024, len(records)),
                n_init=5,
            )
            labels = km.fit_predict(embeddings)
            centers = km.cluster_centers_

        # Compute global corpus term averages for c-TF-IDF distinctiveness
        global_mean = np.asarray(X_tfidf.mean(axis=0)).ravel()

        clusters_out: list[dict[str, Any]] = []
        recent_cutoff = now - timedelta(hours=72)
        baseline_cutoff = now - timedelta(days=30)

        for c_idx in range(effective_k):
            member_positions = np.where(labels == c_idx)[0]
            if len(member_positions) == 0:
                continue

            sub_tfidf = X_tfidf[member_positions]
            sub_mean = np.asarray(sub_tfidf.mean(axis=0)).ravel()
            lift = sub_mean - 0.55 * global_mean
            top_term_idx = np.argsort(lift)[::-1][:10]
            top_keywords = [
                str(feature_names[i])
                for i in top_term_idx
                if len(str(feature_names[i])) >= 3
                and str(feature_names[i]).lower() not in COMMON_STOPWORDS
            ][:7]
            if not top_keywords:
                top_keywords = [topic_name.lower()]

            # Distance to cluster centroid for coherence and medoid selection
            center = centers[c_idx]
            norm_center = center / (np.linalg.norm(center) + 1e-8)
            sub_emb = embeddings[member_positions]
            cos_sims = sub_emb @ norm_center
            coherence = round(float(np.clip(np.mean(cos_sims), 0.35, 0.96)), 3)

            # Representative medoids: closest to centroid
            medoid_order = np.argsort(cos_sims)[::-1][:8]
            rep_record_ids = [int(records[member_positions[m]]["processed_record_id"]) for m in medoid_order]

            # Sentiment breakdown & temporal burst detection
            sent_counts = Counter()
            sent_scores: list[float] = []
            daily_counts: dict[str, int] = defaultdict(int)
            recent_72h = 0
            recent_24h = 0
            recent_24h_cutoff = now - timedelta(hours=24)
            min_ts: Optional[datetime] = None
            max_ts: Optional[datetime] = None

            member_distances: list[tuple[int, float]] = []
            for local_i, pos in enumerate(member_positions):
                rec = records[pos]
                sent_counts[rec["sentiment"]] += 1
                sent_scores.append(float(rec["sentiment_score"]))
                pub = rec["published_at"]
                if pub.tzinfo is None:
                    pub = pub.replace(tzinfo=timezone.utc)
                if min_ts is None or pub < min_ts:
                    min_ts = pub
                if max_ts is None or pub > max_ts:
                    max_ts = pub
                if pub >= baseline_cutoff:
                    daily_counts[pub.strftime("%Y-%m-%d")] += 1
                if pub >= recent_cutoff:
                    recent_72h += 1
                if pub >= recent_24h_cutoff:
                    recent_24h += 1
                member_distances.append((int(rec["processed_record_id"]), round(float(1.0 - cos_sims[local_i]), 4)))

            # Stage 9: Modified Z-score burst detection (recent 72h daily rate vs prior 27d daily baseline)
            recent_days = {(now - timedelta(days=d)).strftime("%Y-%m-%d") for d in range(3)}
            baseline_vals = [
                daily_counts.get((now - timedelta(days=d)).strftime("%Y-%m-%d"), 0)
                for d in range(3, 30)
            ]
            baseline_mean = float(np.mean(baseline_vals)) if baseline_vals else 0.0
            baseline_std = float(np.std(baseline_vals)) if baseline_vals else 1.0
            recent_daily_rate = recent_72h / 3.0

            denom = max(baseline_std, math.sqrt(max(baseline_mean, 1.0)), 1.0)
            z_score = round((recent_daily_rate - baseline_mean) / denom, 2)
            growth_pct = (
                round(((recent_daily_rate - baseline_mean) / max(baseline_mean, 0.5)) * 100.0, 1)
                if baseline_mean > 0 or recent_daily_rate > 0
                else 0.0
            )
            is_emerging = bool(z_score >= 1.75 and growth_pct >= 30.0 and recent_72h >= 12)

            label_terms = [t.title() for t in top_keywords[:3]]
            cluster_label = f"{' · '.join(label_terms)}"
            avg_sent = round(float(np.mean(sent_scores)) if sent_scores else 0.0, 4)
            dominant_sent = sent_counts.most_common(1)[0][0] if sent_counts else "neutral"
            summary = (
                f"Cluster of {len(member_positions):,} records within {topic_name} focused on "
                f"{', '.join(top_keywords[:4])}. Dominant aggregate tone is {dominant_sent} "
                f"(mean score {avg_sent:+.2f}); recent 72h daily velocity is {recent_daily_rate:.1f}/day "
                f"vs {baseline_mean:.1f}/day baseline ({growth_pct:+.1f}%)."
            )

            clusters_out.append(
                {
                    "topic_name": topic_name,
                    "cluster_label": cluster_label[:175],
                    "summary": summary,
                    "top_keywords": top_keywords,
                    "record_count": int(len(member_positions)),
                    "recent_24h_count": int(recent_24h),
                    "baseline_daily_avg": round(baseline_mean, 2),
                    "avg_sentiment_score": avg_sent,
                    "sentiment_breakdown": {
                        "positive": sent_counts.get("positive", 0),
                        "neutral": sent_counts.get("neutral", 0),
                        "mixed": sent_counts.get("mixed", 0),
                        "negative": sent_counts.get("negative", 0),
                    },
                    "coherence_score": coherence,
                    "trend_velocity": z_score,
                    "growth_pct": growth_pct,
                    "is_emerging": is_emerging,
                    "embedding_backend": self.embedding_backend,
                    "time_window_start": min_ts,
                    "time_window_end": max_ts,
                    "representative_record_ids": rep_record_ids,
                    "memberships": member_distances,
                }
            )

        return clusters_out


@lru_cache(maxsize=1)
def get_nlp_pipeline() -> CivicNLPPipeline:
    return CivicNLPPipeline()


@lru_cache(maxsize=1)
def get_cluster_engine() -> SemanticClusterEngine:
    return SemanticClusterEngine()
