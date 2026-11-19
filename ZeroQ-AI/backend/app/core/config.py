from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/zeroq_ai"
    SECRET_KEY: str = "zeroq-ai-dev-secret-key-2024-hackathon"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE_MB: int = 10
    ENVIRONMENT: str = "development"

    # ── Issue intelligence ────────────────────────────────────────────────
    # LLM fallback (Claude). The Anthropic SDK reads ANTHROPIC_API_KEY itself;
    # LLM_ENABLED lets operators switch the fallback off entirely.
    LLM_ENABLED: bool = True
    LLM_MODEL: str = "claude-opus-5-5"
    LLM_TIMEOUT_SECONDS: float = 45.0
    # Below this classifier probability the prediction is treated as low-confidence.
    ML_CONFIDENCE_THRESHOLD: float = 0.55
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

settings = Settings()
