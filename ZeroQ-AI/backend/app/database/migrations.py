"""
Additive, idempotent schema migrations for columns added after a table already exists
(`create_all` creates missing tables but never alters existing ones).

Only two kinds of operation live here, both non-destructive and repeatable:
  * nullable ADD COLUMN
  * widening a VARCHAR(n) column to TEXT (PostgreSQL; SQLite does not enforce lengths)
Nothing is dropped, renamed, narrowed or rewritten.
"""
import logging
from typing import List, Tuple

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

# (table, column, SQL type) — keep in sync with the SQLAlchemy models.
ADDITIVE_COLUMNS: List[Tuple[str, str, str]] = [
    ("incident_resolutions", "units_at_risk", "INTEGER"),
    ("complaints", "data_origin", "VARCHAR(20)"),
]


# (table, column) VARCHAR columns that must become TEXT.
WIDEN_TO_TEXT: List[Tuple[str, str]] = [
    ("issue_analyses", "fallback_reason"),
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
        if engine.dialect.name == "postgresql":
            for table, column in WIDEN_TO_TEXT:
                if table not in tables:
                    continue
                col = next((c for c in inspector.get_columns(table) if c["name"] == column), None)
                if col is not None and getattr(col["type"], "length", None):
                    conn.execute(text(f"ALTER TABLE {table} ALTER COLUMN {column} TYPE TEXT"))
                    applied.append(f"{table}.{column} -> TEXT")
                    logger.info("Applied migration: widened %s.%s to TEXT", table, column)
    return applied
