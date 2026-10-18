"""Ad-hoc-Themen gegen ein echtes PostgreSQL (PRD 7.4, F8)."""

import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from parltopics.api.app import create_app
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


def test_adhoc_endpoints_preview_create_and_activate(conn, settings):
    body = {"keywords": {"de": ["Velo"], "fr": ["vélo"]}}
    topic = {
        **body,
        "name_de": "Velowege",
        "description_de": "Geschäfte zu Velowegen und zum Veloverkehr",
        "broader": ["aps:6.1"],
        "user_name": "Mia",
    }
    with TestClient(create_app(settings)) as client:
        preview = client.post("/v1/adhoc/preview", json=body).json()
        assert (preview["candidates"], preview["sample"]) == (2, 1)
        assert [example["affair_id"] for example in preview["examples"]] == [102, 101]

        created = client.post("/v1/adhoc", json=topic)
        assert created.status_code == 200
        assert {key: created.json()[key] for key in ("tag_id", "jobs", "candidates")} == {
            "tag_id": "adhoc:velowege",
            "jobs": 3,
            "candidates": 2,
        }
        assert client.post("/v1/adhoc", json=topic).status_code == 409
        unknown = {**topic, "name_de": "Velorouten", "broader": ["aps:9.9"]}
        assert client.post("/v1/adhoc", json=unknown).status_code == 422

        conn.execute(
            "INSERT INTO affair_tags (affair_id, tag_id, scheme, confidence, task, stage,"
            " model_version, prompt_version, registry_version, input_hash) VALUES (101,"
            " 'adhoc:velowege', 'adhoc', 0.8, 'classify:adhoc:velowege', '8b', 'm', 'p', 'v', 'h')"
        )
        (label,) = client.get("/v1/affairs/101/topics").json()["labels"]
        assert label["tag_status"] == "proposed"  # vorläufiger Treffer
        assert client.get("/v1/pages/adhoc:velowege").status_code == 404

        activated = client.post("/v1/adhoc/adhoc:velowege/activate")
        assert activated.json()["status"] == "active"
        assert client.post("/v1/adhoc/adhoc:velowege/activate").status_code == 409
        assert client.post("/v1/adhoc/aps:6.1.9/activate").status_code == 404
        assert client.get("/v1/pages/adhoc:velowege").status_code == 200
        (label,) = client.get("/v1/affairs/101/topics").json()["labels"]
        assert label["tag_status"] == "active"


def test_cli_creates_and_activates_an_adhoc_topic(conn, settings, tmp_path, monkeypatch):
    from parltopics.cli import app

    description = tmp_path / "beschreibung.txt"
    description.write_text("Geschäfte zu Velowegen und zum Veloverkehr", encoding="utf-8")
    keywords = tmp_path / "stichwoerter.json"
    keywords.write_text(json.dumps({"de": ["Velo"], "fr": ["vélo"]}), encoding="utf-8")
    monkeypatch.setattr("parltopics.cli.get_settings", lambda: settings)
    runner = CliRunner()
    options = ["--description-file", str(description), "--keywords-file", str(keywords)]
    result = runner.invoke(app, ["adhoc", "Velowege", *options, "--body", "CHE", "--yes"])
    assert result.exit_code == 0, result.output
    assert "1 Kandidaten, 1 Geschäfte in der Stichprobe" in result.output
    assert "adhoc:velowege angelegt" in result.output
    result = runner.invoke(app, ["registry", "activate", "adhoc:velowege"])
    assert (result.exit_code, "adhoc:velowege ist aktiv" in result.output) == (0, True)
