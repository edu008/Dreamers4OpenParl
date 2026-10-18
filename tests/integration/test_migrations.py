"""Migrationen gegen ein echtes PostgreSQL (TEST_DATABASE_URL, z. B. aus `make db` oder CI)."""

import psycopg
import pytest

from parltopics.db import migrate

pytestmark = pytest.mark.integration


def test_migrations_apply_once(conn, repo_root):
    assert migrate(conn, repo_root / "migrations") == [
        "0001_init",
        "0002_one_active_label",
        "0002_wiki_skos",
    ]
    assert migrate(conn, repo_root / "migrations") == []
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = current_schema()"
        )
    }
    assert len(tables - {"schema_migrations"}) == 24
    assert {"affairs", "tags", "affair_tags", "classification_jobs", "agent_runs"} <= tables
    assert {"tag_labels", "tag_relations", "wiki_pages", "search_runs"} <= tables


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


def insert_tag(conn, tag_id: str, parent_id: str | None = None) -> None:
    conn.execute(
        "INSERT INTO tags (tag_id, scheme, status, parent_id, name_de, desc_de, match_text,"
        " content_hash, registry_version) VALUES (%s, %s, 'active', %s, %s, 'x', %s, 'h', 'v')",
        (tag_id, tag_id.split(":")[0], parent_id, tag_id, tag_id),
    )


def test_wiki_page_rules(conn, repo_root):
    migrate(conn, repo_root / "migrations")
    insert_tag(conn, "aps:6")
    page = "INSERT INTO wiki_pages (page_id, kind, tag_id, parent_id, path, title) VALUES %s"
    conn.execute(page % "('heart', 'heart', NULL, NULL, 'HEART.md', 'Heart')")
    conn.execute(page % "('aps:6', 'bereich', 'aps:6', 'heart', 'bereiche/aps-6-x.md', 'X')")
    for broken in (
        "('heart2', 'heart', NULL, NULL, 'HEART2.md', 'Zweite Heart-Seite')",
        "('aps:7', 'bereich', NULL, 'heart', 'bereiche/aps-7.md', 'Ohne tag_id')",
    ):
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(page % broken)
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute("UPDATE wiki_pages SET status = 'pending' WHERE page_id = 'aps:6'")


def test_tag_relations_keep_broader_and_related_apart(conn, repo_root):
    migrate(conn, repo_root / "migrations")
    insert_tag(conn, "aps:6")
    insert_tag(conn, "adhoc:x")
    relation = "INSERT INTO tag_relations (tag_id, target_id, relation) VALUES (%s, %s, %s)"
    conn.execute(relation, ("adhoc:x", "aps:6", "broader"))
    with pytest.raises(psycopg.errors.UniqueViolation):
        conn.execute(relation, ("adhoc:x", "aps:6", "related"))
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute(relation, ("aps:6", "aps:6", "related"))


def test_search_without_results_has_no_answer(conn, repo_root):
    migrate(conn, repo_root / "migrations")
    run = "INSERT INTO search_runs (query, affair_ids, answer, status) VALUES ('q', %s, %s, %s)"
    conn.execute(run, ([1], "Antwort", "ok"))
    conn.execute(run, ([], None, "no_results"))
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute(run, ([], "erfunden", "no_results"))
