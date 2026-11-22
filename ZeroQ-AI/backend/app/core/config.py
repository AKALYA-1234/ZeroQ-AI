from typing import List, Optional

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Development-only signing key. Rejected when ENVIRONMENT=production (see validator below).
DEV_SECRET_KEY = "zeroq-ai-dev-secret-key-2024-hackathon"
MIN_PRODUCTION_SECRET_LENGTH = 32


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
    # LLM fallback (Claude). The Anthropic SDK reads ANTHROPIC_API_KEY itself;
    # LLM_ENABLED lets operators switch the fallback off entirely.
    LLM_ENABLED: bool = True
    LLM_MODEL: str = "claude-opus-5-5"
    LLM_TIMEOUT_SECONDS: float = 45.0
    # Circuit breaker: after this many consecutive LLM failures, skip the LLM for the cooldown.
    LLM_CIRCUIT_FAILURES: int = 3
    LLM_CIRCUIT_COOLDOWN_SECONDS: int = 120
    # List prices (USD per million tokens) used only to *estimate* LLM spend.
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

    # ── Business-impact assumptions (documented; unset = not reported) ──
    IMPACT_UNIT_COST_INR: Optional[float] = None
    IMPACT_DOWNTIME_COST_PER_HOUR_INR: Optional[float] = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def _production_guards(self):
        if self.ENVIRONMENT.lower() == "production":
            if self.SECRET_KEY == DEV_SECRET_KEY or len(self.SECRET_KEY) < MIN_PRODUCTION_SECRET_LENGTH:
                raise ValueError(
                    f"SECRET_KEY must be set to a random value of at least {MIN_PRODUCTION_SECRET_LENGTH} "
                    "characters in production (e.g. `python -c \"import secrets; print(secrets.token_urlsafe(48))\"`).")
        return self

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
