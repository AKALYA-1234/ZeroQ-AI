#!/usr/bin/env python3
"""
Migration: issue-intelligence tables + initial classifier.

Creates (idempotently, checkfirst) the new tables
  issue_analyses, incident_resolutions, resolution_feedback, model_training_runs
on the configured database (PostgreSQL or the SQLite fallback), then trains and
promotes the initial issue classifier if none is active.

Usage:  python scripts/migrate_issue_intelligence.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.database.connection import SessionLocal, engine
from app.models.intelligence import IncidentResolution, IssueAnalysis, ModelTrainingRun, ResolutionFeedback
from app.intelligence import classifier
from app.intelligence.learning import retrain

TABLES = [ModelTrainingRun.__table__, IssueAnalysis.__table__, IncidentResolution.__table__,
          ResolutionFeedback.__table__]


def main() -> None:
    print(f"Database: {engine.dialect.name}")
    for table in TABLES:
        table.create(bind=engine, checkfirst=True)
        print(f"  ok  {table.name}")
    db = SessionLocal()
    try:
        if classifier.load_active() is None:
            run = retrain(db, trigger="bootstrap", user="migration")
            print(f"Trained initial classifier {run.model_version}: "
                  f"benchmark accuracy {run.metrics['benchmark_accuracy']:.1%} "
                  f"({run.metrics['benchmark_n']} independent multilingual queries)")
        else:
            print(f"Active classifier: {classifier.load_active().version}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
