"""Real-Time Live Monitoring: Bootstrap endpoint, WebSocket (/ws/live), and Server-Sent Events (/api/v1/live/stream)."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import decode_access_token, get_current_user
from app.models.models import (
    DataSource,
    ProcessedRecord,
    RawRecord,
    SentimentClassification,
    TopicClassification,
    User,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Live Monitoring"])


@router.get("/api/v1/live/recent")
def get_recent_live_activity(
    limit: int = Query(default=35, ge=5, le=100),
    topic_id: Optional[int] = Query(default=None),
    sentiment: Optional[str] = Query(default=None),
    source_id: Optional[int] = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = (
        select(ProcessedRecord, RawRecord, DataSource, TopicClassification, SentimentClassification)
        .join(RawRecord, RawRecord.id == ProcessedRecord.raw_record_id)
        .join(DataSource, DataSource.id == RawRecord.source_id)
        .join(TopicClassification, TopicClassification.processed_record_id == ProcessedRecord.id)
        .join(SentimentClassification, SentimentClassification.processed_record_id == ProcessedRecord.id)
    )
    if topic_id is not None:
        stmt = stmt.where(TopicClassification.monitoring_topic_id == topic_id)
    if source_id is not None:
        stmt = stmt.where(RawRecord.source_id == source_id)
    if sentiment and sentiment != "all":
        stmt = stmt.where(SentimentClassification.predicted_sentiment == sentiment)

    rows = db.execute(stmt.order_by(ProcessedRecord.processed_at.desc(), ProcessedRecord.id.desc()).limit(limit)).all()
    return [
        {
            "type": "record.processed",
            "processed_record_id": proc.id,
            "raw_record_id": raw.id,
            "external_id": raw.external_id,
            "source_id": src.id,
            "source_name": src.name,
            "provider_type": src.provider_type,
            "is_synthetic": raw.is_synthetic,
            "provenance_label": raw.provenance_label,
            "published_at": raw.published_at.isoformat(),
            "processed_at": proc.processed_at.isoformat(),
            "title": raw.original_title,
            "excerpt": proc.normalized_text[:240],
            "language": proc.detected_language,
            "topic": tcls.effective_topic,
            "monitoring_topic_id": tcls.monitoring_topic_id,
            "topic_confidence": tcls.confidence,
            "sentiment": scls.effective_sentiment,
            "sentiment_score": scls.sentiment_score,
            "sentiment_confidence": scls.confidence,
            "is_duplicate": proc.is_duplicate,
            "processing_status": proc.processing_status,
        }
        for proc, raw, src, tcls, scls in rows
    ]


@router.websocket("/ws/live")
async def websocket_live_feed(websocket: WebSocket, token: Optional[str] = Query(default=None)):
    """Real-time WebSocket stream backed by Redis Pub/Sub (`pulseiq:live_events`)."""
    if token:
        try:
            decode_access_token(token)
        except Exception:
            await websocket.close(code=4401)
            return

    await websocket.accept()
    settings = get_settings()
    redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(settings.LIVE_EVENTS_CHANNEL)

    await websocket.send_json(
        {
            "type": "connection.ready",
            "channel": settings.LIVE_EVENTS_CHANNEL,
            "server_time": datetime.now(timezone.utc).isoformat(),
        }
    )

    try:
        while True:
            try:
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg and msg.get("data"):
                    await websocket.send_text(str(msg["data"]))
                else:
                    # Drain optional client keepalive messages without blocking
                    try:
                        await asyncio.wait_for(websocket.receive_text(), timeout=0.05)
                    except asyncio.TimeoutError:
                        pass
            except WebSocketDisconnect:
                break
            except Exception as exc:
                logger.debug("WebSocket loop notice: %s", exc)
                await asyncio.sleep(0.5)
    finally:
        try:
            await pubsub.unsubscribe(settings.LIVE_EVENTS_CHANNEL)
            await pubsub.aclose()
            await redis_client.aclose()
        except Exception:
            pass


@router.get("/api/v1/live/stream")
async def sse_live_stream(token: Optional[str] = Query(default=None)):
    """Server-Sent Events (SSE) real-time feed backed by Redis Pub/Sub."""
    if token:
        decode_access_token(token)

    settings = get_settings()

    async def event_generator():
        redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(settings.LIVE_EVENTS_CHANNEL)
        try:
            yield f"event: ready\ndata: {json.dumps({'status': 'connected', 'server_time': datetime.now(timezone.utc).isoformat()})}\n\n"
            ticks = 0
            while True:
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg and msg.get("data"):
                    yield f"event: record\ndata: {msg['data']}\n\n"
                else:
                    ticks += 1
                    if ticks % 15 == 0:
                        yield f"event: heartbeat\ndata: {json.dumps({'ts': datetime.now(timezone.utc).isoformat()})}\n\n"
                await asyncio.sleep(0.1)
        finally:
            try:
                await pubsub.unsubscribe(settings.LIVE_EVENTS_CHANNEL)
                await pubsub.close()
                await redis_client.aclose()
            except Exception:
                pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
