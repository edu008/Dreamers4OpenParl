import pytest
from pydantic import ValidationError

from parltopics.config import Settings

ENV_NAMES = ["LLM_NAME", "LLM_NAME_LARGE", "LLM_BASE_URL", "LLM_API_KEY", "DATABASE_URL"]


def test_defaults_without_env(monkeypatch):
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    settings = Settings(_env_file=None)
    assert settings.llm_host == "localhost"
    assert settings.parallel_8b >= 1
    assert settings.confidence_threshold == 0.6


def test_template_variables_are_read(monkeypatch):
    monkeypatch.setenv("LLM_NAME", "apertus-8b")
    monkeypatch.setenv("LLM_BASE_URL", "https://keera.example/v1/")
    monkeypatch.setenv("LLM_API_KEY", "geheim")
    settings = Settings(_env_file=None)
    assert settings.llm_name == "apertus-8b"
    assert settings.llm_base_url == "https://keera.example/v1"
    assert settings.llm_host == "keera.example"
    assert settings.llm_api_key.get_secret_value() == "geheim"
    assert "geheim" not in repr(settings)


@pytest.mark.parametrize("url", ["keera.example/v1", "ftp://keera.example", "http:///v1"])
def test_invalid_base_url_is_rejected(url):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, llm_base_url=url)
