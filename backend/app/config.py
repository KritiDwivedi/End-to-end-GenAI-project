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
    openai_embedding_model: str = Field(default="text-embedding-3-small", alias="OPENAI_EMBEDDING_MODEL")
    openai_embedding_dimensions: int = Field(default=1536, alias="OPENAI_EMBEDDING_DIMENSIONS", gt=0)

    gemini_api_key: SecretStr | None = Field(default=None, alias="GEMINI_API_KEY")
    gemini_embedding_model: str = Field(default="gemini-embedding-2", alias="GEMINI_EMBEDDING_MODEL")
    gemini_embedding_dimensions: int = Field(default=1536, alias="GEMINI_EMBEDDING_DIMENSIONS", gt=0)
    gemini_chat_model: str = Field(default="google-gla:gemini-2.5-flash", alias="GEMINI_CHAT_MODEL")
    local_embedding_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        alias="LOCAL_EMBEDDING_MODEL",
    )
    local_embedding_dimensions: int = Field(default=384, alias="LOCAL_EMBEDDING_DIMENSIONS", gt=0)

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

    @property
    def gemini_api_key_value(self) -> str | None:
        return self.gemini_api_key.get_secret_value() if self.gemini_api_key is not None else None


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

# Some SDKs discover credentials from the environment; keep that bridge here so
# the rest of the application still treats this module as the config boundary.
os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key_value)
if settings.gemini_api_key_value:
    os.environ.setdefault("GEMINI_API_KEY", settings.gemini_api_key_value)
