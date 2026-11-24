"""Redis Pub/Sub real-time event bus for PulseIQ WebSocket and SSE live feeds."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import redis

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def publish_live_event(payload: dict[str, Any]) -> None:
    """Publish a newly processed record or ingestion status event to Redis Pub/Sub."""
    settings = get_settings()
    enriched = {
        "event_ts": datetime.now(timezone.utc).isoformat(),
        **payload,
    }
    try:
        client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=1.5)
        client.publish(settings.LIVE_EVENTS_CHANNEL, json.dumps(enriched, default=str))
        client.close()
    except Exception as exc:
        logger.debug("Live event publish skipped (Redis unavailable): %s", exc)
