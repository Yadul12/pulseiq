"""Records Search, Pagination, Evidence Inspection, Analyst Annotations, Overrides, and CSV Export."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, record_audit_log, require_role
from app.models.models import (
    AnalystAnnotation,
    ClusterMembership,
    DataSource,
    ProcessedRecord,
    RawRecord,
    SentimentClassification,
    TopicClassification,
    User,
)
from app.schemas.schemas import AnnotationUpsertRequest, ClassificationOverrideRequest

router = APIRouter(prefix="/records", tags=["Records & Analyst Workspace"])


def _build_records_query(
    q: Optional[str],
    topic_id: Optional[int],
    topic_name: Optional[str],
    sentiment: Optional[str],
    source_id: Optional[int],
    language: Optional[str],
    status_filter: Optional[str],
    include_duplicates: bool,
    bookmarked: Optional[bool],
    verified: Optional[bool],
    overridden: Optional[bool],
    cluster_id: Optional[int],
    days: Optional[int],
    max_confidence: Optional[float],
    user_id: int,
):
    eff_sent = case(
        (
            SentimentClassification.is_overridden.is_(True),
            func.coalesce(SentimentClassification.overridden_sentiment, SentimentClassification.predicted_sentiment),
        ),
        else_=SentimentClassification.predicted_sentiment,
    )
    eff_topic = case(
        (
            TopicClassification.is_overridden.is_(True),
            func.coalesce(TopicClassification.overridden_topic, TopicClassification.predicted_topic),
        ),
        else_=TopicClassification.predicted_topic,
    )

    stmt = (
        select(
            ProcessedRecord,
            RawRecord,
            DataSource.name.label("source_name"),
            DataSource.provider_type.label("provider_type"),
            TopicClassification,
            SentimentClassification,
        )
        .join(RawRecord, RawRecord.id == ProcessedRecord.raw_record_id)
        .join(DataSource, DataSource.id == RawRecord.source_id)
        .join(TopicClassification, TopicClassification.processed_record_id == ProcessedRecord.id)
        .join(SentimentClassification, SentimentClassification.processed_record_id == ProcessedRecord.id)
    )

    if cluster_id is not None:
        stmt = stmt.join(ClusterMembership, ClusterMembership.processed_record_id == ProcessedRecord.id).where(
            ClusterMembership.cluster_id == cluster_id
        )

    if not include_duplicates:
        stmt = stmt.where(ProcessedRecord.is_duplicate.is_(False))

    if days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        stmt = stmt.where(RawRecord.published_at >= cutoff)

    if q and q.strip():
        pat = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                ProcessedRecord.normalized_text.ilike(pat),
                RawRecord.original_title.ilike(pat),
                RawRecord.external_id.ilike(pat),
            )
        )

    if topic_id is not None:
        stmt = stmt.where(TopicClassification.monitoring_topic_id == topic_id)
    if topic_name:
        stmt = stmt.where(eff_topic == topic_name)
    if sentiment and sentiment != "all":
        stmt = stmt.where(eff_sent == sentiment)
    if source_id is not None:
        stmt = stmt.where(RawRecord.source_id == source_id)
    if language and language != "all":
        stmt = stmt.where(ProcessedRecord.detected_language == language)
    if status_filter and status_filter != "all":
        stmt = stmt.where(ProcessedRecord.processing_status == status_filter)
    if max_confidence is not None:
        stmt = stmt.where(
            or_(
                SentimentClassification.confidence <= max_confidence,
                TopicClassification.confidence <= max_confidence,
            )
        )
    if overridden is True:
        stmt = stmt.where(
            or_(TopicClassification.is_overridden.is_(True), SentimentClassification.is_overridden.is_(True))
        )

    if bookmarked is True or verified is True:
        ann_sub = select(AnalystAnnotation.processed_record_id)
        if bookmarked is True:
            ann_sub = ann_sub.where(AnalystAnnotation.is_bookmarked.is_(True))
        if verified is True:
            ann_sub = ann_sub.where(AnalystAnnotation.is_verified.is_(True))
        stmt = stmt.where(ProcessedRecord.id.in_(ann_sub))

    return stmt


@router.get("")
def list_records(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=5, le=100),
    q: Optional[str] = Query(default=None),
    topic_id: Optional[int] = Query(default=None),
    topic_name: Optional[str] = Query(default=None),
    sentiment: Optional[str] = Query(default=None),
    source_id: Optional[int] = Query(default=None),
    language: Optional[str] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    include_duplicates: bool = Query(default=False),
    bookmarked: Optional[bool] = Query(default=None),
    verified: Optional[bool] = Query(default=None),
    overridden: Optional[bool] = Query(default=None),
    cluster_id: Optional[int] = Query(default=None),
    days: Optional[int] = Query(default=None, ge=1, le=365),
    max_confidence: Optional[float] = Query(default=None, ge=0.0, le=1.0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = _build_records_query(
        q=q,
        topic_id=topic_id,
        topic_name=topic_name,
        sentiment=sentiment,
        source_id=source_id,
        language=language,
        status_filter=status_filter,
        include_duplicates=include_duplicates,
        bookmarked=bookmarked,
        verified=verified,
        overridden=overridden,
        cluster_id=cluster_id,
        days=days,
        max_confidence=max_confidence,
        user_id=current_user.id,
    )

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(
        stmt.order_by(RawRecord.published_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()

    proc_ids = [r[0].id for r in rows]
    ann_map: dict[int, list[AnalystAnnotation]] = {}
    if proc_ids:
        anns = list(
            db.scalars(select(AnalystAnnotation).where(AnalystAnnotation.processed_record_id.in_(proc_ids))).all()
        )
        for a in anns:
            ann_map.setdefault(a.processed_record_id, []).append(a)

    items = []
    for proc, raw, source_name, provider_type, tcls, scls in rows:
        anns = ann_map.get(proc.id, [])
        my_ann = next((a for a in anns if a.analyst_id == current_user.id), None)
        any_verified = any(a.is_verified for a in anns)
        any_bookmarked = any(a.is_bookmarked for a in anns)
        items.append(
            {
                "id": proc.id,
                "raw_record_id": raw.id,
                "external_id": raw.external_id,
                "source_id": raw.source_id,
                "source_name": source_name,
                "provider_type": provider_type,
                "is_synthetic": raw.is_synthetic,
                "provenance_label": raw.provenance_label,
                "has_missing_fields": raw.has_missing_fields,
                "published_at": raw.published_at.isoformat(),
                "original_title": raw.original_title,
                "original_text": raw.original_text,
                "normalized_text": proc.normalized_text,
                "detected_language": proc.detected_language,
                "language_confidence": proc.language_confidence,
                "is_duplicate": proc.is_duplicate,
                "duplicate_of_id": proc.duplicate_of_id,
                "processing_status": proc.processing_status,
                "entities": proc.entities,
                "extracted_keywords": proc.extracted_keywords,
                "predicted_topic": tcls.predicted_topic,
                "effective_topic": tcls.effective_topic,
                "monitoring_topic_id": tcls.monitoring_topic_id,
                "topic_confidence": tcls.confidence,
                "topic_overridden": tcls.is_overridden,
                "predicted_sentiment": scls.predicted_sentiment,
                "effective_sentiment": scls.effective_sentiment,
                "sentiment_score": scls.sentiment_score,
                "sentiment_confidence": scls.confidence,
                "sentiment_overridden": scls.is_overridden,
                "is_bookmarked": any_bookmarked,
                "is_verified": any_verified,
                "analyst_note": my_ann.note if my_ann else (anns[0].note if anns else ""),
                "report_section_tag": my_ann.report_section_tag if my_ann else (anns[0].report_section_tag if anns else None),
            }
        )

    return {
        "total": int(total),
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (int(total) + page_size - 1) // page_size),
        "items": items,
    }


@router.get("/export.csv")
def export_records_csv(
    q: Optional[str] = Query(default=None),
    topic_id: Optional[int] = Query(default=None),
    sentiment: Optional[str] = Query(default=None),
    source_id: Optional[int] = Query(default=None),
    language: Optional[str] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    bookmarked: Optional[bool] = Query(default=None),
    verified: Optional[bool] = Query(default=None),
    overridden: Optional[bool] = Query(default=None),
    days: Optional[int] = Query(default=None),
    limit: int = Query(default=2000, ge=1, le=10000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = _build_records_query(
        q=q,
        topic_id=topic_id,
        topic_name=None,
        sentiment=sentiment,
        source_id=source_id,
        language=language,
        status_filter=status_filter,
        include_duplicates=False,
        bookmarked=bookmarked,
        verified=verified,
        overridden=overridden,
        cluster_id=None,
        days=days,
        max_confidence=None,
        user_id=current_user.id,
    )
    rows = db.execute(stmt.order_by(RawRecord.published_at.desc()).limit(limit)).all()
    proc_ids = [r[0].id for r in rows]
    ann_map: dict[int, AnalystAnnotation] = {}
    if proc_ids:
        for a in db.scalars(select(AnalystAnnotation).where(AnalystAnnotation.processed_record_id.in_(proc_ids))).all():
            ann_map[a.processed_record_id] = a

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "record_id",
            "external_id",
            "published_at",
            "source_name",
            "is_synthetic",
            "provenance_label",
            "language",
            "effective_topic",
            "predicted_topic",
            "topic_confidence",
            "topic_overridden",
            "effective_sentiment",
            "predicted_sentiment",
            "sentiment_score",
            "sentiment_confidence",
            "sentiment_overridden",
            "is_verified",
            "report_section_tag",
            "analyst_note",
            "original_text",
            "normalized_text",
        ]
    )
    for proc, raw, source_name, _pt, tcls, scls in rows:
        ann = ann_map.get(proc.id)
        writer.writerow(
            [
                f"REC-{proc.id}",
                raw.external_id,
                raw.published_at.isoformat(),
                source_name,
                raw.is_synthetic,
                raw.provenance_label,
                proc.detected_language,
                tcls.effective_topic,
                tcls.predicted_topic,
                tcls.confidence,
                tcls.is_overridden,
                scls.effective_sentiment,
                scls.predicted_sentiment,
                scls.sentiment_score,
                scls.confidence,
                scls.is_overridden,
                ann.is_verified if ann else False,
                ann.report_section_tag if ann else "",
                ann.note if ann else "",
                raw.original_text,
                proc.normalized_text,
            ]
        )

    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="pulseiq_evidence_export.csv"'},
    )


@router.get("/{record_id}")
def get_record_detail(
    record_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = db.execute(
        select(ProcessedRecord, RawRecord, DataSource, TopicClassification, SentimentClassification)
        .join(RawRecord, RawRecord.id == ProcessedRecord.raw_record_id)
        .join(DataSource, DataSource.id == RawRecord.source_id)
        .join(TopicClassification, TopicClassification.processed_record_id == ProcessedRecord.id)
        .join(SentimentClassification, SentimentClassification.processed_record_id == ProcessedRecord.id)
        .where(ProcessedRecord.id == record_id)
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Record not found.")

    proc, raw, source, tcls, scls = row
    anns = list(
        db.scalars(
            select(AnalystAnnotation)
            .where(AnalystAnnotation.processed_record_id == proc.id)
            .order_by(AnalystAnnotation.updated_at.desc())
        ).all()
    )
    analyst_ids = {a.analyst_id for a in anns}
    if tcls.overridden_by:
        analyst_ids.add(tcls.overridden_by)
    if scls.overridden_by:
        analyst_ids.add(scls.overridden_by)
    users_map = {
        u.id: u.full_name for u in db.scalars(select(User).where(User.id.in_(analyst_ids))).all()
    } if analyst_ids else {}

    return {
        "id": proc.id,
        "raw": {
            "id": raw.id,
            "external_id": raw.external_id,
            "source_id": source.id,
            "source_name": source.name,
            "provider_type": source.provider_type,
            "source_url": raw.source_url,
            "author_handle_anonymized": raw.author_handle_anonymized,
            "original_title": raw.original_title,
            "original_text": raw.original_text,
            "raw_metadata": raw.raw_metadata,
            "published_at": raw.published_at.isoformat(),
            "ingested_at": raw.ingested_at.isoformat(),
            "content_hash": raw.content_hash,
            "is_synthetic": raw.is_synthetic,
            "provenance_label": raw.provenance_label,
            "has_missing_fields": raw.has_missing_fields,
        },
        "processed": {
            "normalized_text": proc.normalized_text,
            "detected_language": proc.detected_language,
            "language_confidence": proc.language_confidence,
            "is_duplicate": proc.is_duplicate,
            "duplicate_of_id": proc.duplicate_of_id,
            "similarity_score": proc.similarity_score,
            "entities": proc.entities,
            "extracted_keywords": proc.extracted_keywords,
            "processing_status": proc.processing_status,
            "processing_version": proc.processing_version,
            "processed_at": proc.processed_at.isoformat(),
        },
        "topic_classification": {
            "monitoring_topic_id": tcls.monitoring_topic_id,
            "predicted_topic": tcls.predicted_topic,
            "effective_topic": tcls.effective_topic,
            "topic_category": tcls.topic_category,
            "confidence": tcls.confidence,
            "class_probabilities": tcls.class_probabilities,
            "model_name": tcls.model_name,
            "model_version": tcls.model_version,
            "is_overridden": tcls.is_overridden,
            "overridden_topic": tcls.overridden_topic,
            "overridden_by_name": users_map.get(tcls.overridden_by) if tcls.overridden_by else None,
            "overridden_at": tcls.overridden_at.isoformat() if tcls.overridden_at else None,
            "override_reason": tcls.override_reason,
        },
        "sentiment_classification": {
            "predicted_sentiment": scls.predicted_sentiment,
            "effective_sentiment": scls.effective_sentiment,
            "sentiment_score": scls.sentiment_score,
            "confidence": scls.confidence,
            "class_probabilities": scls.class_probabilities,
            "model_name": scls.model_name,
            "model_version": scls.model_version,
            "is_overridden": scls.is_overridden,
            "overridden_sentiment": scls.overridden_sentiment,
            "overridden_by_name": users_map.get(scls.overridden_by) if scls.overridden_by else None,
            "overridden_at": scls.overridden_at.isoformat() if scls.overridden_at else None,
            "override_reason": scls.override_reason,
        },
        "annotations": [
            {
                "id": a.id,
                "analyst_id": a.analyst_id,
                "analyst_name": users_map.get(a.analyst_id, "Analyst"),
                "is_bookmarked": a.is_bookmarked,
                "is_verified": a.is_verified,
                "note": a.note,
                "tags": a.tags,
                "report_section_tag": a.report_section_tag,
                "updated_at": a.updated_at.isoformat(),
            }
            for a in anns
        ],
    }


@router.put("/{record_id}/annotation")
def upsert_annotation(
    record_id: int,
    payload: AnnotationUpsertRequest,
    request: Request,
    current_user: User = Depends(require_role("analyst")),
    db: Session = Depends(get_db),
):
    proc = db.get(ProcessedRecord, record_id)
    if not proc:
        raise HTTPException(status_code=404, detail="Processed record not found.")

    ann = db.scalar(
        select(AnalystAnnotation).where(
            AnalystAnnotation.processed_record_id == record_id,
            AnalystAnnotation.analyst_id == current_user.id,
        )
    )
    if not ann:
        ann = AnalystAnnotation(
            processed_record_id=record_id,
            analyst_id=current_user.id,
            is_bookmarked=bool(payload.is_bookmarked),
            is_verified=bool(payload.is_verified),
            note=payload.note or "",
            tags=payload.tags or [],
            report_section_tag=payload.report_section_tag,
        )
        db.add(ann)
    else:
        if payload.is_bookmarked is not None:
            ann.is_bookmarked = payload.is_bookmarked
        if payload.is_verified is not None:
            ann.is_verified = payload.is_verified
        if payload.note is not None:
            ann.note = payload.note
        if payload.tags is not None:
            ann.tags = payload.tags
        if payload.report_section_tag is not None:
            ann.report_section_tag = payload.report_section_tag or None

    if ann.is_verified and proc.processing_status == "needs_review":
        proc.processing_status = "processed"

    record_audit_log(
        db=db,
        action="analyst.annotation_updated",
        resource_type="processed_record",
        resource_id=str(record_id),
        details={
            "is_bookmarked": ann.is_bookmarked,
            "is_verified": ann.is_verified,
            "report_section_tag": ann.report_section_tag,
        },
        actor=current_user,
        request=request,
    )
    db.commit()
    db.refresh(ann)
    return {
        "id": ann.id,
        "processed_record_id": ann.processed_record_id,
        "is_bookmarked": ann.is_bookmarked,
        "is_verified": ann.is_verified,
        "note": ann.note,
        "tags": ann.tags,
        "report_section_tag": ann.report_section_tag,
        "updated_at": ann.updated_at.isoformat(),
    }


@router.post("/{record_id}/override")
def override_classification(
    record_id: int,
    payload: ClassificationOverrideRequest,
    request: Request,
    current_user: User = Depends(require_role("analyst")),
    db: Session = Depends(get_db),
):
    """Human-in-the-loop override of topic and/or sentiment with preserved original model prediction & audit log."""
    proc = db.get(ProcessedRecord, record_id)
    if not proc:
        raise HTTPException(status_code=404, detail="Processed record not found.")
    if not payload.overridden_topic and not payload.overridden_sentiment:
        raise HTTPException(status_code=400, detail="Provide overridden_topic and/or overridden_sentiment.")

    now = datetime.now(timezone.utc)
    changes: dict = {"reason": payload.override_reason}

    tcls = db.scalar(select(TopicClassification).where(TopicClassification.processed_record_id == record_id))
    if payload.overridden_topic and tcls:
        changes["topic_before"] = tcls.effective_topic
        changes["topic_after"] = payload.overridden_topic
        tcls.is_overridden = True
        tcls.overridden_topic = payload.overridden_topic.strip()
        tcls.overridden_by = current_user.id
        tcls.overridden_at = now
        tcls.override_reason = payload.override_reason

    scls = db.scalar(select(SentimentClassification).where(SentimentClassification.processed_record_id == record_id))
    if payload.overridden_sentiment and scls:
        changes["sentiment_before"] = scls.effective_sentiment
        changes["sentiment_after"] = payload.overridden_sentiment
        scls.is_overridden = True
        scls.overridden_sentiment = payload.overridden_sentiment
        scls.overridden_by = current_user.id
        scls.overridden_at = now
        scls.override_reason = payload.override_reason
        # Adjust effective numeric polarity cleanly to align with human correction
        score_map = {"positive": 0.72, "neutral": 0.0, "mixed": -0.08, "negative": -0.74}
        scls.sentiment_score = score_map[payload.overridden_sentiment]

    proc.processing_status = "processed"
    record_audit_log(
        db=db,
        action="classification.overridden",
        resource_type="processed_record",
        resource_id=str(record_id),
        details=changes,
        actor=current_user,
        request=request,
    )
    db.commit()
    return {
        "record_id": record_id,
        "effective_topic": tcls.effective_topic if tcls else None,
        "topic_overridden": tcls.is_overridden if tcls else False,
        "effective_sentiment": scls.effective_sentiment if scls else None,
        "sentiment_overridden": scls.is_overridden if scls else False,
        "override_reason": payload.override_reason,
        "overridden_at": now.isoformat(),
    }
