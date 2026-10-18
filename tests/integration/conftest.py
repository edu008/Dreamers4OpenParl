"""Fixture für Integrationstests: eigenes Schema je Test in TEST_DATABASE_URL."""

import os
import uuid
from pathlib import Path

import psycopg
import pytest
from psycopg.conninfo import make_conninfo

from parltopics.config import Settings

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "tags_example.yaml"


@pytest.fixture
def conn():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL ist nicht gesetzt")
    schema = f"test_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(url, autocommit=True) as connection:
        connection.execute(f'CREATE SCHEMA "{schema}"')
        connection.execute(f'SET search_path TO "{schema}", public')
        try:
            yield connection
        finally:
            connection.execute(f'DROP SCHEMA "{schema}" CASCADE')


@pytest.fixture
def api_settings(conn, tmp_path) -> Settings:
    """Einstellungen für eine App auf dem Schema dieses Tests, mit dem Review-Token «geheim»."""
    schema = conn.execute("SELECT current_schema()").fetchone()[0]
    url = make_conninfo(os.environ["TEST_DATABASE_URL"], options=f"-c search_path={schema},public")
    return Settings(
        _env_file=None,
        database_url=url,
        web_dist_dir=tmp_path,
        registry_path=FIXTURE,
        review_token="geheim",
    )
