# ZeroQ AI — Production Readiness Report (2026-11-22)

> **Update:** the pilot-preparation phase verified PostgreSQL, Redis, multi-worker operation and live LLM
> providers (Groq and OpenRouter). The current score and remaining risks are in [PILOT_READINESS.md](PILOT_READINESS.md).

**Verdict: ready for a controlled pilot on real complaints; not yet general production.**
Readiness score **7 / 10**. All Critical and High findings that could be fixed in code are fixed and covered by
regression tests. What remains needs infrastructure or secrets that were not available here (LLM key, Redis,
PostgreSQL), plus frontend dependency majors and real-world accuracy data that only a pilot can produce.

## 1. Evidence summary

| Check | Result |
|---|---|
| Backend tests (`pytest tests/`, excl. legacy Playwright files) | **99 passed, 0 failed** — on both the current dev env and the patched dependency set in `requirements.lock.txt` |
| Frontend unit tests (`npm test`, Node test runner) | **6 passed** |
| Frontend production build (`npm run build`) | passes |
| Browser e2e (`scripts/e2e_live_sync.py`, real uvicorn + Vite + Chromium) | **4/4 pass**: AI understanding live; resolution delivered to open customer page in **48 ms**; update missed while offline recovered **0.04 s** after reconnect; no console errors |
| Responsive audit (`scripts/ui_responsive_audit.py`, 9 screens × 390/768/1440) | **27/27 clean** (no page overflow, console errors or failed API calls) after one layout fix |
| Load test (`scripts/load_test.py`, SQLite, 1 worker, laptop) | 50 concurrent submissions: 0 errors, unique IDs, p95 835 ms, 19.3/s; AI analysis p95 2.6 s (50/50); WebSocket fan-out to 100 dashboards: **5000/5000 events**, p95 160 ms; 10 simultaneous double-resolutions: exactly one success each; peak RSS 439 MB |
| `pip-audit` on the full 57-package lock set | **No known vulnerabilities** (was: 91 advisories across python-jose, python-multipart, python-dotenv, pillow, + starlette) |
| Bandit (backend) | 0 High; 4 Medium B608 reviewed — constant SQL fragments selected by a validated key (guarded + annotated); 3 Low (dev secret constant, `"bearer"` strings) |
| `npm audit` | 0 critical; 1 High (vite dev server) + 3 Moderate (esbuild dev server, react-router) — see §6 |
| LLM live connectivity (`scripts/check_llm_connectivity.py`) | **Not verified — no `ANTHROPIC_API_KEY` on this machine**. Integration is tested with mocks only. |

## 2. Findings and fixes

