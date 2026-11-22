import os
from typing import List, Optional

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Development-only signing key. Rejected when ENVIRONMENT=production (see validator below).
DEV_SECRET_KEY = "zeroq-ai-dev-secret-key-2024-hackathon"
MIN_PRODUCTION_SECRET_LENGTH = 32
_BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
# Project-root .env first, backend/.env overrides it. Both are gitignored.
ENV_FILES = (os.path.join(_BACKEND_DIR, "..", ".env"), os.path.join(_BACKEND_DIR, ".env"))


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/zeroq_ai"
    SECRET_KEY: str = DEV_SECRET_KEY
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE_MB: int = 10
    ENVIRONMENT: str = "development"

    # ── Deployment ───────────────────────────────────────────────────────
    # Shared bus for real-time events + rate limits across workers. Unset = in-process (single worker).
    REDIS_URL: Optional[str] = None
    # Comma-separated origins allowed for cross-origin browser access. Unset = same-origin only.
    CORS_ORIGINS: str = ""
    # Interactive API docs; disabled automatically in production unless explicitly enabled.
    API_DOCS_ENABLED: Optional[bool] = None

    # ── Issue intelligence ────────────────────────────────────────────────
    # LLM fallback. Providers are tried in order: LLM_PROVIDER first, then LLM_FALLBACK_PROVIDERS
    # (only those with a key). Keys are SecretStr: never logged, never sent to the frontend.
    LLM_ENABLED: bool = True
    LLM_PROVIDER: str = "groq"
    LLM_FALLBACK_PROVIDERS: str = "openrouter,anthropic"
    LLM_FAILOVER_ENABLED: bool = True
    LLM_MAX_RETRIES: int = 2                 # per provider, for 429 / 5xx / timeouts
    LLM_RETRY_MAX_WAIT_SECONDS: float = 10.0
    GROQ_API_KEY: Optional[SecretStr] = None
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    GROQ_INPUT_PRICE_PER_MTOK: Optional[float] = None    # set to estimate spend; unset = unknown
    GROQ_OUTPUT_PRICE_PER_MTOK: Optional[float] = None
    OPENROUTER_API_KEY: Optional[SecretStr] = None
    OPENROUTER_MODEL: Optional[str] = None
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_INPUT_PRICE_PER_MTOK: Optional[float] = None
    OPENROUTER_OUTPUT_PRICE_PER_MTOK: Optional[float] = None
    OPENROUTER_APP_TITLE: str = "ZeroQ AI"
    ANTHROPIC_API_KEY: Optional[SecretStr] = None   # falls back to the process environment
    LLM_MODEL: str = "claude-opus-5-5"               # Anthropic model
    LLM_TIMEOUT_SECONDS: float = 45.0
    # Circuit breaker: after this many consecutive LLM failures, skip the LLM for the cooldown.
    LLM_CIRCUIT_FAILURES: int = 3
    LLM_CIRCUIT_COOLDOWN_SECONDS: int = 120
    # Anthropic list prices (USD per million tokens) used only to *estimate* spend.
    LLM_INPUT_PRICE_PER_MTOK: float = 4.0
    LLM_OUTPUT_PRICE_PER_MTOK: float = 20.0
    # Below this classifier probability the prediction is treated as low-confidence.
    ML_CONFIDENCE_THRESHOLD: float = 0.55
    # Below this probability, with no LLM and no symptom rule, the issue is left undetermined.
    ML_MIN_GUESS_CONFIDENCE: float = 0.35
    # Below this best-match similarity the issue is treated as unfamiliar.
    MIN_HISTORICAL_SIMILARITY: float = 0.20
    # "auto" tries a locally cached sentence-transformers model, else TF-IDF.
    EMBEDDING_BACKEND: str = "auto"
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    # Minimum new admin-verified incidents before a retrain is allowed (unless forced).
    RETRAIN_MIN_NEW_SAMPLES: int = 20

    # Submissions from these accounts are tagged data_origin="test" and excluded from real-world
    # metrics and model training. Comma-separated emails and/or whole domains ("@example.com").
    PILOT_TEST_EMAILS: str = "demo@customer.com"

    # ── Business-impact assumptions (documented; unset = not reported) ──
    IMPACT_UNIT_COST_INR: Optional[float] = None
    IMPACT_DOWNTIME_COST_PER_HOUR_INR: Optional[float] = None

    # env_ignore_empty: container/compose files pass unset optional values as "" (e.g. IMPACT_UNIT_COST_INR=);
    # treat those as "not set" instead of failing validation. To disable an LLM provider use LLM_ENABLED=false
    # or LLM_PROVIDER / LLM_FALLBACK_PROVIDERS, not an empty key.
    model_config = SettingsConfigDict(env_file=ENV_FILES, env_file_encoding="utf-8", extra="ignore",
                                      env_ignore_empty=True)

    @model_validator(mode="after")
    def _production_guards(self):
        if self.ENVIRONMENT.lower() == "production":
            if self.SECRET_KEY == DEV_SECRET_KEY or len(self.SECRET_KEY) < MIN_PRODUCTION_SECRET_LENGTH:
                raise ValueError(
                    f"SECRET_KEY must be set to a random value of at least {MIN_PRODUCTION_SECRET_LENGTH} "
                    "characters in production (e.g. `python -c \"import secrets; print(secrets.token_urlsafe(48))\"`).")
        return self

    @property
    def pilot_test_emails(self) -> List[str]:
        return [e.strip().lower() for e in self.PILOT_TEST_EMAILS.split(",") if e.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def docs_enabled(self) -> bool:
        return self.API_DOCS_ENABLED if self.API_DOCS_ENABLED is not None else not self.is_production


settings = Settings()
