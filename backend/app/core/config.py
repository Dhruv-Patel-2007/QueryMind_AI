"""Application Configuration Module for QueryMind AI 2.0."""

import os
from functools import lru_cache
from typing import List
from pydantic import BaseModel


class Settings(BaseModel):
    """Application settings and runtime constants."""

    PROJECT_NAME: str = os.getenv("PROJECT_NAME", "QueryMind AI 2.0")
    VERSION: str = os.getenv("VERSION", "2.0.0")
    API_V1_STR: str = os.getenv("API_V1_STR", "/api")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = os.getenv("DEBUG", "true").lower() in ("true", "1", "yes")

    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", "8000"))

    CORS_ORIGINS: List[str] = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        ).split(",")
        if origin.strip()
    ]

    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./data/academic.db")
    CONTEXT_TTL_SECONDS: int = int(os.getenv("CONTEXT_TTL_SECONDS", "600"))
    SESSION_CLEANUP_INTERVAL_SECONDS: int = int(os.getenv("SESSION_CLEANUP_INTERVAL_SECONDS", "60"))


@lru_cache()
def get_settings() -> Settings:
    """Returns cached application settings instance."""
    return Settings()

