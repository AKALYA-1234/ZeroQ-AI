# ZeroQ AI: Multilingual, Evidence-Backed Quality Intelligence for Food & CPG Manufacturing

## Abstract

Food and consumer-packaged-goods (CPG) plants learn about many quality failures from customer complaints: torn seals, insects, foreign matter, short weights, off odours. These complaints reach the quality team weeks after the batch has shipped. They arrive in whatever language the customer speaks, and often in a code-mixed form like Tamil-English ("Tanglish") or Hindi-English ("Hinglish"). A quality engineer then has to read each one, classify it, search past investigations for similar cases, guess the root cause, and decide on a corrective action. All of this is manual and inconsistent, and its knowledge leaves when people do. Repeat defects follow.

**ZeroQ AI** turns this manual loop into a closed, AI-assisted workflow. A customer describes a problem in their own words, in any of 20 languages or 5 Indian code-mixed varieties. ZeroQ AI then:

1. Detects the language and translates it into English.
2. Extracts the symptoms and classifies the issue into a manufacturing defect taxonomy.
3. Retrieves similar historical incidents.
4. Recommends a probable root cause and a corrective action.

Every recommendation comes with the evidence behind it: the past incidents it was based on, the share of each candidate root cause, and the measured success rate of each previous fix. A quality admin confirms or corrects the AI, writes an explanation, and resolves the case. The customer sees the update live and rates the resolution. Each verified resolution becomes labelled training data, but a retrained model is promoted only if it passes evaluation gates.

ZeroQ AI was built on a 19-year manufacturing dataset (2008–2026). It covers:
- 20 products, 5 facilities, 15 production lines and 40 materials
- 24,000 production batches
- 37,245 quality inspections
- 6,000 customer complaints
- 4,000 root-cause investigations
- 3,500 CAPA records

The dataset is synthetic. The system labels it as such everywhere and keeps it strictly apart from real-world performance metrics.

## Problem

- **Slow, reactive detection.** Defects surface as complaints 30–90 days after shipping, by which time companion units from the same batch are already in the market.
- **Language barrier.** In India and other multilingual markets, customers write in native scripts or romanised, code-mixed text. Keyword systems and English-only models misread or drop these complaints.
- **Lost institutional knowledge.** Past root-cause investigations and CAPA outcomes sit in records nobody searches. The same fixes are re-invented, and the same ineffective fixes are repeated.
- **Untrustworthy AI.** Black-box classifiers produce a label without a reason. Generative models can confidently invent root causes. Neither is acceptable in a regulated food-safety context.

## Solution

ZeroQ AI has two portals over a shared intelligence engine.

**Customer portal**
- Submit a complaint in any language, with an optional batch code and photos.
- Track it through a four-stage live milestone tracker.
- Read the quality team's plain-language explanation and rate the resolution.

**Quality admin portal**
- An executive KPI dashboard.
- A complaint queue with AI verification and resolution.
- Root-cause analysis (Ishikawa / 5-Why), risk assessment and CAPA management.
- A batch-level complaint-risk predictor.
- AI Insights & Impact analytics.
- A Model Monitoring dashboard.

### How a complaint is analysed

1. **Language understanding.** Offline script and lexicon detection identifies:
   - **20 languages**: English, Tamil, Hindi, Telugu, Malayalam, Kannada, Bengali, Gujarati, Punjabi, Odia, Arabic/Urdu, Chinese, Japanese, Korean, Thai, Russian, Spanish, French, German, plus an "undetermined" fallback.
   - **5 code-mixed varieties**: Tanglish, Hinglish, Tenglish, Manglish and Kanglish.

   An LLM translates the text into English when one is available. Otherwise, a domain glossary of 28 manufacturing concepts produces an English gloss. The customer's original words are always stored unchanged.
2. **Symptom extraction and classification.** A TF-IDF (word 1–2-gram and character 3–5-gram) logistic-regression classifier predicts the category, subcategory and severity, with a calibrated confidence score. Its eight categories are Packaging, Sensory, Physical, Foreign Matter, Weight/Quantity, Process, Infestation, and Other.
3. **Evidence retrieval.** Similarity search over resolved historical incidents returns the closest cases. It also returns:
   - each candidate root cause's similarity-weighted share
   - each past corrective action's success rate, computed from CAPA effectiveness reviews (effective = 100%, partially effective = 50%, ineffective = 0%)