| ID | Sev. | Finding | Fix | Regression test |
|---|---|---|---|---|
| C1 | Critical | Any customer could read 5,960 unowned imported complaints incl. PII (`GET /api/complaints/{id}`, `/timeline`) | Strict ownership; non-owned → 404 (no enumeration) | `test_customer_cannot_read_*` |
| C2 | Critical | Hardcoded default JWT secret usable in production | Settings refuse to start in production with the dev secret or < 32 chars | `test_production_rejects_default_secret` |
| C3 | Critical | AI Insights mixed 6,000 synthetic imported records into "live" KPIs (all mislabelled `customer_submitted`) | Explicit data scope (`live` default / `imported` / `all`), banner when synthetic data is shown | `test_default_scope_is_live_platform_data_only` |
| H1 | High | No rate limiting (login brute force; paid-LLM-triggering submissions) | Login lockout per (ip, email), register/submit/admin-AI limits; Redis-backed when `REDIS_URL` set | `test_*_rate_limited*` |
| H2 | High | Complaint ID `count+1` collides under concurrency → 500 | ID from primary key, collision-safe suffix | `test_complaint_id_does_not_collide…` |
| H3 | High | Attachments publicly served; extension-only checks; whole file buffered | Removed public mount; authenticated owner/admin endpoint with `nosniff` + sandbox CSP; magic-byte check; bounded read; orphan cleanup | `test_attachments_require_owner…` |
| H4 | High | Wastage % divided by `units_affected`, never collected for live complaints | Admin records `units_at_risk`; % shown only when recorded, else N/A | `test_wastage_requires_recorded_units_at_risk` |
| H5 | High | LLM path: no breaker, no usage/cost, weak guesses presented as predictions | Typed error chain, circuit breaker, token/cost capture, `/llm/status`, prompt-injection hardening, **`undetermined`** outcome | `test_llm_*`, `test_low_confidence_…` |
| H6 | High | Evaluation: 29-item benchmark, no per-class/calibration/leakage-safe metrics, no data versioning | 4 separate evaluations, per-class P/R/F1/FPR/FNR, confusion matrix, ECE/Brier, grouped-template CV, dataset fingerprint, explicit promotion criteria | `test_model_evaluation.py` |
| H7 | High | python-jose (JWT) unmaintained with unpatched advisory; Starlette 0.37 advisories affecting `FileResponse`/multipart; 69 pillow advisories | Migrated to PyJWT 2.15; FastAPI 0.165 / Starlette 1.10; removed unused pillow, aiofiles, passlib; tested lock file | `test_jwt_rejects_tampered_none_alg_and_expired_tokens` |
| M1 | Med | `async def` complaint submission did blocking I/O on the event loop | Sync handler (thread pool) | covered by submission tests |
| M2 | Med | SQLite without WAL/busy timeout; silent SQLite fallback in production | WAL + `busy_timeout`; production refuses fallback | `test_sqlite_connections_use_wal…`, `test_concurrent_resolutions…` |
| M3 | Med | Analyses lost on crash never retried | Startup recovery sweep (bounded, no retry loops) | `test_missing_analyses_are_recovered` |
| M4 | Med | Legacy PUT could reopen verified resolutions; no stale-write protection | 409 on reopen; `expected_version` optimistic concurrency; row lock on PostgreSQL | `test_resolve_rejects_stale_version`, `test_legacy_update_cannot_reopen…` |
| M5 | Med | Single-process broker; no jitter; sockets outlive JWT | Redis pub/sub bus (opt-in), jittered backoff, close at token expiry, local fallback on bus failure | `test_realtime.py`, `liveEventsCore.test.js` |
| M6 | Med | Trend series ignored category filter; repeat-rate on tiny samples | All series filtered consistently; repeat metric needs ≥ 30 complaints per window | `test_category_filter_applies_to_every_trend_series` |
| M7 | Med | No password policy | ≥ 8 chars, letters + digits (register + change-password) | `test_registration_rejects_weak_passwords` |
| M8 | Med | Admin pages overflowed horizontally at 390/768 px (Dashboard, AI Prediction, CAPA) | `min-w-0` on the admin `main` flex child | `scripts/ui_responsive_audit.py` |
| — | Bug | Native-script matcher: substring matches (கெட்டு "spoiled" inside பாக்கெட்டுக்குள் "inside the packet"); inflected words missed stems ending in a virama | Prefix matching on virama-stripped stems, longest match wins | `test_spoiled_stem_inside_packet…`, `test_inflected_words_match…` |
| — | Bug | Calibration flipped category decisions (sum over subcategories) | Decision at T=1, confidence from calibrated probabilities | `test_temperature_changes_confidence_but_never_the_decision` |
| — | Bug | WebSocket client leaving before auth crashed the handler | Handled cleanly | `test_websocket_client_leaving_before_auth…` |

**WebSocket errors previously seen in the Vite log** were reproduced: `ECONNREFUSED` = backend not running on the proxy
target; a backend without `/api/ws` (older code) rejects the upgrade with 403; `ECONNRESET` = backend restarted while a
socket was open. They are availability/version-mismatch symptoms, not protocol bugs. The client now backs off with
jitter, stops on 4401, and re-syncs from the API after reconnecting.

