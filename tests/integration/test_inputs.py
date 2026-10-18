"""Klassifikationstext gegen ein echtes PostgreSQL (PRD F3, F18)."""

from datetime import date

import pytest

from parltopics.db import migrate
from parltopics.inputs import build_inputs

pytestmark = pytest.mark.integration


def seed(conn) -> None:
    affair = (
        "INSERT INTO affairs (id, body_key, title_de, title_fr, begin_date, raw)"
        " VALUES (%s, %s, %s, %s, %s, '{}')"
    )
    conn.execute(affair, (1, "CHE", "Motion Digitalisierung", None, "2026-03-01"))
    conn.execute(affair, (2, "ZH", "Anfrage Velowege", None, "2026-02-01"))
    conn.execute(affair, (3, "GE", None, "Question sur les transports publics", "2026-01-01"))
    conn.execute(affair, (4, "CHE", None, None, "2026-01-01"))
    text = (
        "INSERT INTO affair_texts (id, affair_id, text_type, language, text, raw)"
        " VALUES (%s, 1, %s, 'de', %s, '{}')"
    )
    conn.execute(text, (10, "Eingereichter Text", "<p>Der Bundesrat wird beauftragt.</p>"))
    conn.execute(text, (11, "Antwort BR / Büro", "<p>Der Bundesrat beantragt Ablehnung.</p>"))
    conn.execute(
        "INSERT INTO affair_docs (id, parent_type, parent_id, doc_date, language, text, raw)"
        " VALUES (21, 'affair', 2, '2026-03-01', 'de', 'Späteres Dokument', '{}'),"
        " (20, 'affair', 2, '2026-02-02', 'de', 'Erstes Dokument', '{}')"
    )


def test_inputs_are_built_once_and_a_changed_text_reopens_done_jobs(conn, repo_root):
    migrate(conn, repo_root / "migrations")
    seed(conn)
    assert build_inputs(conn, since=date(2026, 2, 15)).changed == 1
    first_two = build_inputs(conn, limit=2)
    assert (first_two.changed, first_two.unchanged) == (1, 1)
    rest = build_inputs(conn)
    assert (rest.changed, rest.unchanged, rest.skipped) == (1, 2, 1)

    rows = {
        row[0]: row[1:]
        for row in conn.execute("SELECT affair_id, text, language, source FROM affair_inputs")
    }
    assert rows[1] == ("Motion Digitalisierung\nDer Bundesrat wird beauftragt.", "de", "texts")
    assert rows[2] == ("Anfrage Velowege\nErstes Dokument", "de", "first_doc")
    assert rows[3] == ("Question sur les transports publics", "fr", "title_only")
    again = build_inputs(conn)
    assert (again.changed, again.unchanged) == (0, 3)

    conn.execute(
        "INSERT INTO classification_jobs (affair_id, task, status, attempts)"
        " VALUES (1, 'classify:aps', 'done', 1)"
    )
    conn.execute("UPDATE affair_texts SET text = '<p>Neuer Text.</p>' WHERE id = 10")
    changed = build_inputs(conn, bodies=["CHE"])
    assert (changed.changed, changed.reopened) == (1, 1)
    job = "SELECT status, attempts FROM classification_jobs"
    assert conn.execute(job).fetchone() == ("open", 0)
    event = "SELECT from_status, to_status, reason FROM job_events"
    assert conn.execute(event).fetchone() == ("done", "open", "input_changed")


def test_inputs_fill_the_full_text_search_once_per_text(conn, repo_root):
    migrate(conn, repo_root / "migrations")
    seed(conn)
    assert build_inputs(conn).indexed == 3
    docs = dict(conn.execute("SELECT affair_id, language FROM search_documents").fetchall())
    assert docs == {1: "de", 2: "de", 3: "fr"}
    hit = "SELECT affair_id FROM search_documents WHERE document @@ plainto_tsquery(%s, %s)"
    assert conn.execute(hit, ("german", "Bundesrates")).fetchall() == [(1,)]  # Stammform
    assert conn.execute(hit, ("french", "transport")).fetchall() == [(3,)]
    title = "SELECT ts_filter(document, '{a}') FROM search_documents WHERE affair_id = 1"
    assert conn.execute(title).fetchone()[0] == "'digitalisier':2A 'motion':1A"
    assert build_inputs(conn).indexed == 0
    stamps = "SELECT count(*) FROM search_documents JOIN affair_inputs USING (affair_id)"
    assert conn.execute(f"{stamps} WHERE updated_at = built_at").fetchone() == (3,)

    conn.execute("UPDATE affair_texts SET text = '<p>Cybersicherheit stärken.</p>' WHERE id = 10")
    assert build_inputs(conn).indexed == 1
    assert conn.execute(hit, ("german", "Cybersicherheit")).fetchall() == [(1,)]
    conn.execute("DELETE FROM search_documents WHERE affair_id = 2")  # fehlt: wird nachgeholt
    assert build_inputs(conn).indexed == 1
