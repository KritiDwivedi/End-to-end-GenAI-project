from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """Application settings loaded from the process environment."""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    supabase_url: str = Field(..., alias="SUPABASE_URL")
    supabase_anon_key: SecretStr = Field(..., alias="SUPABASE_ANON_KEY")
    supabase_service_role_key: SecretStr = Field(..., alias="SUPABASE_SERVICE_ROLE_KEY")

    database_url: SecretStr = Field(..., alias="DATABASE_URL")

    openai_api_key: SecretStr = Field(..., alias="OPENAI_API_KEY")
    openai_embedding_model: str = Field(
        default="text-embedding-3-small",
        alias="OPENAI_EMBEDDING_MODEL",
    )
    openai_embedding_dimensions: int = Field(
        default=1536,
        alias="OPENAI_EMBEDDING_DIMENSIONS",
        gt=0,
    )

    allowed_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:5173"],
        alias="ALLOWED_ORIGINS",
    )

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, value: Any) -> list[str] | Any:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("supabase_url")
    @classmethod
    def strip_trailing_supabase_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @property
    def database_url_value(self) -> str:
        return self.database_url.get_secret_value()

    @property
    def supabase_anon_key_value(self) -> str:
        return self.supabase_anon_key.get_secret_value()

    @property
    def supabase_service_role_key_value(self) -> str:
        return self.supabase_service_role_key.get_secret_value()

    @property
    def openai_api_key_value(self) -> str:
        return self.openai_api_key.get_secret_value()


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

# Some SDKs discover credentials from the environment; keep that bridge here so
# the rest of the application still treats this module as the config boundary.
os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key_value)
