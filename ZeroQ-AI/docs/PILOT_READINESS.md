# ZeroQ AI — Controlled Pilot Readiness (2026-11-22)

This covers what was built and verified to prepare a controlled pilot. It follows on from
[PRODUCTION_READINESS.md](PRODUCTION_READINESS.md). The ML pipeline is described in
[ISSUE_INTELLIGENCE.md](ISSUE_INTELLIGENCE.md).

**Ground rules this report follows**
- Every number below comes from a command that was actually run. Where nothing could be measured, the report says so.
- **No real admin-verified incidents exist yet**, so real-world accuracy is **N/A**. It is never estimated.
- Synthetic, test and model-generated data are kept out of real-world metrics.
- No test ever touched the development database. Its SHA-256 prefix `07b37dfe9c5418d4` was the same before and after all the work.

---

## 1. Pilot deployment architecture

```
                 Internet ──TLS (operator-provided: Caddy / cloud LB / nginx+certbot)──┐
                                                                                       ▼
┌──────────────────────────── docker compose project "zeroq-pilot" ──────────────────────────┐
│  frontend  nginx 1.27 + built SPA      :80 → ${PUBLIC_PORT:-8080}   (the only published port) │
│    ├─ /            static SPA (CSP, X-Frame-Options, nosniff, Referrer/Permissions-Policy)  │
│    ├─ /api/        → backend:8000   (proxy headers)                                         │
│    └─ /api/ws/     → backend:8000   (WebSocket upgrade, long read timeout)                  │
│                                                                                           │
│  backend   uvicorn, BACKEND_WORKERS (default 2), non-root uid 10001, healthcheck /api/health │
│    ├─ PostgreSQL  (db)     system of record                                                 │
│    ├─ Redis       (redis)  pub/sub event bus + shared rate limits (no persistence; 128 MB)  │
│    └─ outbound HTTPS → LLM chain: Groq → OpenRouter → Anthropic (only providers with a key) │
│                                                                                           │
│  migrate   one-shot: create tables, additive columns, initial issue classifier             │
│  db        postgres:16-alpine, volume pgdata     (internal network only)                   │
│  redis     redis:7.4-alpine                      (internal network only)                   │
│  volumes:  pgdata, uploads (/data/uploads), classifier (versioned model registry)          │
└───────────────────────────────────────────────────────────────────────────────────────────┘
```

**Request path for a complaint**
1. The customer submits through the SPA to `/api/complaints/`. The row is stored with `data_origin` set to `real`, or `test` for a `PILOT_TEST_EMAILS` account.
2. The intelligence engine runs: translation (glossary first, LLM only for unsupported languages or low-quality glossary output), then the ML classifier, then historical similarity.
3. If ML confidence is low, the LLM is consulted. The text is **redacted** before it leaves the server.
4. If every LLM provider fails, the result is marked `rules` or `undetermined` with a `fallback_reason`. Nothing is fabricated.
5. The event is published to Redis, so every worker pushes it to its own WebSocket clients. Clients also poll as a fallback.
6. An admin verifies the incident and records the resolution. That verified record is the only input to real-world monitoring and to retraining.

**Data-origin model** ([backend/app/intelligence/origin.py](../backend/app/intelligence/origin.py))

| Origin | How it is assigned | Real-world metrics | Training |
|---|---|---|---|
| `synthetic` | Imported dataset rows (has `customer_id`) | Excluded (scope `imported`) | Historical only, labelled as such |
| `real` | Platform submission from a non-test account; legacy NULL rows count as real | **Included** (scope `live`) | Yes, once admin-verified |
| `test` | Submission from a `PILOT_TEST_EMAILS` address or domain, or reclassified with `pilot_accounts.py mark-test` | Excluded (scope `test`) | **Never** |
| model-generated | `prediction_source` ∈ ml / llm / rules / undetermined on the analysis | Is the thing being measured, never the ground truth | Never used as a label |

---

## 2. Infrastructure setup guide

### 2.1 Prerequisites
- Docker Engine 24 or later with Compose v2. The host clock must be NTP-synced (see risk R9).
- The repository root must be present, because the backend image reads the sibling `Model/` folder.
- A TLS terminator in front of `PUBLIC_PORT`. The stack itself serves plain HTTP.

### 2.2 Secrets file
```bash
cd ZeroQ-AI
cp deploy/.env.pilot.example deploy/.env.pilot          # gitignored, never commit it
python -c "import secrets; print(secrets.token_urlsafe(48))"   # run twice: SECRET_KEY and POSTGRES_PASSWORD
```
Fill in the values (section 3). Keys are read only by the backend. They never reach the frontend bundle, and
`/api/admin/intelligence/llm/status` reports only whether a key is *configured*.

