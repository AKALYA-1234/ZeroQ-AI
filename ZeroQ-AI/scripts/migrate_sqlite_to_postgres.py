#!/usr/bin/env python3
"""
Copy the ZeroQ AI SQLite database into an EMPTY PostgreSQL database and prove the copy is faithful.

  python scripts/migrate_sqlite_to_postgres.py --source backend/zeroq_ai.db \
      --target postgresql://user:pass@host:5432/dbname --report migration_report.json

Safety:
  * The source is opened read-only (SQLite URI mode=ro) — it is never modified.
  * Aborts if any target table already contains rows (no merge, no overwrite).
  * Preflight: every source table/column is known to the models; no FK orphans; no string longer
    than its PostgreSQL column limit. Any failure aborts before writing.
  * The copy runs in ONE transaction: any error rolls everything back.
Validation (after commit): row counts per table, FK constraints present and orphan-free, id checksums,
random row-by-row comparison, sequences advanced past max(id). Writes a JSON report.
Never prints the target password.
"""
import argparse
import json
import os
import random
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from sqlalchemy import create_engine, func, inspect, select, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

import app.models  # noqa: E402,F401  (registers every table)
from app.database.base import Base  # noqa: E402
from app.database.migrations import apply_additive_migrations  # noqa: E402

BATCH = 2000
SPOT_CHECK_ROWS = 200


def source_engine(path: str):
    path = os.path.abspath(path).replace(os.sep, "/")
    return create_engine(f"sqlite:///file:{path}?mode=ro&uri=true")


def preflight(src, tables) -> list:
    problems = []
    insp = inspect(src)
    src_tables = set(insp.get_table_names())
    with src.connect() as conn:
        for t in tables:
            if t.name not in src_tables:
                continue
            src_cols = {c["name"] for c in insp.get_columns(t.name)}
            unknown = src_cols - {c.name for c in t.columns}
            if unknown:
                problems.append(f"{t.name}: source columns not in models: {sorted(unknown)}")
            for col in t.columns:
                if col.name in src_cols and getattr(col.type, "length", None):
                    longest = conn.execute(select(func.max(func.length(t.c[col.name])))).scalar() or 0
                    if longest > col.type.length:
                        problems.append(f"{t.name}.{col.name}: value length {longest} > limit {col.type.length}")
            for fk in t.foreign_keys:
                parent = fk.column.table
                if parent.name not in src_tables:
                    continue
                orphans = conn.execute(text(
                    f'SELECT count(*) FROM "{t.name}" c WHERE c."{fk.parent.name}" IS NOT NULL AND NOT EXISTS '
                    f'(SELECT 1 FROM "{parent.name}" p WHERE p."{fk.column.name}" = c."{fk.parent.name}")')).scalar()
                if orphans:
                    problems.append(f"{t.name}.{fk.parent.name}: {orphans} orphan rows")
    return problems


def copy_all(src, dst, tables) -> dict:
    copied = {}
    src_tables = set(inspect(src).get_table_names())
    with src.connect() as s, dst.begin() as d:          # single target transaction
        for t in tables:
            if t.name not in src_tables:
                copied[t.name] = 0
                continue
            cols = [c for c in t.columns if c.name in {x["name"] for x in inspect(src).get_columns(t.name)}]
            total, offset = 0, 0
            pk = list(t.primary_key.columns)
            while True:
                rows = s.execute(select(*cols).order_by(*pk).limit(BATCH).offset(offset)).mappings().all()
                if not rows:
                    break
                d.execute(t.insert(), [dict(r) for r in rows])
                total += len(rows)
                offset += BATCH
            copied[t.name] = total
        for t in tables:                                 # advance sequences past copied ids
            if "id" in t.c and t.c.id.autoincrement:
                d.execute(text(f"SELECT setval(pg_get_serial_sequence('{t.name}', 'id'), "
                               f"COALESCE((SELECT max(id) FROM \"{t.name}\"), 0) + 1, false)"))
    return copied


def _norm(v):
    if isinstance(v, datetime):
        return v.replace(tzinfo=None).isoformat()
    if isinstance(v, float):
        return round(v, 9)
    return v


