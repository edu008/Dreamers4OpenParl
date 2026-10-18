"""Migrationen gegen ein echtes PostgreSQL (TEST_DATABASE_URL, z. B. aus `make db` oder CI)."""

import os
import uuid

import psycopg
import pytest

from parltopics.db import migrate

pytestmark = pytest.mark.integration


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


def test_migrations_apply_once(conn, repo_root):
    assert migrate(conn, repo_root / "migrations") == ["0001_init", "0002_one_active_label"]
    assert migrate(conn, repo_root / "migrations") == []
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = current_schema()"
        )
    }
    assert len(tables - {"schema_migrations"}) == 17
    assert {"affairs", "tags", "affair_tags", "classification_jobs", "agent_runs"} <= tables


def test_only_one_active_label_per_key(conn, repo_root):
    migrate(conn, repo_root / "migrations")
    conn.execute("INSERT INTO affairs (id, body_key, raw) VALUES (1, 'CHE', '{}')")
    conn.execute(
        "INSERT INTO tags (tag_id, scheme, status, name_de, desc_de, match_text, content_hash,"
        " registry_version) VALUES ('adhoc:x', 'adhoc', 'active', 'X', 'x', 'x', 'h', 'v')"
    )
    label = (
        "INSERT INTO affair_tags (affair_id, tag_id, scheme, confidence, task, stage,"
        " model_version, prompt_version, registry_version, input_hash)"
        " VALUES (1, 'adhoc:x', 'adhoc', 0.8, %s, %s, 'm', %s, 'v', %s)"
    )
    conn.execute(label, ("classify:aps", "8b", "p1", "i1"))
    # Gleiches Tag aus einer anderen Aufgabe, mit neuem Text oder neuem Prompt: ebenfalls gesperrt.
    for other in [
        ("classify:aps", "70b", "p1", "i1"),
        ("reclassify:adhoc:x", "8b", "p1", "i1"),
        ("classify:aps", "8b", "p2", "i2"),
    ]:
        with pytest.raises(psycopg.errors.UniqueViolation):
            conn.execute(label, other)
    conn.execute("UPDATE affair_tags SET status = 'superseded' WHERE stage = '8b'")
    conn.execute(label, ("reclassify:adhoc:x", "8b", "p1", "i1"))


def test_pending_job_needs_owner(conn, repo_root):
    migrate(conn, repo_root / "migrations")
    conn.execute("INSERT INTO affairs (id, body_key, raw) VALUES (1, 'CHE', '{}')")
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute(
            "INSERT INTO classification_jobs (affair_id, task, status)"
            " VALUES (1, 'classify:aps', 'pending')"
        )