### 2.3 LLM providers (each one is optional; providers without a key are skipped)

| Provider | Get a key | Settings | Billing as reported by the app |
|---|---|---|---|
| **Groq** (primary) | console.groq.com → API Keys | `GROQ_API_KEY`, `GROQ_MODEL` (default `openai/gpt-oss-120b`) | `unknown` until you set `GROQ_INPUT/OUTPUT_PRICE_PER_MTOK`, then `paid` with an estimated cost |
| **OpenRouter** (secondary) | openrouter.ai → Keys | `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` | A model ID ending in `:free` is `free_tier`: cost 0, rate-capped, no availability guarantee. Any other model is `paid` if a price is set, otherwise `unknown` |
| **Anthropic** (third) | console.anthropic.com | `ANTHROPIC_API_KEY`, `LLM_MODEL` | `paid` at `LLM_INPUT/OUTPUT_PRICE_PER_MTOK` |

Before enabling the pilot, check each provider on its own (no key values are printed):
```bash
python scripts/check_llm_connectivity.py          # per-provider pass/fail, latency, model, OpenRouter key limits
```

### 2.4 PostgreSQL and the first start
The importer refuses to write into a target that already has rows. So **import before the first full start**:
```bash
C="docker compose -f deploy/docker-compose.pilot.yml --env-file deploy/.env.pilot"
$C up -d db                                                     # empty database only
$C run --rm --no-deps -v "$PWD/backend/zeroq_ai.db:/import/zeroq_ai.db:ro" migrate \
   sh -c 'python ../scripts/migrate_sqlite_to_postgres.py --source /import/zeroq_ai.db \
          --target "$DATABASE_URL" --report /tmp/migration_report.json && cat /tmp/migration_report.json'
$C up -d --build                                                # migrate (additive) → backend → frontend
```
- The source is mounted read-only and also opened read-only.
- The password stays inside the container environment.
- To start empty instead (no history), skip the `run` step.

### 2.5 Pilot accounts (run inside the backend container, or anywhere `DATABASE_URL` points at the pilot DB)
```bash
$C exec backend python ../scripts/pilot_accounts.py create-admin --email ops@yourco.com --name "Ops Lead"
$C exec backend python ../scripts/pilot_accounts.py deactivate   --email admin@zeroq.com      # demo admin
$C exec backend python ../scripts/pilot_accounts.py deactivate   --email demo@customer.com    # demo customer
$C exec backend python ../scripts/pilot_accounts.py list
```
- Passwords come from a hidden prompt (use `exec -it`) or from the `PILOT_PASSWORD` environment variable. They are never accepted as arguments.
- Deactivation keeps all records and refuses to remove the last active admin.
- `mark-test --email` reclassifies an account's existing complaints as test data.

### 2.6 Updating a running stack
Rebuild a single service **with `--no-deps`**, for example `$C up -d --build --no-deps frontend`. Without it, Compose restarts `migrate` and `backend` as dependencies, which gave a brief 502 during testing.

### 2.7 Redis
No setup is needed beyond Compose. Redis holds no durable data: events are fire-and-forget, rate-limit counters are short-lived, and persistence is off on purpose. `BACKEND_WORKERS > 1` **requires** `REDIS_URL`. Without it, events stay on one worker and rate limits are per-process.

---

## 3. Environment variables

The backend reads `ZeroQ-AI/.env` and then `backend/.env`. Real environment variables win. **Empty values are ignored** (`env_ignore_empty`), so Compose passing `""` for an unset optional value leaves the default in place.

