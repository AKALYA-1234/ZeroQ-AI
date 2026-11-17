import os
import socket
import logging
from urllib.parse import urlparse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

logger = logging.getLogger(__name__)

db_url = settings.DATABASE_URL
engine = None

# SQLite path relative to backend root
sqlite_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "zeroq_ai.db"))
sqlite_url = f"sqlite:///{sqlite_file.replace(os.sep, '/')}"

if db_url.startswith("sqlite"):
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
else:
    # Check if PostgreSQL port is open
    parsed = urlparse(db_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 5432
    
    is_open = False
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        res = sock.connect_ex((host, port))
        if res == 0:
            is_open = True
        sock.close()
    except Exception:
        is_open = False

    if is_open:
        try:
            temp_engine = create_engine(db_url, pool_pre_ping=True)
            with temp_engine.connect() as conn:
                pass
            engine = temp_engine
            logger.info("Connected to PostgreSQL database.")
        except Exception as e:
            logger.warning(f"PostgreSQL connection error: {e}. Using SQLite fallback: {sqlite_url}")
            engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})
    else:
        logger.info(f"PostgreSQL not detected on {host}:{port}. Using SQLite: {sqlite_url}")
        engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
