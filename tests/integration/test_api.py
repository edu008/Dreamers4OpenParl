"""Sidecar-API gegen ein echtes PostgreSQL (PRD F10, F18)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from parltopics.api.app import create_app
from parltopics.db import migrate
from parltopics.registry import file_hash, load_registry
from parltopics.registry.sync import sync_registry

pytestmark = pytest.mark.integration

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "tags_example.yaml"
TEXT = "Der Bundesrat soll die Verwaltung digitalisieren."


def seed(conn) -> None:
    conn.execute(
        "INSERT INTO bodies (id, body_key, name, level, raw)"
        " VALUES (1, 'CHE', 'Schweiz', 'country', '{}')"
    )
    conn.execute(
        "INSERT INTO affairs (id, body_key, number, title_de, type_harmonized_en, begin_date, raw)"
        " VALUES (70435, 'CHE', '24.3456', 'Digitale Verwaltung', 'Motion', '2026-03-01', '{}')"
    )
    conn.execute(
        "INSERT INTO affair_inputs (affair_id, text, language, source, input_hash)"
        " VALUES (70435, %s, 'de', 'texts', 'h1')",
        (TEXT,),
    )
    label = (
        "INSERT INTO affair_tags (affair_id, tag_id, scheme, confidence, evidence,"
        " evidence_verified, task, stage, model_version, prompt_version, registry_version,"
        " input_hash, status) VALUES (70435, %s, 'aps', %s, 'die Verwaltung digitalisieren',"
        " true, 'classify:aps', %s, 'm', 'p1', '2026-10-18.3', 'h1', %s)"
    )
    conn.execute(label, ("aps:6.1.9", 0.86, "70b", "active"))
    conn.execute(label, ("aps:2.4.1", 0.4, "8b", "superseded"))
    conn.execute(
        "INSERT INTO affair_summaries (affair_id, summary, task, stage, model_version,"
        " prompt_version, input_hash) VALUES (70435, %s, 'classify:aps', '70b', 'm', 'p1', 'h1')",
        (TEXT,),
    )
    conn.execute(
        "INSERT INTO classification_jobs (affair_id, task, status)"
        " VALUES (70435, 'classify:aps', 'done')"
    )


def test_endpoints_read_labels_topics_and_jobs(conn, repo_root, api_settings):
    migrate(conn, repo_root / "migrations")
    sync_registry(conn, load_registry(FIXTURE), file_hash(FIXTURE))
    seed(conn)
    with TestClient(create_app(api_settings)) as client:
        counts = {"open": 0, "pending": 0, "done": 1, "failed": 0, "total": 1}
        expected = {"tasks": [{"task": "classify:aps", **counts}]}
        assert client.get("/v1/jobs/summary").json() == expected

        affair = client.get("/v1/affairs/70435/topics").json()
        assert (affair["title"], affair["text"], affair["summary_de"]) == (
            "Digitale Verwaltung",
            TEXT,
            TEXT,
        )
        assert (affair["body_name"], affair["body_level"]) == ("Schweiz", "country")
        labels = [(item["tag_id"], item["status"], item["confidence"]) for item in affair["labels"]]
        assert labels == [("aps:6.1.9", "active", 0.86), ("aps:2.4.1", "superseded", 0.4)]
        assert client.get("/v1/affairs/1/topics").status_code == 404

        response = client.get("/v1/topics", params={"scheme": "aps"}).json()
        topics = {topic["tag_id"]: topic for topic in response}
        assert (topics["aps:6.1.9"]["n_affairs"], topics["aps:2.4.1"]["n_affairs"]) == (1, 0)
        assert "adhoc:digitalisierung-breit" not in topics

        path = "/v1/topics/aps:6.1.9/affairs"
        filters = {"body_key": "CHE", "from": "2026-01-01", "min_confidence": 0.8}
        page = client.get(path, params=filters).json()
        assert (page["total"], page["items"][0]["affair_id"]) == (1, 70435)
        assert page["items"][0]["body_name"] == "Schweiz"
        assert client.get(path, params={"min_confidence": 0.9}).json()["total"] == 0
        assert client.get(path, params={"to": "2025-12-31"}).json()["total"] == 0
        assert client.get("/v1/topics/aps:9.9/affairs").status_code == 404