| Variable | Default | Required | Notes |
|---|---|---|---|
| `ENVIRONMENT` | development | prod: `production` | Production refuses the dev `SECRET_KEY` and disables API docs |
| `SECRET_KEY` | dev key | **yes** | 32 or more random characters. JWT signing (HS256) |
| `DATABASE_URL` | local PG | **yes** | Built by Compose from `POSTGRES_*` |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | zeroq_pilot / zeroq / — | password **yes** | Compose only |
| `REDIS_URL` | unset | yes if workers > 1 | Compose sets `redis://redis:6379/0` |
| `BACKEND_WORKERS` | 2 | | uvicorn worker processes |
| `PUBLIC_PORT` | 8080 | | The only published port |
| `CORS_ORIGINS` | "" | | Comma-separated. Not needed behind the bundled nginx (same origin) |
| `API_DOCS_ENABLED` | auto | | Off in production unless set to true |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | 60 | | JWT verification allows 30 s of clock skew |
| `UPLOAD_DIR` / `MAX_FILE_SIZE_MB` | /data/uploads / 10 | | |
| `LLM_ENABLED` | true | | false means ML, rules and undetermined only |
| `LLM_PROVIDER` | groq | | Primary provider |
| `LLM_FALLBACK_PROVIDERS` | openrouter,anthropic | | Tried in order. Unknown names are ignored |
| `LLM_FAILOVER_ENABLED` | true | | false means the primary only |
| `LLM_MAX_RETRIES` / `LLM_RETRY_MAX_WAIT_SECONDS` | 2 / 10 | | Per provider, for 429, 5xx and timeouts. Honours `Retry-After` |
| `LLM_TIMEOUT_SECONDS` | 45 | | Per HTTP call |
| `LLM_CIRCUIT_FAILURES` / `LLM_CIRCUIT_COOLDOWN_SECONDS` | 3 / 120 | | Per-provider circuit breaker |
| `GROQ_API_KEY` / `GROQ_MODEL` / `GROQ_BASE_URL` | — / openai/gpt-oss-120b / api.groq.com | | Secret |
| `GROQ_INPUT_PRICE_PER_MTOK` / `GROQ_OUTPUT_PRICE_PER_MTOK` | unset | | Unset means cost is reported as unknown (None), never 0 |
| `OPENROUTER_API_KEY` / `OPENROUTER_MODEL` / `OPENROUTER_BASE_URL` | — | | `:free` suffix means free tier |
| `OPENROUTER_INPUT/OUTPUT_PRICE_PER_MTOK` / `OPENROUTER_APP_TITLE` | unset / ZeroQ AI | | |
| `ANTHROPIC_API_KEY` / `LLM_MODEL` | — / claude-opus-5-5 | | Secret |
| `LLM_INPUT/OUTPUT_PRICE_PER_MTOK` | 4.0 / 20.0 | | Anthropic estimate |
| `ML_CONFIDENCE_THRESHOLD` | 0.55 | | Below this, the LLM is consulted |
| `ML_MIN_GUESS_CONFIDENCE` / `MIN_HISTORICAL_SIMILARITY` | 0.35 / 0.20 | | |
| `EMBEDDING_BACKEND` / `EMBEDDING_MODEL` | auto / all-MiniLM-L6-v2 | | |
| `RETRAIN_MIN_NEW_SAMPLES` | 20 | | Retraining gate |
| `PILOT_TEST_EMAILS` | demo@customer.com | | Exact addresses and/or `@domain` entries, matched against whole domains only. Example: `demo@customer.com,@example.com` |
| `IMPACT_UNIT_COST_INR` / `IMPACT_DOWNTIME_COST_PER_HOUR_INR` | unset | | Unset means cost saved shows N/A |
| `VITE_SHOW_DEMO_CREDENTIALS` | unset | | Frontend build only. Demo logins appear only in dev builds or when this is `true` |

---

## 4. Database migration report (SQLite → PostgreSQL)

Tool: [scripts/migrate_sqlite_to_postgres.py](../scripts/migrate_sqlite_to_postgres.py). The source is read-only, the target must be empty, preflight checks run first, the copy is one transaction, and a JSON report is written.

| Check | Result |
|---|---|
| Rows copied (host run, scratch PostgreSQL 18) | **81,356 rows in 8.6 s** |
| Rows copied (Compose run into postgres:16) | **81,359 rows in 14.2 s**, status OK |
| Row counts per table, source vs target | All equal |
| ID checksums per table | All equal |
| Random row-by-row comparison (200 rows per table) | **0 mismatches** |
| Foreign-key constraints present / orphans | **23 FKs / 0 orphans** |
| Sequences advanced past max(id) | OK |
| Source database SHA after migration | Unchanged |
| Re-run against the populated target | **Aborted (exit 2)**, nothing written |
| Additive migration on the populated pilot DB | `complaints.data_origin` added. 6,124 complaints kept |
| PostgreSQL-specific fixes found by the run | Boolean comparison `= 1` changed to a bound parameter. `issue_analyses.fallback_reason` widened VARCHAR(255) → TEXT, applied additively on PostgreSQL |
| Test suite against PostgreSQL (`TEST_DATABASE_URL=…/zeroq_test`) | **107 passed** |
| Legacy tests against the migrated pilot DB | **28 passed** |
| Transactions and concurrency | Concurrent double-resolution gave exactly one 200 and the rest 409. Concurrent submissions got unique IDs and every row persisted (section 6) |

