"""Einstellungen aus Umgebungsvariablen und .env (PRD 5, .env.example)."""

import datetime as dt
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from parltopics.search.navigate import Limits
from parltopics.wiki.tree import Thresholds


class Settings(BaseSettings):
    """Alle Einstellungen. Namen der LLM-Variablen folgen dem Hack-Apertus-Template."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    llm_name: str = "apertus-v1-5-8b"
    llm_name_large: str = "apertus-v1-5-70b"
    llm_base_url: str = "http://localhost:8080/v1"
    llm_api_key: SecretStr = SecretStr("")

    database_url: str = "postgresql://parltopics:parltopics@localhost:5432/parltopics"

    parallel_8b: int = Field(20, ge=1)  # Pilot 18.10.2026: 16 ohne Drosselung, Volllauf < 24 h
    parallel_70b: int = Field(12, ge=1)  # Curia-Check 19.10.2026: 12 parallel ohne Drosselung
    # single_70b: ein 70B-Durchlauf über alle Themen (Curia-Check: 84,6 % statt 72,7 %);
    # two_stage: Kapitel und Themen mit 8B, Eskalation an 70B (bis 19.10.2026).
    classify_mode: Literal["single_70b", "two_stage"] = "single_70b"
    confidence_threshold: float = Field(0.6, ge=0, le=1)
    job_timeout_seconds: int = Field(600, ge=30)
    heartbeat_seconds: int = Field(120, ge=5)
    # Seite der DVS-Liste (F12) und des Digitalisierungsteils im Bericht (F16), mit Unterseiten
    dvs_topic: str = "adhoc:digitalisierung-breit"

    registry_path: Path = Path("registry/tags.yaml")
    prompts_dir: Path = Path("prompts")
    migrations_dir: Path = Path("migrations")
    web_dist_dir: Path = Path("web/dist")

    # Seitenbaum und Zusammenfassungen (PRD 7.9): Schwellen und Eingabegrenzen.
    page_tag_changes: int = Field(5, ge=1)
    page_parent_changes: int = Field(1, ge=1)
    page_max_age_days: int = Field(7, ge=1)
    page_min_affairs: int = Field(3, ge=1)
    page_window_months: int = Field(12, ge=1)
    page_max_affairs: int = Field(80, ge=1)
    page_samples: int = Field(12, ge=0)
    page_prompt_max_tokens: int = Field(24000, ge=1000)

    # Navigationssuche (PRD 7.10)
    navigate_max_steps: int = Field(8, ge=1)
    navigate_min_relevance: float = Field(0.3, ge=0, le=1)
    navigate_max_branches: int = Field(2, ge=1)
    navigate_max_candidates: int = Field(20, ge=1)

    @field_validator("llm_base_url")
    @classmethod
    def _check_base_url(cls, value: str) -> str:
        parts = urlsplit(value)
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            raise ValueError("LLM_BASE_URL muss eine http(s)-URL mit Host sein")
        return value.rstrip("/")

    def page_thresholds(self) -> Thresholds:
        return Thresholds(
            tag_changes=self.page_tag_changes,
            parent_changes=self.page_parent_changes,
            max_age=dt.timedelta(days=self.page_max_age_days),
        )

    def navigate_limits(self) -> Limits:
        return Limits(
            max_steps=self.navigate_max_steps,
            min_relevance=self.navigate_min_relevance,
            max_branches=self.navigate_max_branches,
            max_candidates=self.navigate_max_candidates,
        )

    @property
    def llm_host(self) -> str:
        """Der einzige Host, den der LLM-Client zur Laufzeit ansprechen darf."""
        host = urlsplit(self.llm_base_url).hostname
        assert host is not None  # durch den Validator gesichert
        return host


@lru_cache
def get_settings() -> Settings:
    return Settings()