## 3. AI / ML results (four separate evaluations — never blended)

Active model `issue-clf-20261122071804159063` (promoted by the gated pipeline; dataset fingerprint recorded).

| Evaluation | n | Accuracy | Macro-F1 | Notes |
|---|---|---|---|---|
| Independent multilingual set | 79 (en, ta incl. Tanglish, hi incl. Hinglish, te, ml, kn) | 97.5% | 0.958 | en 93%, hi 95%, ta/te/ml/kn 100%. Measured 93.7% before the matcher fixes; two lexicon additions (*naatham*, *துர்நாற்றம்*) were found via this set, so its figure is slightly optimistic. |
| Historical, leakage-safe (templates held out) | 35 templates, 5 folds | 82.9% | 0.821 | Subcategory 65.7%. Imported text is synthetic (35 sentences). |
| Unsupported offline (bn, gu, es, fr) | 4 | 25% | — | Expected: these need the LLM translator. |
| Admin-verified holdout | 0 | — | — | **No real-world accuracy yet.** Becomes available after ≥ 5 held-out verified incidents. |

Calibration (temperature fitted on out-of-fold historical predictions, never on the evaluation set): ECE 0.417 → **0.077**,
Brier 0.213 → **0.039**; share of predictions confident enough to skip fallback 59% → **91%** at 100% accuracy on that share.
Promotion criteria: independent accuracy ≥ 0.75, macro-F1 ≥ 0.70, and no regression > 0.02 vs the active model
(independent set and verified holdout). The pipeline rejected one candidate during this work for a 0.008 macro-F1
regression — which led to the calibration-decision bug fix above.

## 4. LLM integration status

Code path complete and tested with mocks (success, provider failure, circuit breaker, usage/cost accounting, refusal
fallback `fallbacks: "default"`). **Live connectivity is unverified** because no key is configured. To verify:
set `ANTHROPIC_API_KEY`, run `python scripts/check_llm_connectivity.py` (≈2 small billed requests), then check
`GET /api/admin/intelligence/llm/status`. Without a key the system uses the offline glossary + symptom rules and labels
results `rules` or `undetermined`; it never presents a guess as a prediction.

## 5. Database changes

* New column `incident_resolutions.units_at_risk` (nullable) — applied by the additive, idempotent
  `app/database/migrations.py` at startup and by `scripts/migrate_issue_intelligence.py`. No data is modified or dropped.
* SQLite connections: WAL, `busy_timeout=10000`, `foreign_keys=ON`. PostgreSQL: pool 10 + overflow 20, pre-ping, recycle.
* Browser, load and retraining tests used copies of the database. The development database `backend/zeroq_ai.db`
  did change during this session in two ways: (1) it switched to WAL journal mode (the new connection setting,
  applied when the test suite opened it), and (2) the pre-existing `tests/test_api_endpoints.py` and
  `tests/test_model_service.py` write `model_predictions` rows into it on every run (+15 rows). Complaints, users and
  all other tables are unchanged. Restore with `git checkout -- backend/zeroq_ai.db` if desired. Those two legacy test
  files should be moved onto the temporary-database fixture (`tests/conftest.py`) — listed under remaining issues.

## 6. Remaining issues