The 3-row difference between the two runs is the development database gaining rows between the runs. Each run matched its own source exactly.

**Rollback:** the SQLite file is never modified. To roll back, stop the stack and point `DATABASE_URL` back at SQLite. To retry an import, the target must be dropped and recreated first. That is an irreversible operation on the pilot database, so get explicit approval before doing it.

---

## 5. LLM integration test report

**Implementation:** [llm_providers.py](../backend/app/intelligence/llm_providers.py) and [llm.py](../backend/app/intelligence/llm.py).
- Groq and OpenRouter use the OpenAI-compatible chat API with `json_schema` structured output. If a model rejects `response_format`, the call is retried automatically in prompt-JSON mode.
- Anthropic uses the existing SDK path, unchanged.
- Every response is validated against the existing pydantic schemas.

**What leaves the server:** [redaction.py](../backend/app/intelligence/redaction.py) replaces emails, phone numbers (10 or more digits), and the complaint's own customer name, email, contact and organisation with `[EMAIL]`, `[PHONE]` and `[CUSTOMER]`. Batch and machine IDs, quantities and dates are kept. The original text stays in our database.

### 5.1 Mocked tests (no network): [tests/test_llm_providers.py](../tests/test_llm_providers.py), 17 cases, all passing
They cover:
- structured success and the recorded fields (provider, model, latency, tokens, status)
- 429 retried while honouring `Retry-After`
- the prompt-JSON fallback
- free-tier vs priced billing
- 503 failover
- timeout, invalid JSON, truncated output and 401, each failing over
- all providers failing raises `LLMUnavailable`
- failover disabled
- an open circuit skips the provider
- end-to-end redaction
- the rules fallback when every provider fails
- the status endpoint never contains secrets and returns 403 for customers
- a redacted echo never replaces the English working text

### 5.2 Live connectivity, each provider tested on its own
| Provider | Model | Result |
|---|---|---|
| Groq | openai/gpt-oss-120b | **Pass.** translate 1.6 s (214 in / 150 out tokens), analyze 2.0 s. `json_schema` supported. Billing `unknown` (no price set) |
| OpenRouter | nvidia/nemotron-3-ultra-550b-a55b:free | **Pass.** `is_free_tier=true`, key limit 50 requests, latency **14–23 s**, cost 0 |
| Anthropic | — | **Not tested.** No key was provided |

### 5.3 Live validation: [scripts/llm_live_validation.py](../scripts/llm_live_validation.py), labelled multilingual set
| Measure | Result |
|---|---|
| Category accuracy, 79 items in supported languages | ML **97.47 %**, LLM-only **92.41 %**, full pipeline **100 %** (LLM consulted for 13.25 % of items) |
| Unsupported languages (n = 4) | ML 25 %, LLM 100 %. The sample is too small to generalise |
| Identifiers preserved through LLM translation | Yes |
| Primary timeout | Failed over to OpenRouter, or raised `LLMUnavailable` when no fallback was available |
| Invalid Groq key | Failed over to OpenRouter in 6.6 s |
| Every provider failing | `LLMUnavailable`. **No fabricated prediction** |
| Groq usage for the run | 84 calls, 62,177 input / 37,309 output tokens, p50 latency 5.1 s, cost **unknown** (no price configured) |

> **Caveat:** this labelled set is *not* admin-verified real outcomes, and the glossary was tuned on it. Treat these figures as a regression baseline, **not** as pilot accuracy.

### 5.4 Live LLM inside the production containers
- A Bengali complaint was translated by Groq and then classified by ML as Infestation.
- A QR-code complaint got ML confidence 0.31 and was routed to the Groq LLM.
- Phone and email were redacted in the outbound request.
- No key values appeared in `/llm/status`.

### 5.5 Free tier vs paid
`/api/admin/intelligence/llm/status` shows each provider's billing class (`free_tier` / `paid` / `unknown`), calls, failures and errors. It shows a known-cost subtotal, and the total cost is `null` whenever any call's cost is unknown, so it is never understated as 0. **For the pilot, set the Groq prices** from your Groq plan, so spend is estimated rather than unknown.

---

## 6. Redis and multi-worker validation

Tool: [scripts/multiworker_validation.py](../scripts/multiworker_validation.py)

