import os
import socket
import logging
from urllib.parse import urlparse

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

logger = logging.getLogger(__name__)

SQLITE_BUSY_TIMEOUT_MS = 10_000
POSTGRES_POOL_SIZE = 10
POSTGRES_MAX_OVERFLOW = 20

# SQLite path relative to backend root
sqlite_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "zeroq_ai.db"))
sqlite_url = f"sqlite:///{sqlite_file.replace(os.sep, '/')}"


def _configure_sqlite(engine: Engine) -> Engine:
    """WAL lets readers proceed during a write; busy_timeout makes concurrent writers wait
    instead of failing with 'database is locked'."""
    @event.listens_for(engine, "connect")
    def _pragmas(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()
    return engine


def make_engine(url: str) -> Engine:
    if url.startswith("sqlite"):
        return _configure_sqlite(create_engine(url, connect_args={"check_same_thread": False}))
    return create_engine(url, pool_pre_ping=True, pool_size=POSTGRES_POOL_SIZE,
                         max_overflow=POSTGRES_MAX_OVERFLOW, pool_recycle=1800)


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def _resolve_engine() -> Engine:
    db_url = settings.DATABASE_URL
    if db_url.startswith("sqlite"):
        return make_engine(db_url)
    parsed = urlparse(db_url)
    host, port = parsed.hostname or "localhost", parsed.port or 5432
    try:
        if not _port_open(host, port):
            raise ConnectionError(f"PostgreSQL not reachable on {host}:{port}")
        engine = make_engine(db_url)
        with engine.connect():
            pass
        logger.info("Connected to PostgreSQL database.")
        return engine
    except Exception as exc:
        if settings.is_production:
            # Never silently switch a production deployment onto a local SQLite file.
            raise RuntimeError(f"Database unavailable in production: {exc}") from exc
        logger.warning("PostgreSQL unavailable (%s). Using SQLite fallback: %s", exc, sqlite_url)
        return make_engine(sqlite_url)


engine = _resolve_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