def validate(src, dst, tables) -> dict:
    out = {"tables": {}, "fk_constraints": 0, "fk_orphans": 0, "sequence_problems": []}
    src_tables = set(inspect(src).get_table_names())
    with src.connect() as s, dst.connect() as d:
        out["fk_constraints"] = d.execute(text(
            "SELECT count(*) FROM information_schema.table_constraints WHERE constraint_type='FOREIGN KEY' "
            "AND table_schema='public'")).scalar()
        for t in tables:
            if t.name not in src_tables:
                continue
            src_n = s.execute(select(func.count()).select_from(t)).scalar()
            dst_n = d.execute(select(func.count()).select_from(t)).scalar()
            entry = {"source_rows": src_n, "target_rows": dst_n, "counts_match": src_n == dst_n}
            if "id" in t.c:
                entry["id_checksum_match"] = (s.execute(select(func.sum(t.c.id))).scalar()
                                              == d.execute(select(func.sum(t.c.id))).scalar())
                ids = [r[0] for r in s.execute(select(t.c.id))]
                sample = random.sample(ids, min(SPOT_CHECK_ROWS, len(ids)))
                cols = [c for c in t.columns if c.name in {x["name"] for x in inspect(src).get_columns(t.name)}]
                mismatches = 0
                for chunk in range(0, len(sample), 500):
                    part = sample[chunk:chunk + 500]
                    a = {r["id"]: r for r in s.execute(select(*cols).where(t.c.id.in_(part))).mappings()}
                    b = {r["id"]: r for r in d.execute(select(*cols).where(t.c.id.in_(part))).mappings()}
                    mismatches += sum(1 for i in part
                                      if {k: _norm(v) for k, v in a[i].items()} != {k: _norm(v) for k, v in b[i].items()})
                entry["spot_checked_rows"] = len(sample)
                entry["spot_check_mismatches"] = mismatches
                if t.c.id.autoincrement and dst_n:
                    nextval_ok = d.execute(text(
                        f"SELECT last_value >= (SELECT max(id) FROM \"{t.name}\") FROM "
                        f"{d.execute(text(f'SELECT pg_get_serial_sequence(:t, :c)'), {'t': t.name, 'c': 'id'}).scalar()}"
                    )).scalar()
                    if not nextval_ok:
                        out["sequence_problems"].append(t.name)
            for fk in t.foreign_keys:
                out["fk_orphans"] += d.execute(text(
                    f'SELECT count(*) FROM "{t.name}" c WHERE c."{fk.parent.name}" IS NOT NULL AND NOT EXISTS '
                    f'(SELECT 1 FROM "{fk.column.table.name}" p WHERE p."{fk.column.name}" = c."{fk.parent.name}")')).scalar()
            out["tables"][t.name] = entry
    out["all_counts_match"] = all(e["counts_match"] for e in out["tables"].values())
    out["all_checksums_match"] = all(e.get("id_checksum_match", True) for e in out["tables"].values())
    out["spot_check_mismatches"] = sum(e.get("spot_check_mismatches", 0) for e in out["tables"].values())
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--target", required=True)
    ap.add_argument("--report", default="migration_report.json")
    args = ap.parse_args()
    target_url = make_url(args.target)
    print(f"source: {os.path.abspath(args.source)} (read-only)")
    print(f"target: {target_url.render_as_string(hide_password=True)}")
    src = source_engine(args.source)
    dst = create_engine(args.target, pool_pre_ping=True)
    tables = Base.metadata.sorted_tables                 # FK dependency order

    Base.metadata.create_all(dst)
    apply_additive_migrations(dst)
    with dst.connect() as d:
        nonempty = [t.name for t in tables if d.execute(select(func.count()).select_from(t)).scalar()]
    if nonempty:
        print(f"ABORT: target already has data in {nonempty}. Use an empty database.")
        return 2
    problems = preflight(src, tables)
    if problems:
        print("ABORT: preflight failed:\n  " + "\n  ".join(problems))
        return 3

    started = time.monotonic()
    copied = copy_all(src, dst, tables)
    seconds = round(time.monotonic() - started, 1)
    report = {"source": os.path.abspath(args.source), "target": target_url.render_as_string(hide_password=True),
              "copied_rows": copied, "copy_seconds": seconds, "validation": validate(src, dst, tables),
              "migrated_at": datetime.now(timezone.utc).isoformat()}
    v = report["validation"]
    ok = (v["all_counts_match"] and v["all_checksums_match"] and v["spot_check_mismatches"] == 0
          and v["fk_orphans"] == 0 and not v["sequence_problems"])
    report["result"] = "OK" if ok else "VALIDATION FAILED"
    with open(args.report, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1)
    print(f"copied {sum(copied.values())} rows in {seconds}s; counts match={v['all_counts_match']} "
          f"checksums match={v['all_checksums_match']} spot-check mismatches={v['spot_check_mismatches']} "
          f"FK constraints={v['fk_constraints']} FK orphans={v['fk_orphans']} sequences ok={not v['sequence_problems']}")
    print("RESULT:", report["result"])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