| Setup | Checks | Notes |
|---|---|---|
| Two host uvicorn processes (8011 / 8012) sharing PostgreSQL and Redis | **7 / 7 pass** | Cross-worker event delivery in about 5 ms |
| Production containers via nginx, 2 uvicorn workers | **7 / 7 pass** | Redis `NUMSUB` = 2 subscribers. Shared login lockout triggered at attempt 11 across workers |

The checks:
- cross-worker `complaint.resolved` delivery, with unrelated customers receiving nothing
- admin fan-out of `complaint.created`
- exactly-once delivery across 40 submissions
- a shared rate limit
- concurrent double-resolution: one 200, the rest 409
- concurrent submissions: unique IDs, all persisted

**Redis outage test** (Redis stopped while the stack was running):
- Submissions still succeeded (3.3 s).
- Same-worker events were still delivered.
- **Cross-worker events were missed** during the outage.
- The database stayed correct.
- The bus recovered automatically 17.3 s after Redis returned.
- Clients heal through the 30 s poll fallback on the tracking page and resync on reconnect.

**Browser end-to-end** ([scripts/e2e_live_sync.py](../scripts/e2e_live_sync.py)) against the production stack: **5 / 5 pass**. Live delivery took 39 ms, and the offline state was shown within 0.01 s of the network dropping. **UI responsive audit:** 30 / 30.

---

## 7. Real-world AI evaluation dashboard

**Where:** Admin → **Model Monitoring** (`/admin/ai-monitoring`). API: `GET /api/admin/intelligence/monitoring` and `/monitoring/report` (Markdown). Offline report: `python scripts/generate_monitoring_report.py --scope live --start … --end … --out …`.

**Computed only from admin-verified incidents in the selected scope** (default `live` = real customers):
- overall accuracy with a Wilson 95 % interval
- accuracy by prediction source (ML / LLM / rules)
- model vs fallback
- the admin correction rate
- per-category precision, recall and F1
- the confusion matrix
- per-language accuracy
- the pipeline mix: LLM fallback rate, low-confidence rate, undetermined rate
- unfamiliar or new-category candidates
- confidence calibration buckets
- accuracy by model version

**Reliability guards:**
- Rates are marked *insufficient data* below **30** verified incidents overall, or below **5** per category or language.
- Test and synthetic data are only visible by explicitly picking their scope, and a banner says so.

**Current state:** the pilot has **0 real verified incidents**, so the dashboard correctly shows empty and insufficient-data states. Nothing is back-filled from synthetic data.

**Model promotion:** a retrained classifier is promoted only through the existing gates: enough new samples (`RETRAIN_MIN_NEW_SAMPLES`) and evaluation no worse than the current model. Test-origin incidents are excluded from training, which is verified by tests. Monitoring never promotes a model.

---

## 8. Pilot testing checklist

**Before go-live**
- [ ] `deploy/.env.pilot` filled in. `SECRET_KEY` and `POSTGRES_PASSWORD` freshly generated. The file is not in git.
- [ ] TLS terminator in front of `PUBLIC_PORT`. HTTP redirects to HTTPS.
- [ ] Host clock NTP-synced.
- [ ] `check_llm_connectivity.py` passes for each provider you intend to use. Groq prices set.
- [ ] Decide whether to import history (section 2.4) or start empty. If importing, keep the migration report.
- [ ] Real admin created. Demo admin and demo customer deactivated. `pilot_accounts.py list` checked.
- [ ] `PILOT_TEST_EMAILS` lists every internal or QA address or domain.
- [ ] Smoke test: login, submit, live update on the admin dashboard, resolve, customer sees the resolution.
- [ ] Optional: `IMPACT_*` cost assumptions agreed with the business owner.
- [ ] Backups: scheduled `pg_dump` of `pgdata`, and a restore tested once.

**During the pilot (weekly)**
- [ ] Every resolved incident verified by an admin, with the true category and root cause.
- [ ] Review Model Monitoring (scope `live`): correction rate, low-confidence and LLM fallback rates, unfamiliar issues.
- [ ] Review `/llm/status`: provider errors, open circuits, OpenRouter free-tier cap, spend.
- [ ] Export `generate_monitoring_report.py` output for the period.
- [ ] Retrain only when the gates pass. Record the model version change.

**Exit criteria (suggested)**
- At least 30 real verified incidents overall, and at least 5 per main category, before quoting accuracy.
- Correction rate and per-category recall reviewed with a domain owner.
- No open high-severity risk from section 9.

---

## 9. Remaining production risks

