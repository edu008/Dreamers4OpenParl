from pathlib import Path

import pytest

from parltopics.config import Settings

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture
def settings() -> Settings:
    """Feste Einstellungen ohne .env, mit einem Test-Host als LLM-Endpunkt."""
    return Settings(
        _env_file=None,
        llm_base_url="http://llm.test/v1",
        llm_name="test-8b",
        llm_name_large="test-70b",
        llm_api_key="secret",
        registry_path=REPO_ROOT / "registry" / "tags.yaml",
        prompts_dir=REPO_ROOT / "prompts",
        migrations_dir=REPO_ROOT / "migrations",
    )
