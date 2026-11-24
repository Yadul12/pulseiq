"""Event Intelligence CRUD and Before-and-After Window Analytics."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, record_audit_log, require_role
from app.models.models import Event, User
from app.schemas.schemas import EventCreate
from app.services.event_service import analyze_event

router = APIRouter(prefix="/events", tags=["Event Intelligence"])


@router.get("")
def list_events(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    events = list(db.scalars(select(Event).order_by(Event.start_time.desc())).all())
    return [
        {
            "id": e.id,
            "title": e.title,
            "description": e.description,
            "event_type": e.event_type,
            "location": e.location,
            "start_time": e.start_time.isoformat(),
            "end_time": e.end_time.isoformat(),
            "baseline_days": e.baseline_days,
            "monitoring_topic_ids": e.monitoring_topic_ids,
            "keywords": e.keywords,
            "status": e.status,
            "created_at": e.created_at.isoformat(),
        }
        for e in events
    ]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_event(
    payload: EventCreate,
    request: Request,
    current_user: User = Depends(require_role("analyst")),
    db: Session = Depends(get_db),
):
    if payload.end_time <= payload.start_time:
        raise HTTPException(status_code=400, detail="Event end_time must be after start_time.")

    ev = Event(
        title=payload.title.strip(),
        description=payload.description.strip(),
        event_type=payload.event_type,
        location=payload.location,
        start_time=payload.start_time,
        end_time=payload.end_time,
        baseline_days=payload.baseline_days,
        monitoring_topic_ids=payload.monitoring_topic_ids,
        keywords=[k.strip() for k in payload.keywords if k.strip()],
        status="active",
        created_by=current_user.id,
    )
    db.add(ev)
    db.flush()
    record_audit_log(
        db=db,
        action="event.created",
        resource_type="event",
        resource_id=str(ev.id),
        details={"title": ev.title, "event_type": ev.event_type},
        actor=current_user,
        request=request,
    )
    db.commit()
    db.refresh(ev)
    return {
        "id": ev.id,
        "title": ev.title,
        "description": ev.description,
        "event_type": ev.event_type,
        "location": ev.location,
        "start_time": ev.start_time.isoformat(),
        "end_time": ev.end_time.isoformat(),
        "baseline_days": ev.baseline_days,
        "monitoring_topic_ids": ev.monitoring_topic_ids,
        "keywords": ev.keywords,
        "status": ev.status,
    }


@router.get("/{event_id}/analysis")
def get_event_analysis(
    event_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ev = db.get(Event, event_id)
    if not ev:
        raise HTTPException(status_code=404, detail="Event not found.")
    return analyze_event(db=db, event=ev)


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(
    event_id: int,
    request: Request,
    current_user: User = Depends(require_role("senior_analyst")),
    db: Session = Depends(get_db),
):
    ev = db.get(Event, event_id)
    if not ev:
        raise HTTPException(status_code=404, detail="Event not found.")
    record_audit_log(
        db=db,
        action="event.deleted",
        resource_type="event",
        resource_id=str(ev.id),
        details={"title": ev.title},
        actor=current_user,
        request=request,
    )
    db.delete(ev)
    db.commit()
    return None