| # | Risk | Severity | Mitigation / plan |
|---|---|---|---|
| R1 | **No real-world accuracy yet.** All accuracy figures come from labelled or synthetic sets | High (for claims) | Quote no accuracy until the section 8 exit criteria are met |
| R2 | **Out-of-distribution overconfidence.** Nonsense input such as "qwerty" received about 74 % ML confidence after calibration | Medium | The UI flags it as "unfamiliar" and admins verify everything. Plan: an OOD detector based on embedding distance, tuned on pilot data |
| R3 | **Frontend dependency advisories.** `npm audit` reports 1 high and 3 moderate (Vite 5 / esbuild dev server, React Router 6) | Medium | Dev-server issues do not apply to the nginx-served build. Upgrade plan below |
| R4 | **OpenRouter free tier:** 50-request cap and 14–23 s latency | Medium | Secondary only. Use a paid model or add credit before relying on failover at volume |
| R5 | **Groq spend unknown** until prices are set | Low | Set `GROQ_*_PRICE_PER_MTOK` |
| R6 | **Anthropic path untested live** in this phase (no key) | Low | Run `check_llm_connectivity.py` once a key is added |
| R7 | **Redis outage:** cross-worker live events are lost while Redis is down | Low | DB stays correct. Polling and reconnect resync heal it. Self-recovered in 17 s. Monitor Redis health |
| R8 | **Fixed-window rate limits** allow up to twice the limit across a window boundary | Low | Acceptable for the pilot. Sliding window later if needed |
| R9 | **Clock skew:** a 15 s step back in the Docker VM clock caused intermittent 401s | Low | Fixed with 30 s JWT leeway. Keep NTP on |
| R10 | **No automated backups** in the Compose stack | Medium | Operator schedules `pg_dump` (checklist) |
| R11 | Single host, with no high availability for PostgreSQL or Redis | Medium (for SLAs) | Fine for a controlled pilot. Managed PostgreSQL and Redis for general availability |

### R3 upgrade plan: Vite and React Router (trialled, *not* applied)
A trial on a scratch copy of the frontend (the project was not changed) used **vite 8.3.8 + @vitejs/plugin-react 6.3.0 + react-router-dom 7.18.6**. Results:
- build OK
- **`npm audit` 0 vulnerabilities**
- browser e2e 4 / 4
- UI audit 26 / 27. The single failure was a Recharts tooltip overflow, since fixed in the project.

Steps:
1. Raise the Node baseline: Vite 8 needs Node **^20.19 or ≥ 22.12**. Update CI and `Dockerfile.frontend`, which already uses node:22.
2. On a branch: `npm i -D vite@8.3.8 @vitejs/plugin-react@6.3.0 && npm i react-router-dom@7.18.6`.
3. Adopt React Router v7 behaviour. Check `startTransition` navigation and relative splat paths in the route tree ([src/App.jsx](../frontend/src/App.jsx)).
4. Gates: `npm run build`, `npm test` (8 tests), `npm audit`, `scripts/e2e_live_sync.py`, `scripts/ui_responsive_audit.py` at 390 px and 1440 px, then a manual check of login and redirect flows.
5. Merge only if every gate passes. Roll back by reverting the lockfile.

---

## 10. Updated readiness score

| Area | Before (production audit) | Now | Why |
|---|---|---|---|
| Infrastructure | PostgreSQL / Redis unverified | Verified | Compose stack with PostgreSQL 16, Redis 7.4, nginx and 2 workers, all validated |
| Data migration | Not available | Verified | Lossless and idempotent-safe, 0 mismatches |
| LLM integration | Anthropic only, not live | Live (Groq, OpenRouter) | Failover, redaction and honest billing |
| Real-time / multi-worker | Single process | Verified | 7 / 7 multi-worker checks. Outage behaviour known |
| Data hygiene | Mixed scopes | Separated | real / test / synthetic in metrics and training |
| Monitoring | Offline evaluation only | Dashboard and report | Waiting for real verified incidents |
| Security | 7 / 10 | Improved | Bandit 0 high / 0 medium. Security headers. Demo credentials dev-only. Accounts provisioned. Frontend advisories remain (R3) |
| Tests | — | 135 SQLite / 107 PostgreSQL / 8 frontend | All passing |

**Controlled-pilot readiness: 8.5 / 10.** Ready for a supervised pilot with real customers, as long as the section 8 go-live checklist is done.
**General-production readiness: 7.5 / 10.** That needs R1 (real accuracy evidence), R3 (dependency upgrade), R10 (backups) and R11 (high availability).
