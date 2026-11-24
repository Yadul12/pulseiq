"""Evidence-Backed Insight Reports Generation, Hydration, Editing, and Export."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, record_audit_log, require_role
from app.models.models import (
    AnalystAnnotation,
    DataSource,
    ProcessedRecord,
    RawRecord,
    Report,
    SentimentClassification,
    TopicClassification,
    User,
)
from app.schemas.schemas import ReportGenerateRequest, ReportUpdateRequest
from app.services.report_service import generate_grounded_report

router = APIRouter(prefix="/reports", tags=["Insight Reports"])


def _hydrate_evidence(db: Session, record_ids: list[int]) -> list[dict]:
    if not record_ids:
        return []
    rows = db.execute(
        select(ProcessedRecord, RawRecord, DataSource.name, TopicClassification, SentimentClassification)
        .join(RawRecord, RawRecord.id == ProcessedRecord.raw_record_id)
        .join(DataSource, DataSource.id == RawRecord.source_id)
        .join(TopicClassification, TopicClassification.processed_record_id == ProcessedRecord.id)
        .join(SentimentClassification, SentimentClassification.processed_record_id == ProcessedRecord.id)
        .where(ProcessedRecord.id.in_(record_ids))
    ).all()
    ann_rows = list(
        db.scalars(select(AnalystAnnotation).where(AnalystAnnotation.processed_record_id.in_(record_ids))).all()
    )
    ann_map = {a.processed_record_id: a for a in ann_rows}
    by_id = {}
    for proc, raw, source_name, tcls, scls in rows:
        ann = ann_map.get(proc.id)
        by_id[proc.id] = {
            "processed_record_id": proc.id,
            "citation_tag": f"REC-{proc.id}",
            "external_id": raw.external_id,
            "source_name": source_name,
            "is_synthetic": raw.is_synthetic,
            "provenance_label": raw.provenance_label,
            "published_at": raw.published_at.isoformat(),
            "original_title": raw.original_title,
            "original_text": raw.original_text,
            "detected_language": proc.detected_language,
            "effective_topic": tcls.effective_topic,
            "effective_sentiment": scls.effective_sentiment,
            "sentiment_confidence": scls.confidence,
            "is_overridden": bool(tcls.is_overridden or scls.is_overridden),
            "is_verified": ann.is_verified if ann else False,
            "analyst_note": ann.note if ann else "",
        }
    return [by_id[rid] for rid in record_ids if rid in by_id]


@router.get("")
def list_reports(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reports = list(db.scalars(select(Report).order_by(Report.created_at.desc())).all())
    author_ids = {r.generated_by for r in reports if r.generated_by}
    authors = {
        u.id: u.full_name for u in db.scalars(select(User).where(User.id.in_(author_ids))).all()
    } if author_ids else {}

    return [
        {
            "id": r.id,
            "title": r.title,
            "subtitle": r.subtitle,
            "monitoring_topic_id": r.monitoring_topic_id,
            "event_id": r.event_id,
            "time_range_start": r.time_range_start.isoformat(),
            "time_range_end": r.time_range_end.isoformat(),
            "status": r.status,
            "executive_summary": r.executive_summary,
            "key_metrics": r.key_metrics,
            "evidence_count": len(r.evidence_record_ids or []),
            "generated_by_name": authors.get(r.generated_by, "PulseIQ System") if r.generated_by else "PulseIQ System",
            "created_at": r.created_at.isoformat(),
            "updated_at": r.updated_at.isoformat(),
        }
        for r in reports
    ]


@router.post("/generate", status_code=status.HTTP_201_CREATED)
def create_report(
    payload: ReportGenerateRequest,
    current_user: User = Depends(require_role("analyst")),
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    end_dt = payload.time_range_end or now
    start_dt = payload.time_range_start or (end_dt - timedelta(days=payload.days))

    report = generate_grounded_report(
        db=db,
        title=payload.title.strip(),
        subtitle=payload.subtitle.strip() or "Evidence-Backed Public Intelligence Brief",
        monitoring_topic_id=payload.monitoring_topic_id,
        event_id=payload.event_id,
        time_range_start=start_dt,
        time_range_end=end_dt,
        actor=current_user,
        status="draft",
    )
    return {
        "id": report.id,
        "title": report.title,
        "status": report.status,
        "executive_summary": report.executive_summary,
        "key_metrics": report.key_metrics,
        "evidence_record_ids": report.evidence_record_ids,
        "created_at": report.created_at.isoformat(),
    }


@router.get("/{report_id}")
def get_report_detail(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")
    author = db.get(User, report.generated_by) if report.generated_by else None
    evidence = _hydrate_evidence(db, report.evidence_record_ids or [])

    return {
        "id": report.id,
        "title": report.title,
        "subtitle": report.subtitle,
        "monitoring_topic_id": report.monitoring_topic_id,
        "event_id": report.event_id,
        "time_range_start": report.time_range_start.isoformat(),
        "time_range_end": report.time_range_end.isoformat(),
        "status": report.status,
        "executive_summary": report.executive_summary,
        "sections": report.sections,
        "key_metrics": report.key_metrics,
        "evidence": evidence,
        "methodology_notes": report.methodology_notes,
        "data_limitations": report.data_limitations,
        "provenance_disclosure": report.provenance_disclosure,
        "generated_by_name": author.full_name if author else "PulseIQ System",
        "created_at": report.created_at.isoformat(),
        "updated_at": report.updated_at.isoformat(),
    }


@router.patch("/{report_id}")
def update_report(
    report_id: int,
    payload: ReportUpdateRequest,
    request: Request,
    current_user: User = Depends(require_role("analyst")),
    db: Session = Depends(get_db),
):
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")

    if payload.title is not None:
        report.title = payload.title.strip()
    if payload.subtitle is not None:
        report.subtitle = payload.subtitle.strip()
    if payload.executive_summary is not None:
        report.executive_summary = payload.executive_summary.strip()
    if payload.status is not None:
        report.status = payload.status
    if payload.analyst_commentary is not None:
        sec = dict(report.sections or {})
        sec["analyst_commentary"] = payload.analyst_commentary
        report.sections = sec

    record_audit_log(
        db=db,
        action="report.updated",
        resource_type="report",
        resource_id=str(report.id),
        details={"status": report.status},
        actor=current_user,
        request=request,
    )
    db.commit()
    db.refresh(report)
    return {"id": report.id, "title": report.title, "status": report.status, "updated_at": report.updated_at.isoformat()}


@router.get("/{report_id}/export")
def export_report(
    report_id: int,
    format: str = Query(default="markdown", pattern="^(markdown|csv)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")
    evidence = _hydrate_evidence(db, report.evidence_record_ids or [])

    if format == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            ["citation_tag", "published_at", "source_name", "provenance", "topic", "sentiment", "confidence", "verified", "original_text"]
        )
        for ev in evidence:
            writer.writerow(
                [
                    ev["citation_tag"],
                    ev["published_at"],
                    ev["source_name"],
                    ev["provenance_label"],
                    ev["effective_topic"],
                    ev["effective_sentiment"],
                    ev["sentiment_confidence"],
                    ev["is_verified"],
                    ev["original_text"],
                ]
            )
        buf.seek(0)
        return StreamingResponse(
            iter([buf.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="pulseiq_report_{report.id}_evidence.csv"'},
        )

    lines = [
        f"# {report.title}",
        f"*{report.subtitle}*",
        "",
        f"- **Status:** {report.status.upper()}",
        f"- **Reporting Window:** {report.time_range_start.strftime('%Y-%m-%d')} to {report.time_range_end.strftime('%Y-%m-%d')}",
        f"- **Generated:** {report.created_at.strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        f"> {report.provenance_disclosure}",
        "",
        "## 1. Executive Summary",
        report.executive_summary,
        "",
        "## 2. Key Quantitative Metrics",
    ]
    for k, v in (report.key_metrics or {}).items():
        lines.append(f"- **{k.replace('_', ' ').title()}:** {v}")
    lines += [
        "",
        "## 3. Key Themes & Emerging Clusters",
    ]
    for th in (report.sections or {}).get("key_themes", []):
        lines.append(
            f"- **{th['label']}** ({th['record_count']:,} records, growth {th['growth_pct']:+.1f}%, Z={th['trend_velocity']:+.2f}): {th['summary']}"
        )
    lines += [
        "",
        "## 4. Representative Source Evidence",
    ]
    for ev in evidence:
        lines.append(
            f"- **[{ev['citation_tag']}]** ({ev['published_at'][:10]} | {ev['source_name']} | {ev['effective_sentiment'].upper()} | {ev['provenance_label']}): \"{ev['original_text']}\""
        )
    lines += [
        "",
        "## 5. Methodology",
        report.methodology_notes,
        "",
        "## 6. Data Limitations",
        report.data_limitations,
    ]
    return PlainTextResponse(
        content="\n".join(lines),
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="pulseiq_report_{report.id}.md"'},
    )
