"""Data Sources, Modular Ingestion Execution, and Ingestion Job Logs."""

from __future__ import annotations

import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, record_audit_log, require_role
from app.ingestion.service import execute_ingestion_job
from app.models.models import DataSource, IngestionJob, MonitoringTopic, User
from app.schemas.schemas import DataSourceCreate, DataSourceUpdate, RunIngestionRequest
from app.workers.tasks import run_source_ingestion

router = APIRouter(tags=["Data Sources & Ingestion"])


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "source"


@router.get("/sources")
def list_sources(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sources = list(db.scalars(select(DataSource).order_by(DataSource.id.asc())).all())
    return [
        {
            "id": s.id,
            "name": s.name,
            "slug": s.slug,
            "provider_type": s.provider_type,
            "description": s.description,
            "config": s.config,
            "is_synthetic": s.is_synthetic,
            "is_enabled": s.is_enabled,
            "schedule_interval_minutes": s.schedule_interval_minutes,
            "rate_limit_per_min": s.rate_limit_per_min,
            "last_cursor": s.last_cursor,
            "last_ingested_at": s.last_ingested_at.isoformat() if s.last_ingested_at else None,
            "health_status": s.health_status,
            "total_records_ingested": s.total_records_ingested,
            "error_count_24h": s.error_count_24h,
            "created_at": s.created_at.isoformat(),
        }
        for s in sources
    ]


@router.post("/sources", status_code=status.HTTP_201_CREATED)
def create_source(
    payload: DataSourceCreate,
    request: Request,
    current_user: User = Depends(require_role("senior_analyst")),
    db: Session = Depends(get_db),
):
    slug = _slugify(payload.name)
    exists = db.scalar(select(DataSource).where((DataSource.name == payload.name) | (DataSource.slug == slug)))
    if exists:
        raise HTTPException(status_code=409, detail=f"Data source '{payload.name}' already exists.")

    src = DataSource(
        name=payload.name.strip(),
        slug=slug,
        provider_type=payload.provider_type,
        description=payload.description.strip(),
        config=payload.config,
        is_synthetic=payload.is_synthetic,
        is_enabled=payload.is_enabled,
        schedule_interval_minutes=payload.schedule_interval_minutes,
        rate_limit_per_min=payload.rate_limit_per_min,
        health_status="idle",
    )
    db.add(src)
    db.flush()
    record_audit_log(
        db=db,
        action="data_source.created",
        resource_type="data_source",
        resource_id=str(src.id),
        details={"provider_type": src.provider_type, "is_synthetic": src.is_synthetic},
        actor=current_user,
        request=request,
    )
    db.commit()
    db.refresh(src)
    return {"id": src.id, "name": src.name, "slug": src.slug, "provider_type": src.provider_type}


@router.patch("/sources/{source_id}")
def update_source(
    source_id: int,
    payload: DataSourceUpdate,
    request: Request,
    current_user: User = Depends(require_role("analyst")),
    db: Session = Depends(get_db),
):
    src = db.get(DataSource, source_id)
    if not src:
        raise HTTPException(status_code=404, detail="Data source not found.")
    updates = payload.model_dump(exclude_unset=True)
    for k, v in updates.items():
        setattr(src, k, v)
    record_audit_log(
        db=db,
        action="data_source.updated",
        resource_type="data_source",
        resource_id=str(src.id),
        details={"updated_fields": list(updates.keys())},
        actor=current_user,
        request=request,
    )
    db.commit()
    db.refresh(src)
    return {"id": src.id, "is_enabled": src.is_enabled, "health_status": src.health_status}


@router.post("/sources/{source_id}/run")
def run_source_ingestion_endpoint(
    source_id: int,
    payload: RunIngestionRequest = RunIngestionRequest(),
    current_user: User = Depends(require_role("analyst")),
    db: Session = Depends(get_db),
):
    src = db.get(DataSource, source_id)
    if not src:
        raise HTTPException(status_code=404, detail="Data source not found.")
    topic = db.get(MonitoringTopic, payload.monitoring_topic_id) if payload.monitoring_topic_id else None

    if payload.use_celery:
        task = run_source_ingestion.delay(src.id, payload.monitoring_topic_id, "manual", payload.batch_size)
        return {"mode": "queued", "task_id": task.id, "source_id": src.id}

    job = execute_ingestion_job(
        db=db,
        source=src,
        monitoring_topic=topic,
        job_type="manual",
        triggered_by=current_user,
        batch_size=payload.batch_size,
        publish_live=True,
    )
    return {
        "mode": "completed",
        "job_id": job.id,
        "status": job.status,
        "records_fetched": job.records_fetched,
        "records_inserted": job.records_inserted,
        "records_duplicated": job.records_duplicated,
        "records_failed": job.records_failed,
        "retry_count": job.retry_count,
        "cursor_after": job.cursor_after,
        "error_log": job.error_log,
    }


@router.get("/ingestion-jobs")
def list_ingestion_jobs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=5, le=100),
    source_id: Optional[int] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(IngestionJob, DataSource.name.label("source_name"), DataSource.provider_type).join(
        DataSource, DataSource.id == IngestionJob.source_id
    )
    if source_id is not None:
        stmt = stmt.where(IngestionJob.source_id == source_id)
    if status_filter and status_filter != "all":
        stmt = stmt.where(IngestionJob.status == status_filter)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(stmt.order_by(IngestionJob.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()

    return {
        "total": int(total),
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "id": j.id,
                "source_id": j.source_id,
                "source_name": s_name,
                "provider_type": p_type,
                "monitoring_topic_id": j.monitoring_topic_id,
                "job_type": j.job_type,
                "status": j.status,
                "records_fetched": j.records_fetched,
                "records_inserted": j.records_inserted,
                "records_duplicated": j.records_duplicated,
                "records_failed": j.records_failed,
                "retry_count": j.retry_count,
                "cursor_before": j.cursor_before,
                "cursor_after": j.cursor_after,
                "error_log": j.error_log,
                "started_at": j.started_at.isoformat() if j.started_at else None,
                "completed_at": j.completed_at.isoformat() if j.completed_at else None,
                "created_at": j.created_at.isoformat(),
            }
            for j, s_name, p_type in rows
        ],
    }