| Sev. | Issue | Required action |
|---|---|---|
| High | LLM fallback not verified live | Provide `ANTHROPIC_API_KEY`; run the connectivity script |
| High | Vite 5 dev server advisories (path traversal, Windows NTLM via launch-editor); the team's dev server runs with `--host 0.0.0.0` | Don't expose the dev server on shared networks; plan the Vite major upgrade. Production serves the static build, which is unaffected. |
| Medium | react-router-dom 6 open-redirect advisory (fix only in v7) | App navigates only to internal routes; schedule the v7 migration |
| Medium | Redis bus and Redis-backed rate limits not tested against a real Redis (Docker daemon not running) | Run the two-worker check in §7 before multi-worker deployment |
| Medium | Analytics is CPU-bound in one process: 10 concurrent requests p50 2.6 s (single request ≈ 120 ms server time) | Run ≥ 2 workers (requires `REDIS_URL`) or add a cache |
| Medium | Real-world prediction accuracy unknown; training data is synthetic + curated seeds | Pilot with admin verification; promote retrained models only through the gated pipeline |
| Medium | Legacy Playwright tests (`tests/test_e2e_playwright.py`, `test_full_lifecycle_e2e.py`) hardcode `127.0.0.1:5173` and were not run | Use `scripts/e2e_live_sync.py` or parametrise them |
| Medium | Legacy API tests write to the real development DB on every run | Move them onto the `tests/conftest.py` temporary-DB fixture |
| Low | JWT stored in `localStorage` (XSS would expose it); React escaping + CSP on attachments mitigate | Consider httpOnly cookie sessions |
| Low | Rate-limit client IP behind a proxy | Run uvicorn with `--proxy-headers --forwarded-allow-ips=<proxy>` |
| Low | 28 MB SQLite DB committed to git | Move to a release artifact / seed script |

## 7. Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `ENVIRONMENT` | `development` | `production` enables secret and DB guards and disables API docs |
| `SECRET_KEY` | dev value | **Required in production**, ≥ 32 random chars |
| `DATABASE_URL` | local PostgreSQL | Production refuses to fall back to SQLite |
| `REDIS_URL` | unset | Required for > 1 worker (event bus + shared rate limits) |
| `CORS_ORIGINS` | empty | Only if the frontend is served from another origin |
| `API_DOCS_ENABLED` | auto | Override docs visibility |
| `ANTHROPIC_API_KEY` | unset | Enables the LLM fallback |
| `LLM_ENABLED`, `LLM_MODEL`, `LLM_TIMEOUT_SECONDS`, `LLM_CIRCUIT_FAILURES`, `LLM_CIRCUIT_COOLDOWN_SECONDS` | `true`, `claude-opus-5-5`, 45, 3, 120 | LLM behaviour |
| `LLM_INPUT_PRICE_PER_MTOK`, `LLM_OUTPUT_PRICE_PER_MTOK` | 4, 20 | Cost estimates only |
| `ML_CONFIDENCE_THRESHOLD`, `ML_MIN_GUESS_CONFIDENCE`, `MIN_HISTORICAL_SIMILARITY` | 0.55, 0.35, 0.20 | Fallback / undetermined thresholds |
| `EMBEDDING_BACKEND` | `auto` | `sentence-transformers` if installed and cached, else TF-IDF |
| `RETRAIN_MIN_NEW_SAMPLES` | 20 | Gate for non-forced retraining |
| `IMPACT_UNIT_COST_INR`, `IMPACT_DOWNTIME_COST_PER_HOUR_INR` | unset | Cost-saved estimate is N/A until set |
| `UPLOAD_DIR`, `MAX_FILE_SIZE_MB` | `./uploads`, 10 | Private attachment storage |

## 8. Deployment

```bash
cd backend && python -m venv .venv && .venv/Scripts/pip install -r requirements.lock.txt   # tested, audited set
export ENVIRONMENT=production SECRET_KEY=... DATABASE_URL=postgresql://... REDIS_URL=redis://...
python ../scripts/migrate_issue_intelligence.py           # tables + additive columns + initial model if missing
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2 --proxy-headers --forwarded-allow-ips=<proxy-ip>
cd ../frontend && npm ci && npm run build                  # serve dist/ behind the same origin, proxy /api (incl. WebSocket upgrade)
python scripts/check_llm_connectivity.py                   # if ANTHROPIC_API_KEY is set
```
Before go-live: run `pytest tests/`, `npm test`, `scripts/e2e_live_sync.py`, `scripts/ui_responsive_audit.py`
and `scripts/load_test.py` (against a staging copy) on the target infrastructure, including a two-worker WebSocket check.
