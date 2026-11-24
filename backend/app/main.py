"""PulseIQ Enterprise Social Intelligence Platform — FastAPI Application Entrypoint."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

import redis
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, select, text

from app.api import auth, events, live, overview, records, reports, sources, topics
from app.core.config import get_settings
from app.core.database import Base, SessionLocal, engine
from app.models.models import ProcessedRecord, RawRecord
from app.nlp.pipeline import get_nlp_pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("pulseiq.api")

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Warm up calibrated scikit-learn NLP pipeline on startup for instant low-latency inference
    get_nlp_pipeline()
    if os.environ.get("VERCEL") == "1":
        Base.metadata.create_all(bind=engine)
        from app.data.seed_database import seed_database

        vercel_seed_count = int(os.environ.get("VERCEL_SEED_COUNT", "4000"))
        seed_database(record_count_override=vercel_seed_count)
    logger.info("PulseIQ API started cleanly (version %s).", settings.APP_VERSION)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Enterprise public-data intelligence, NLP trend monitoring, and evidence-backed reporting platform.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(_request: Request, exc: Exception):
    logger.exception("Unhandled API error: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal platform error occurred. Please check system logs."},
    )


@app.get(f"{settings.API_V1_PREFIX}/health", tags=["Health"])
def health_check():
    db_ok = False
    redis_ok = False
    raw_count = 0
    proc_count = 0
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
            raw_count = int(db.scalar(select(func.count(RawRecord.id))) or 0)
            proc_count = int(db.scalar(select(func.count(ProcessedRecord.id))) or 0)
            db_ok = True
    except Exception as exc:
        logger.error("DB health check failed: %s", exc)

    try:
        r = redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=1.5)
        redis_ok = bool(r.ping())
        r.close()
    except Exception:
        redis_ok = False

    return {
        "status": "healthy" if db_ok else "degraded",
        "service": "pulseiq-api",
        "version": settings.APP_VERSION,
        "database": "connected" if db_ok else "error",
        "redis": "connected" if redis_ok else "unavailable",
        "raw_records": raw_count,
        "processed_records": proc_count,
    }


app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(overview.router, prefix=settings.API_V1_PREFIX)
app.include_router(topics.router, prefix=settings.API_V1_PREFIX)
app.include_router(records.router, prefix=settings.API_V1_PREFIX)
app.include_router(sources.router, prefix=settings.API_V1_PREFIX)
app.include_router(events.router, prefix=settings.API_V1_PREFIX)
app.include_router(reports.router, prefix=settings.API_V1_PREFIX)
app.include_router(live.router)
