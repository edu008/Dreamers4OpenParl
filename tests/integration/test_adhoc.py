"""Ad-hoc-Themen gegen ein echtes PostgreSQL (PRD 7.4, F8)."""

import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from parltopics.api.app import create_app
from parltopics.classify.adhoc import Keywords, activate, create, find_affairs, retire
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
TOPIC = {"name_de": "Velowege", "definition_de": "Geschäfte zu Velowegen und zum Veloverkehr"}
TASK = adhoc_task("adhoc:velowege")


def label(conn, affair_id):
    conn.execute(
        "INSERT INTO affair_tags (affair_id, tag_id, scheme, confidence, task, stage,"
        " model_version, prompt_version, registry_version, input_hash) VALUES (%s,"
        " 'adhoc:velowege', 'adhoc', 0.8, 'classify:adhoc:velowege', '8b', 'm', 'p', 'v', 'h')",
        (affair_id,),
    )


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

    registry = activate(conn, settings, "adhoc:velowege", by="Leo")
    assert registry.get("adhoc:velowege").status == "active"
    assert conn.execute(status).fetchone() == ("active",)


def test_retire_closes_the_jobs_and_supersedes_the_labels_and_create_reopens_them(conn, settings):
    run = create(conn, settings, **TOPIC, keywords=KEYWORDS, by="Mia").run
    conn.execute("UPDATE classification_jobs SET status = 'done' WHERE affair_id = 101")
    conn.execute(
        "UPDATE classification_jobs SET status = 'pending', worker_id = 'w', locked_at = now()"
        " WHERE affair_id = 102"
    )
    label(conn, 101)

    retired = retire(conn, settings, "adhoc:velowege", by="Leo")
    assert (retired.jobs, retired.labels) == (3, 1)
    tag = load_registry(settings.registry_path).get("adhoc:velowege")
    assert (tag.status, [(change.by, change.status) for change in tag.changes]) == (
        "retired",
        [("Leo", "retired")],
    )
    jobs = "SELECT status, last_error, count(*) FROM classification_jobs GROUP BY 1, 2"
    assert conn.execute(jobs).fetchall() == [("failed", "retired", 3)]
    events = conn.execute(
        "SELECT from_status FROM job_events WHERE task = %s AND reason = 'retired'"
        " ORDER BY affair_id",
        (TASK,),
    ).fetchall()
    assert events == [("done",), ("pending",), ("open",)]
    assert conn.execute("SELECT status FROM affair_tags").fetchall() == [("superseded",)]
    finished = "SELECT n_failed, finished_at IS NOT NULL FROM classification_runs WHERE id = %s"
    assert conn.execute(finished, (run.run_id,)).fetchone() == (2, True)  # open und pending

    again = create(conn, settings, **TOPIC, keywords=KEYWORDS, by="Ana")
    assert (again.tag_id, again.run.total, again.run.reopened) == ("adhoc:velowege", 3, 3)
    assert conn.execute(jobs).fetchall() == [("open", None, 3)]
    assert load_registry(settings.registry_path).get("adhoc:velowege").status == "proposed"
    assert conn.execute("SELECT status FROM affair_tags").fetchall() == [("superseded",)]


def test_adhoc_endpoints_preview_create_activate_and_retire(conn, settings):
    body = {"keywords": {"de": ["Velo"], "fr": ["vélo"]}}
    topic = {
        **body,
        "name_de": "Velowege",
        "description_de": "Geschäfte zu Velowegen und zum Veloverkehr",
        "broader": ["aps:6.1"],
        "user_name": "Mia",
    }
    leo = {"user_name": "Leo"}
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

        label(conn, 101)
        (found,) = client.get("/v1/affairs/101/topics").json()["labels"]
        assert found["tag_status"] == "proposed"  # vorläufiger Treffer
        assert client.get("/v1/pages/adhoc:velowege").status_code == 404

        activate_url = "/v1/adhoc/adhoc:velowege/activate"
        assert client.post(activate_url).status_code == 422  # ohne Name
        assert client.post(activate_url, json=leo).json()["status"] == "active"
        assert client.post(activate_url, json=leo).status_code == 409
        assert client.post("/v1/adhoc/aps:6.1.9/activate", json=leo).status_code == 404
        assert client.get("/v1/pages/adhoc:velowege").status_code == 200
        (found,) = client.get("/v1/affairs/101/topics").json()["labels"]
        assert found["tag_status"] == "active"
        label(conn, 102)
        review = {"affair_id": 102, "tag_id": "adhoc:velowege", "user_name": "Leo"}
        assert client.post("/v1/reviews", json={**review, "action": "reject"}).status_code == 200

        retire_url = "/v1/adhoc/adhoc:velowege/retire"
        retired = client.post(retire_url, json=leo).json()
        assert (retired["status"], retired["jobs"], retired["labels"]) == ("retired", 3, 1)
        assert client.post(retire_url, json=leo).status_code == 409
        assert client.post(activate_url, json=leo).status_code == 409
        assert client.post("/v1/adhoc/aps:6.1.9/retire", json=leo).status_code == 404
        assert client.get("/v1/pages/adhoc:velowege").status_code == 404
        (found,) = client.get("/v1/affairs/101/topics").json()["labels"]
        assert (found["status"], found["tag_status"]) == ("superseded", "retired")
        undo = client.post("/v1/reviews", json={**review, "action": "undo"})
        assert undo.status_code == 409  # das verworfene Label kommt nicht zurück

        back = client.post("/v1/adhoc", json=topic)  # Rückweg: dasselbe Thema neu anlegen
        assert (back.status_code, back.json()["jobs"]) == (200, 3)


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
