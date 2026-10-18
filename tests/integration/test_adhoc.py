"""Ad-hoc-Themen gegen ein echtes PostgreSQL (PRD 7.4, F8)."""

import shutil
from pathlib import Path

import pytest

from parltopics.classify.adhoc import Keywords, activate, create, find_affairs
from parltopics.classify.queue import adhoc_task
from parltopics.db import migrate
from parltopics.inputs import SEARCH as INDEX
from parltopics.registry import file_hash, load_registry
from parltopics.registry.sync import sync_registry

pytestmark = pytest.mark.integration

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "tags_example.yaml"
KEYWORDS = Keywords(de=["Velo", "Velo fahren"], fr=["vélo"])
AFFAIRS = [
    (101, "CHE", "de", "Velowege\nDer Bund soll das Velo fördern."),  # Kandidat
    (102, "GE", "fr", "Pistes cyclables\nLe vélo en ville."),  # Kandidat auf Französisch
    (150, "CHE", "de", "Landwirtschaft\nDie Bauern brauchen Hilfe."),  # Stichprobe: 150 % 50
    (151, "CHE", "de", "Steuern\nDie Steuern sinken."),  # weder noch
]


@pytest.fixture
def settings(conn, repo_root, api_settings, tmp_path):
    registry_path = tmp_path / "tags.yaml"
    shutil.copy(FIXTURE, registry_path)
    migrate(conn, repo_root / "migrations")
    sync_registry(conn, load_registry(registry_path), file_hash(registry_path))
    for affair_id, body_key, language, text in AFFAIRS:
        conn.execute(
            "INSERT INTO affairs (id, body_key, begin_date, raw)"
            " VALUES (%s, %s, '2026-01-01', '{}')",
            (affair_id, body_key),
        )
        conn.execute(
            "INSERT INTO affair_inputs (affair_id, text, language, source, input_hash)"
            " VALUES (%s, %s, %s, 'texts', 'h')",
            (affair_id, text, language),
        )
    conn.execute(INDEX, ([affair[0] for affair in AFFAIRS],))
    return api_settings.model_copy(update={"registry_path": registry_path})


def test_candidates_come_from_the_keywords_and_the_sample_from_the_rest(conn, settings):
    assert find_affairs(conn, KEYWORDS, bodies=None, since=None) == ([102, 101], [150])
    assert find_affairs(conn, KEYWORDS, bodies=["CHE"], since=None) == ([101], [150])
    assert find_affairs(conn, Keywords(), bodies=None, since=None) == ([], [150])


def test_create_proposes_the_tag_and_opens_jobs_then_activate_releases_it(conn, settings):
    created = create(
        conn,
        settings,
        name_de="Velowege",
        definition_de="Geschäfte zu Velowegen und zum Veloverkehr",
        keywords=KEYWORDS,
        by="Mia",
        broader=["aps:6.1"],
    )
    assert (created.tag_id, created.candidates, created.sample) == ("adhoc:velowege", 2, 1)
    assert created.run.total == 3
    assert load_registry(settings.registry_path).get("adhoc:velowege").status == "proposed"
    status = "SELECT status FROM tags WHERE tag_id = 'adhoc:velowege'"
    assert conn.execute(status).fetchone() == ("proposed",)
    jobs = conn.execute(
        "SELECT affair_id FROM classification_jobs WHERE task = %s ORDER BY affair_id",
        (adhoc_task("adhoc:velowege"),),
    ).fetchall()
    assert jobs == [(101,), (102,), (150,)]
    run = conn.execute(
        "SELECT kind, params->'keywords'->'fr', params->>'by' FROM classification_runs"
        " WHERE id = %s",
        (created.run.run_id,),
    ).fetchone()
    assert run == ("adhoc", ["vélo"], "Mia")

    registry = activate(conn, settings, "adhoc:velowege")
    assert registry.get("adhoc:velowege").status == "active"
    assert conn.execute(status).fetchone() == ("active",)
