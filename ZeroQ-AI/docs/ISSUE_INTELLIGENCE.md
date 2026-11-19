# Issue Intelligence — multilingual prediction, verification, real-time sync, impact

## Flow

```
Customer submits complaint (any language)
  → background job: language detection → English working text (LLM translation, or offline glossary)
  → symptoms + entities → issue classifier (ML) → historical retrieval (same-category evidence)
  → confidence check: confident & comparable history → source "ml"
                      otherwise → LLM fallback (source "llm") if configured, else symptom rules ("rules")
  → IssueAnalysis row (original text preserved) → WebSocket event to admins + owner
Admin verifies / corrects → resolves → IncidentResolution (ground truth) → WebSocket event → customer page updates
Verified incidents → gated retraining (promote only if no regression) → analytics
```

## Setup

```bash
pip install -r backend/requirements.txt
python scripts/migrate_issue_intelligence.py   # creates 4 tables (idempotent) + trains initial classifier
```

Optional `backend/.env` settings (see `app/core/config.py`):

| Setting | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | unset | Enables Claude translation + low-confidence fallback. Without it the offline path is used. |
| `LLM_MODEL` | `claude-opus-5-5` | Model for the fallback (refusal fallback `fallbacks: "default"` is enabled). |
| `ML_CONFIDENCE_THRESHOLD` | `0.55` | Below this category probability → fallback. |
| `MIN_HISTORICAL_SIMILARITY` | `0.20` | Below this best-match similarity → unfamiliar issue. |
| `EMBEDDING_BACKEND` | `auto` | Locally cached sentence-transformers model if present, else TF-IDF. |
| `RETRAIN_MIN_NEW_SAMPLES` | `20` | New verified incidents required before a non-forced retrain. |
| `IMPACT_UNIT_COST_INR`, `IMPACT_DOWNTIME_COST_PER_HOUR_INR` | unset | Cost-saved is reported only when set. |

Dev proxy target: `VITE_API_TARGET` (default `http://localhost:8000`); WebSockets are proxied on `/api/ws`.

## API

| Method | Path | Notes |
|---|---|---|
| WS | `/api/ws` | First message `{"type":"auth","token":"<jwt>"}`. Events: `complaint.created`, `analysis.completed`, `complaint.updated`, `complaint.resolved`, `feedback.submitted`, `model.retrained`; each has `event_id` and complaint `version`. |
| GET | `/api/admin/intelligence/config` | Thresholds, taxonomy, LLM availability, metric definitions. |
| GET | `/api/admin/intelligence/incidents/{complaint_id}` | Analysis + verified resolution. |
| POST | `/api/admin/intelligence/incidents/{complaint_id}/analyze` | (Re)run analysis. |
| POST | `/api/admin/intelligence/incidents/{complaint_id}/resolve` | Verify/correct + resolve. 409 if already resolved. |
| POST | `/api/admin/intelligence/preview` | Dry-run analysis of raw text. |
| GET | `/api/admin/intelligence/kpis`, `/trends` | `start`, `end` (ISO dates), `category`. |
| GET/POST | `/api/admin/intelligence/learning/status`, `/learning/retrain` | `{"force": bool}`. |
| POST | `/api/complaints/{complaint_id}/feedback` | Customer rating 1–5 (owner only, after resolution). |

`POST /api/complaints/` now accepts empty `category` / `reported_severity` ("let AI identify").
`GET /api/complaints/{id}` adds `ai_understanding`, `resolution`, `feedback`, `version`.
`GET /api/admin/complaints` items add an `ai` badge object.

## Known limitations

* Historical complaint text uses ~35 template sentences; the classifier relies on curated seed phrases
  (`app/intelligence/seeds.py`) for vocabulary. Benchmark accuracy (29 independent multilingual queries) is
  indicative only — real accuracy is measured from admin-verified incidents.
* Offline understanding of non-English text uses a domain glossary (Tamil, Hindi, Telugu, Malayalam,
  Kannada, romanised/code-mixed). Other languages are detected but need the LLM for translation.
* The real-time broker is in-process: run a single worker, or replace `EventBroker` with Redis pub/sub.
* Imported historical complaints have `resolved_date == submitted_date`; they are excluded from
  resolution-time averages.
