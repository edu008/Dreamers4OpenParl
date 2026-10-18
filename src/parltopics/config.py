"""Einstellungen aus Umgebungsvariablen und .env (PRD 5, .env.example)."""

from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Alle Einstellungen. Namen der LLM-Variablen folgen dem Hack-Apertus-Template."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    llm_name: str = "swiss-ai/Apertus-v1.5-8B"
    llm_name_large: str = "swiss-ai/Apertus-v1.5-70B"
    llm_base_url: str = "http://localhost:8080/v1"
    llm_api_key: SecretStr = SecretStr("")

    database_url: str = "postgresql://parltopics:parltopics@localhost:5432/parltopics"

    parallel_8b: int = Field(16, ge=1)
    parallel_70b: int = Field(4, ge=1)
    confidence_threshold: float = Field(0.6, ge=0, le=1)
    job_timeout_seconds: int = Field(600, ge=30)
    heartbeat_seconds: int = Field(120, ge=5)

    registry_path: Path = Path("registry/tags.yaml")
    prompts_dir: Path = Path("prompts")
    migrations_dir: Path = Path("migrations")

    review_token: SecretStr | None = None

    @field_validator("llm_base_url")
    @classmethod
    def _check_base_url(cls, value: str) -> str:
        parts = urlsplit(value)
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            raise ValueError("LLM_BASE_URL muss eine http(s)-URL mit Host sein")
        return value.rstrip("/")

    @property
    def llm_host(self) -> str:
        """Der einzige Host, den der LLM-Client zur Laufzeit ansprechen darf."""
        host = urlsplit(self.llm_base_url).hostname
        assert host is not None  # durch den Validator gesichert
        return host


@lru_cache
def get_settings() -> Settings:
    return Settings()
