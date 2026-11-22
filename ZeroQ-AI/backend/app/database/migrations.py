"""
Additive, idempotent schema migrations for columns added after a table already exists
(`create_all` creates missing tables but never alters existing ones).

Only nullable ADD COLUMN operations live here — nothing is dropped, renamed or rewritten,
so running it against production data is safe and repeatable.
"""
import logging
from typing import List, Tuple

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

# (table, column, SQL type) — keep in sync with the SQLAlchemy models.
ADDITIVE_COLUMNS: List[Tuple[str, str, str]] = [
    ("incident_resolutions", "units_at_risk", "INTEGER"),
]


def apply_additive_migrations(engine: Engine) -> List[str]:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    applied = []
    with engine.begin() as conn:
        for table, column, sql_type in ADDITIVE_COLUMNS:
            if table not in tables:
                continue  # create_all will create it with the column
            existing = {c["name"] for c in inspector.get_columns(table)}
            if column not in existing:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}"))
                applied.append(f"{table}.{column}")
                logger.info("Applied migration: added %s.%s", table, column)
    return applied
