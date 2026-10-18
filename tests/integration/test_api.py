"""Sidecar-API gegen ein echtes PostgreSQL (PRD F10, F18)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from parltopics.api.app import create_app
from parltopics.db import migrate
from parltopics.inputs import SEARCH as INDEX
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
        expected = {"tasks": [{"task": "classify:aps", **counts}], "runs": [], "errors": []}
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


def test_page_affairs_cover_the_subtree_of_a_page(conn, repo_root, api_settings):
    migrate(conn, repo_root / "migrations")
    sync_registry(conn, load_registry(FIXTURE), file_hash(FIXTURE))
    seed(conn)  # 70435 (Motion, CHE): aktiv aps:6.1.9
    conn.execute(
        "INSERT INTO affairs (id, body_key, title_de, type_harmonized_en, raw)"
        " VALUES (70436, 'CHE', 'Arbeitsmarkt', 'Postulate', '{}')"
    )
    label = (
        "INSERT INTO affair_tags (affair_id, tag_id, scheme, confidence, task, stage,"
        " model_version, prompt_version, registry_version, input_hash)"
        " VALUES (%s, %s, split_part(%s, ':', 1), %s, 'classify:aps', '8b', 'm', 'p', 'v', 'h')"
    )
    conn.execute(label, (70435, "adhoc:digitalisierung-breit", "adhoc:digitalisierung-breit", 0.7))
    conn.execute(label, (70436, "aps:2.4.1", "aps:2.4.1", 0.9))

    def rows(page_id, **params):
        found = client.get(f"/v1/pages/{page_id}/affairs", params=params).json()
        return found["total"], [(item["affair_id"], item["tag_id"]) for item in found["items"]]

    with TestClient(create_app(api_settings)) as client:
        assert rows("aps:6.1.9") == (1, [(70435, "aps:6.1.9")])
        # Kapitel und Bereich: alle Unterseiten; die verlinkte Querschnittsseite zählt nicht dazu.
        assert rows("aps:6.1") == rows("aps:6") == (1, [(70435, "aps:6.1.9")])
        assert rows("adhoc:digitalisierung-breit") == (1, [(70435, "adhoc:digitalisierung-breit")])
        everything = [
            (70436, "aps:2.4.1"),
            (70435, "aps:6.1.9"),
            (70435, "adhoc:digitalisierung-breit"),
        ]
        assert rows("heart") == (3, everything)
        assert rows("heart", type="Postulate") == (1, [(70436, "aps:2.4.1")])
        assert rows("heart", level="country")[0] == 3
        assert rows("heart", level="canton")[0] == 0
        assert rows("heart", min_confidence=0.8, limit=1) == (2, [(70436, "aps:2.4.1")])
        item = client.get("/v1/pages/aps:2/affairs").json()["items"][0]
        assert (item["name_de"], item["body_name"]) == ("Arbeitsmarkt", "Schweiz")
        assert client.get("/v1/pages/aps:9/affairs").status_code == 404
        assert client.get("/v1/pages/heart/affairs", params={"level": "x"}).status_code == 422


def test_parliaments_german_types_and_recent_runs(conn, repo_root, api_settings):
    migrate(conn, repo_root / "migrations")
    sync_registry(conn, load_registry(FIXTURE), file_hash(FIXTURE))
    seed(conn)  # CHE mit einem klassifizierten Geschäft
    conn.execute(
        "INSERT INTO bodies (id, body_key, name, level, raw) VALUES"
        " (2, 'ZH', 'Zürich', 'canton', '{}'), (3, 'BE', 'Bern', 'canton', '{}')"
    )
    conn.execute(
        "INSERT INTO affairs (id, body_key, title_de, type_harmonized_en, raw) VALUES"
        " (80001, 'ZH', 'Velowege', 'Postulate', '{\"type_harmonized_de\": \"Postulat\"}'),"
        " (80002, 'BE', 'Ohne Label', 'Motion', '{}')"
    )
    conn.execute(
        "INSERT INTO affair_inputs (affair_id, text, language, source, input_hash)"
        " VALUES (80001, 'Velowege', 'de', 'texts', 'h')"
    )
    conn.execute(
        "INSERT INTO affair_tags (affair_id, tag_id, scheme, confidence, task, stage,"
        " model_version, prompt_version, registry_version, input_hash)"
        " VALUES (80001, 'aps:6.1.9', 'aps', 0.8, 'classify:aps', '8b', 'm', 'p', 'v', 'h')"
    )
    conn.execute(
        "INSERT INTO classification_runs (kind, task, registry_version, scheme_hash,"
        " prompt_version, n_total, n_done, n_failed, n_escalated)"
        " VALUES ('full', 'classify:aps', '2026-10-18.3', 's', 'p', 5, 4, 1, 2)"
    )
    conn.execute(
        "INSERT INTO classification_runs (kind, task, registry_version, scheme_hash,"
        " prompt_version, n_total, n_done, started_at, finished_at) VALUES ('daily',"
        " 'classify:aps', 'v', 's', 'p', 30, 30, '2026-10-18 10:00+00', '2026-10-18 10:10+00')"
    )
    conn.execute(
        "INSERT INTO classification_jobs (affair_id, task, status, attempts, last_error)"
        " VALUES (80002, 'classify:aps', 'failed', 3, %s)",
        ("ungültige Antwort: 1 validation error\nchapters zu kurz",),
    )
    with TestClient(create_app(api_settings)) as client:
        bodies = [tuple(body.values()) for body in client.get("/v1/bodies").json()]
        assert bodies == [("CHE", "Schweiz", "country", 1), ("ZH", "Zürich", "canton", 1)]

        affair = client.get("/v1/affairs/80001/topics").json()
        assert (affair["type"], affair["type_de"]) == ("Postulate", "Postulat")
        assert client.get("/v1/affairs/70435/topics").json()["type_de"] is None  # raw ohne Typ

        summary = client.get("/v1/jobs/summary").json()
        finished, run = summary["runs"]  # neuester zuerst
        assert (finished["duration_s"], finished["per_minute"]) == (600, 3.0)
        assert (run["kind"], run["task"], run["finished_at"]) == ("full", "classify:aps", None)
        counts = (run["n_total"], run["n_done"], run["n_failed"], run["n_escalated"])
        assert counts == (5, 4, 1, 2)
        assert run["duration_s"] >= 0
        reason = "ungültige Antwort: 1 validation error"
        assert summary["errors"] == [{"task": "classify:aps", "reason": reason, "count": 1}]

        stats = client.get("/v1/stats").json()
        assert stats == {
            "affairs": 3,
            "prepared": 2,
            "indexed": 0,
            "classified": 1,
            "labelled": 2,
            "labels": 2,
            "reviewed": 0,
        }


def test_full_text_search_in_german_and_french(conn, repo_root, api_settings):
    migrate(conn, repo_root / "migrations")
    sync_registry(conn, load_registry(FIXTURE), file_hash(FIXTURE))
    seed(conn)  # 70435: «Der Bundesrat soll die Verwaltung digitalisieren.», aktiv aps:6.1.9
    conn.execute(
        "INSERT INTO bodies (id, body_key, name, level, raw)"
        " VALUES (2, 'ZH', 'Zürich', 'canton', '{}')"
    )
    conn.execute(
        "INSERT INTO affairs (id, body_key, title_fr, begin_date, raw) VALUES"
        " (70437, 'CHE', 'Numérisation', '2026-02-01', '{}'),"
        " (80003, 'ZH', 'Velowege', '2024-06-01', '{}')"
    )
    texts = [
        (
            70437,
            "Numérisation <script>x()</script> si coût < 5 & délai\nLe Conseil doit numériser.",
            "fr",
        ),
        (80003, "Velowege in Zürich\nDie Stadt soll die Ausleihe digitalisieren.", "de"),
    ]
    for affair_id, text, language in texts:
        conn.execute(
            "INSERT INTO affair_inputs (affair_id, text, language, source, input_hash)"
            " VALUES (%s, %s, %s, 'texts', 'h')",
            (affair_id, text, language),
        )
    conn.execute("UPDATE affairs SET title_fr = 'Administration numérique' WHERE id = 70435")
    conn.execute(INDEX, ([70435, 70437, 80003],))

    def found(q, **params):
        result = client.get("/v1/search", params={"q": q, **params}).json()
        return result["total"], [item["affair_id"] for item in result["items"]]

    with TestClient(create_app(api_settings)) as client:
        result = client.get("/v1/search", params={"q": "digitalisieren"}).json()
        assert (result["q"], result["total"]) == ("digitalisieren", 2)
        assert result["duration_ms"] >= 0
        first, second = result["items"]
        assert (first["affair_id"], second["affair_id"]) == (70435, 80003)  # Titel vor Text
        assert first["rank"] > second["rank"]
        assert "<mark>digitalisieren</mark>" in first["headline"]
        (topic,) = first["topics"]
        assert (topic["tag_id"], topic["confidence"], topic["stage"]) == ("aps:6.1.9", 0.86, "70b")
        assert (topic["evidence"], topic["evidence_verified"]) == (
            "die Verwaltung digitalisieren",
            True,
        )
        assert second["topics"] == []

        french = client.get("/v1/search", params={"q": "numériser"}).json()["items"]
        assert [item["affair_id"] for item in french] == [70437]
        headline = french[0]["headline"]
        assert "<mark>" in headline
        assert "&lt;" in headline  # maskiert: nur <mark> ist echtes HTML
        assert "<" not in headline.replace("<mark>", "").replace("</mark>", "")

        assert found("administration") == (1, [70435])  # deutscher Text, französischer Titel
        assert found('"Verwaltung digitalisieren"') == (1, [70435])
        assert found("digitalisieren", topic="aps:6.1.9") == (1, [70435])
        assert found("digitalisieren", body_key="ZH") == (1, [80003])
        assert found("digitalisieren", level="canton") == (1, [80003])
        assert found("digitalisieren", to="2024-12-31") == (1, [80003])
        assert found("digitalisieren", limit=1, offset=1) == (2, [80003])
        assert found("Raumfahrt") == (0, [])
        assert first["language"] == "de"
        assert found("numériser", language="fr") == (1, [70437])
        assert found("digitalisieren", language="fr") == (0, [])
        assert client.get("/v1/search", params={"q": "a"}).status_code == 422
