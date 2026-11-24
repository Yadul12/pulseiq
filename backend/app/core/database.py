import os
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

_db_url = settings.DATABASE_URL
if os.environ.get("VERCEL") == "1" and ("localhost" in _db_url or "127.0.0.1" in _db_url):
    _db_url = "sqlite:////tmp/pulseiq.db"

if _db_url.startswith("sqlite"):
    engine = create_engine(
        _db_url,
        connect_args={"check_same_thread": False},
        future=True,
    )
else:
    engine = create_engine(
        _db_url,
        pool_pre_ping=True,
        pool_size=12,
        max_overflow=20,
        future=True,
    )

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
