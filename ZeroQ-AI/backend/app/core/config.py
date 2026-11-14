from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/zeroq_ai"
    SECRET_KEY: str = "zeroq-ai-dev-secret-key-2024-hackathon"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE_MB: int = 10
    ENVIRONMENT: str = "development"

    class Config:
        env_file = ".env"

settings = Settings()
