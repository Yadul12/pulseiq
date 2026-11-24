"""Event Intelligence Service: Before / During / After quantitative & evidence analysis."""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from datetime import timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import (
    DataSource,
    Event,
    ProcessedRecord,
    RawRecord,
    SentimentClassification,
    TopicClassification,
)


def _effective_sentiment(sc: SentimentClassification) -> str:
    return sc.overridden_sentiment if (sc.is_overridden and sc.overridden_sentiment) else sc.predicted_sentiment


def _effective_topic(tc: TopicClassification) -> str:
    return tc.overridden_topic if (tc.is_overridden and tc.overridden_topic) else tc.predicted_topic


def analyze_event(db: Session, event: Event) -> dict[str, Any]:
    """Compute before/during/after volume shifts, sentiment shifts, emerging themes, and source evidence."""
    start = event.start_time if event.start_time.tzinfo else event.start_time.replace(tzinfo=timezone.utc)
    end = event.end_time if event.end_time.tzinfo else event.end_time.replace(tzinfo=timezone.utc)
    baseline_days = max(1, event.baseline_days or 7)
    before_start = start - timedelta(days=baseline_days)
    after_end = end + timedelta(days=baseline_days)

    stmt = (
        select(
            ProcessedRecord.id,
            ProcessedRecord.normalized_text,
            ProcessedRecord.extracted_keywords,
            ProcessedRecord.detected_language,
            RawRecord.published_at,
            RawRecord.original_title,
            RawRecord.original_text,
            RawRecord.is_synthetic,
            RawRecord.provenance_label,
            DataSource.name.label("source_name"),
            TopicClassification.predicted_topic,
            TopicClassification.overridden_topic,
            TopicClassification.is_overridden.label("topic_overridden"),
            TopicClassification.monitoring_topic_id,
            TopicClassification.confidence.label("topic_confidence"),
            SentimentClassification.predicted_sentiment,
            SentimentClassification.overridden_sentiment,
            SentimentClassification.is_overridden.label("sent_overridden"),
            SentimentClassification.sentiment_score,
            SentimentClassification.confidence.label("sent_confidence"),
        )
        .join(RawRecord, RawRecord.id == ProcessedRecord.raw_record_id)
        .join(DataSource, DataSource.id == RawRecord.source_id)
        .join(TopicClassification, TopicClassification.processed_record_id == ProcessedRecord.id)
        .join(SentimentClassification, SentimentClassification.processed_record_id == ProcessedRecord.id)
        .where(
            ProcessedRecord.is_duplicate.is_(False),
            RawRecord.published_at >= before_start,
            RawRecord.published_at <= after_end,
        )
    )

    if event.monitoring_topic_ids:
        stmt = stmt.where(TopicClassification.monitoring_topic_id.in_(event.monitoring_topic_ids))

    rows = db.execute(stmt).all()
    event_kws = [k.lower() for k in (event.keywords or []) if k]

    # Separate into before, during, after
    phases: dict[str, list[Any]] = {"before": [], "during": [], "after": []}
    daily_buckets: dict[str, dict[str, Any]] = {}

    for r in rows:
        pub = r.published_at if r.published_at.tzinfo else r.published_at.replace(tzinfo=timezone.utc)
        if pub < start:
            phase = "before"
        elif pub <= end:
            phase = "during"
        else:
            phase = "after"

        phases[phase].append(r)
        day_key = pub.strftime("%Y-%m-%d")
        if day_key not in daily_buckets:
            daily_buckets[day_key] = {
                "date": day_key,
                "phase": phase,
                "volume": 0,
                "positive": 0,
                "neutral": 0,
                "mixed": 0,
                "negative": 0,
                "sentiment_sum": 0.0,
            }
        sent = r.overridden_sentiment if (r.sent_overridden and r.overridden_sentiment) else r.predicted_sentiment
        daily_buckets[day_key]["volume"] += 1
        daily_buckets[day_key][sent] = daily_buckets[day_key].get(sent, 0) + 1
        daily_buckets[day_key]["sentiment_sum"] += float(r.sentiment_score)

    event_days = max(1.0, (end - start).total_seconds() / 86400.0)

    def _summarize(bucket: list[Any], duration_days: float) -> dict[str, Any]:
        cnt = len(bucket)
        s_counts = Counter()
        t_counts = Counter()
        kw_counts = Counter()
        s_sum = 0.0
        for r in bucket:
            sent = r.overridden_sentiment if (r.sent_overridden and r.overridden_sentiment) else r.predicted_sentiment
            top = r.overridden_topic if (r.topic_overridden and r.overridden_topic) else r.predicted_topic
            s_counts[sent] += 1
            t_counts[top] += 1
            s_sum += float(r.sentiment_score)
            for kw in (r.extracted_keywords or []):
                kw_counts[kw] += 1
        return {
            "count": cnt,
            "daily_rate": round(cnt / max(duration_days, 1.0), 1),
            "avg_sentiment": round(s_sum / cnt, 4) if cnt else 0.0,
            "sentiment_breakdown": {
                "positive": s_counts.get("positive", 0),
                "neutral": s_counts.get("neutral", 0),
                "mixed": s_counts.get("mixed", 0),
                "negative": s_counts.get("negative", 0),
            },
            "topic_counts": dict(t_counts),
            "keyword_counts": kw_counts,
        }

    before_s = _summarize(phases["before"], baseline_days)
    during_s = _summarize(phases["during"], event_days)
    after_s = _summarize(phases["after"], baseline_days)

    volume_change_pct = (
        round(((during_s["daily_rate"] - before_s["daily_rate"]) / max(before_s["daily_rate"], 0.1)) * 100.0, 1)
        if (before_s["daily_rate"] > 0 or during_s["daily_rate"] > 0)
        else 0.0
    )
    sentiment_delta = round(during_s["avg_sentiment"] - before_s["avg_sentiment"], 4)

    # Topic volume changes (before daily rate vs during daily rate)
    all_topics = sorted(set(before_s["topic_counts"].keys()) | set(during_s["topic_counts"].keys()))
    topic_changes = []
    for t in all_topics:
        b_rate = round(before_s["topic_counts"].get(t, 0) / baseline_days, 1)
        d_rate = round(during_s["topic_counts"].get(t, 0) / event_days, 1)
        a_rate = round(after_s["topic_counts"].get(t, 0) / baseline_days, 1)
        delta_pct = round(((d_rate - b_rate) / max(b_rate, 0.1)) * 100.0, 1)
        topic_changes.append(
            {
                "topic": t,
                "before_daily_rate": b_rate,
                "during_daily_rate": d_rate,
                "after_daily_rate": a_rate,
                "change_pct": delta_pct,
            }
        )
    topic_changes.sort(key=lambda x: x["during_daily_rate"], reverse=True)

    # Emerging themes: keyword lift during event vs before baseline (smoothed log-odds)
    b_total = max(before_s["count"], 1)
    d_total = max(during_s["count"], 1)
    emerging_themes = []
    for kw, d_cnt in during_s["keyword_counts"].most_common(60):
        if d_cnt < 3:
            continue
        b_cnt = before_s["keyword_counts"].get(kw, 0)
        p_during = (d_cnt + 1.0) / (d_total + 10.0)
        p_before = (b_cnt + 1.0) / (b_total + 10.0)
        lift = round(p_during / p_before, 2)
        if lift >= 1.15:
            emerging_themes.append(
                {
                    "term": kw,
                    "during_count": d_cnt,
                    "before_count": b_cnt,
                    "lift_ratio": lift,
                }
            )
    emerging_themes.sort(key=lambda x: (x["lift_ratio"] * math.log1p(x["during_count"])), reverse=True)

    # Representative evidence inside the event window (prioritizing event keyword matches)
    def _relevance(r: Any) -> float:
        txt_l = (r.normalized_text or "").lower()
        kw_score = sum(2.0 for k in event_kws if k in txt_l)
        return kw_score + float(r.sent_confidence)

    ranked_during = sorted(phases["during"], key=_relevance, reverse=True)[:12]
    evidence = [
        {
            "processed_record_id": r.id,
            "published_at": r.published_at.isoformat(),
            "source_name": r.source_name,
            "is_synthetic": r.is_synthetic,
            "provenance_label": r.provenance_label,
            "title": r.original_title,
            "original_text": r.original_text,
            "topic": r.overridden_topic if (r.topic_overridden and r.overridden_topic) else r.predicted_topic,
            "sentiment": r.overridden_sentiment if (r.sent_overridden and r.overridden_sentiment) else r.predicted_sentiment,
            "sentiment_confidence": r.sent_confidence,
            "language": r.detected_language,
        }
        for r in ranked_during
    ]

    timeline = []
    for dk in sorted(daily_buckets.keys()):
        b = daily_buckets[dk]
        vol = b["volume"]
        timeline.append(
            {
                "date": b["date"],
                "phase": b["phase"],
                "volume": vol,
                "positive": b["positive"],
                "neutral": b["neutral"],
                "mixed": b["mixed"],
                "negative": b["negative"],
                "avg_sentiment": round(b["sentiment_sum"] / vol, 3) if vol else 0.0,
            }
        )

    return {
        "event": {
            "id": event.id,
            "title": event.title,
            "description": event.description,
            "event_type": event.event_type,
            "location": event.location,
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
            "baseline_days": baseline_days,
            "monitoring_topic_ids": event.monitoring_topic_ids,
            "keywords": event.keywords,
            "status": event.status,
        },
        "comparison": {
            "before": {k: v for k, v in before_s.items() if k != "keyword_counts"},
            "during": {k: v for k, v in during_s.items() if k != "keyword_counts"},
            "after": {k: v for k, v in after_s.items() if k != "keyword_counts"},
            "volume_change_pct": volume_change_pct,
            "sentiment_delta": sentiment_delta,
        },
        "topic_changes": topic_changes,
        "emerging_themes": emerging_themes[:10],
        "timeline": timeline,
        "representative_evidence": evidence,
        "analytical_disclaimer": (
            "Before-and-after metrics measure observable discussion volume and classifier-estimated tone across configured "
            "public and synthetic sources; they indicate agenda salience rather than probability-sampled public opinion."
        ),
    }