4. **Confidence-gated LLM fallback.** If ML confidence falls below a threshold (0.55 by default), a provider-agnostic LLM layer is consulted. The primary is Groq (`gpt-oss-120b`), followed by OpenRouter and Anthropic. Its output is constrained to a JSON schema, and the layer has retries, per-provider circuit breakers and automatic failover. If every provider fails, the system falls back to rule-based analysis and records why. **It never fabricates a prediction.**
5. **Privacy by design.** Names, emails and phone numbers are redacted before any text leaves the server. Operational identifiers such as batch codes and line numbers are kept. API keys never reach the browser.

### Human-in-the-loop learning

The admin's verification panel shows the AI's prediction next to the evidence. Confirming or correcting the prediction (category, root cause, action taken, explanation for the customer, units contained) does three things:
- It resolves the case.
- It notifies the customer in real time, over WebSocket with Redis pub/sub across workers, falling back to polling.
- It stores a verified label.

Retraining is explicit. A candidate model is evaluated on held-out data and promoted only if it does not regress, so there is no silent self-modification.

### Honest metrics

Every record carries a data origin: **synthetic** (imported history), **real** (live customers) or **test** (designated test accounts). Model Monitoring reports real-world accuracy only from admin-verified real incidents, with Wilson confidence intervals and minimum sample sizes: 30 overall and 5 per group. Below those thresholds it shows "insufficient data" instead of a number. Business-impact figures (units saved, downtime avoided, cost) are admin-reported or computed from documented assumptions, never silently estimated.

## Technology

| Layer | Stack |
|---|---|
| Frontend | React 18, Vite, Tailwind CSS, Recharts, React Router |
| Backend | FastAPI, SQLAlchemy 2, Pydantic v2, PyJWT and bcrypt authentication, rate limiting |
| ML / NLP | scikit-learn (TF-IDF + logistic regression issue classifier), XGBoost (batch complaint-risk model), offline language detection and glossary |
| LLM | Provider-agnostic adapter: Groq → OpenRouter → Anthropic, JSON-schema outputs, PII redaction |
| Data | PostgreSQL in production, SQLite for local development, verified migration tooling |
| Real time | WebSockets with Redis pub/sub for multi-worker delivery |
| Deployment | Docker Compose pilot stack (nginx, backend workers, PostgreSQL, Redis) |

## Results and validation

- **Classifier accuracy (offline benchmark):** 97.5% category accuracy on an independent 79-item labelled test set. The LLM alone scored 92.4%. The combined ML → LLM pipeline classified all 79 correctly. These figures are benchmarks, not field results: the test set is small and the glossary was tuned on it.
- **Live LLM integration:** Groq and OpenRouter were each verified against the real APIs. Groq answers in about 2 s, and failover to OpenRouter works. Anthropic is supported in code but has not been tested live.
- **Data migration:** SQLite → PostgreSQL migration of 81,356 rows with matching row counts and checksums, and zero mismatches.
- **Scale-out:** multi-worker real-time delivery passed 7/7 checks, both on a host and in containers behind nginx.
- **Quality gates:**
  - 135 backend tests pass on SQLite and 107 on PostgreSQL.
  - Frontend tests and the production build pass.
  - The Bandit static scan reports no high- or medium-severity findings.
  - Browser end-to-end flows pass, and a 30/30 responsive-layout audit passes from 390 px to 1440 px.
- **Real-world accuracy:** not yet measured. No real customer incidents have been verified, so the platform reports this as N/A by design.

## Impact

ZeroQ AI shortens the path from a customer's words to a verified root cause. Customers who don't write formal English are fully served. Every closed case keeps the organisation's knowledge and makes the next prediction better. Because it shows its evidence, refuses to invent answers, and measures itself only on verified real data, quality teams can trust it in a food-safety setting.

## Limitations and next steps

- **Real-world accuracy:** this needs a pilot that collects at least 30 verified real incidents.
- **Overconfidence on unfamiliar input:** the classifier can be overconfident on nonsense or out-of-domain text. These cases are flagged in the UI, and calibration is planned.
- **Production operations:** a controlled pilot still needs TLS, automated backups, and a supported frontend toolchain upgrade (Vite and React Router security advisories).
- **Next features:** image-based defect evidence, batch-level early warning linking complaints to the risk model, and per-plant model variants.

**Readiness:** 8.5/10 for a controlled pilot and 7.5/10 for general production, by the project's own audit ([PILOT_READINESS.md](PILOT_READINESS.md)).
