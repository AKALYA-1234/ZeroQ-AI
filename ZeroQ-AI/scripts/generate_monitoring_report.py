#!/usr/bin/env python3
"""
Generate the real-world model monitoring report from admin-verified incidents.

  python scripts/generate_monitoring_report.py [--scope live] [--start 2026-12-01] [--end 2026-12-31]
         [--out reports/monitoring_2026-12.md] [--json reports/monitoring_2026-12.json]

Reads the database configured by DATABASE_URL. Read-only. Default scope "live" = real customers only.
"""
import argparse
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.database.connection import SessionLocal  # noqa: E402
from app.intelligence.monitoring import compute_monitoring, render_markdown_report  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scope", choices=["live", "test", "imported", "all"], default="live")
    ap.add_argument("--start")
    ap.add_argument("--end")
    ap.add_argument("--out", default="monitoring_report.md")
    ap.add_argument("--json", dest="json_out")
    args = ap.parse_args()

    def parse(value):
        return datetime.fromisoformat(value) if value else None

    db = SessionLocal()
    try:
        metrics = compute_monitoring(db, parse(args.start), parse(args.end), args.scope)
    finally:
        db.close()
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(render_markdown_report(metrics))
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            json.dump(metrics, fh, indent=1, default=str)
    b = metrics["basis"]
    print(f"wrote {args.out}: scope={args.scope} verified={b['verified_incidents']} "
          f"assessed={b['predictions_assessed']} sufficient={b['sample_sufficient']}")


if __name__ == "__main__":
    main()
