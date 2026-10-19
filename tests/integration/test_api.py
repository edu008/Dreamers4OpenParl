"""Sidecar-API gegen ein echtes PostgreSQL (PRD F10, F18)."""

import csv
import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

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

        def newest(**params):  # ohne q: alle mit Klassifikationstext, neueste zuerst
            return client.get("/v1/search", params=params).json()

        result = newest()
        assert (result["q"], result["total"]) == (None, 3)
        assert [item["affair_id"] for item in result["items"]] == [70435, 70437, 80003]
        assert {(item["rank"], item["headline"]) for item in result["items"]} == {(None, None)}
        assert [item["affair_id"] for item in newest(body_key="ZH")["items"]] == [80003]
        assert [item["affair_id"] for item in newest(topic="aps:6.1.9")["items"]] == [70435]


def test_topic_graph_by_area_and_related_topics(conn, repo_root, api_settings):
    migrate(conn, repo_root / "migrations")
    sync_registry(conn, load_registry(FIXTURE), file_hash(FIXTURE))
    seed(conn)  # 70435: aktiv aps:6.1.9
    conn.execute(
        "INSERT INTO affairs (id, body_key, raw) VALUES (70436, 'CHE', '{}'), (70437, 'CHE', '{}')"
    )
    label = (
        "INSERT INTO affair_tags (affair_id, tag_id, scheme, confidence, task, stage,"
        " model_version, prompt_version, registry_version, input_hash)"
        " VALUES (%s, %s, split_part(%s, ':', 1), 0.8, 'classify:aps', '8b', 'm', 'p', 'v', 'h')"
    )
    for affair_id, tag_id in [
        (70435, "aps:2.4.1"),
        (70435, "aps:6.1"),
        (70436, "aps:6.1.9"),
        (70436, "aps:2.4.1"),
        (70437, "aps:6.1.9"),
        (70437, "adhoc:digitalisierung-breit"),
    ]:
        conn.execute(label, (affair_id, tag_id, tag_id))

    with TestClient(create_app(api_settings)) as client:
        overview = client.get("/v1/graph/topics").json()
        nodes = [(n["id"], n["kind"], n["count"], n["group"]) for n in overview["nodes"]]
        assert nodes == [("aps:2", "bereich", 2, "aps:2"), ("aps:6", "bereich", 3, "aps:6")]
        assert overview["nodes"][0]["label"] == "Wirtschaft"
        assert overview["edges"] == [{"a": "aps:2", "b": "aps:6", "weight": 2}]
        assert (overview["area"], overview["hidden"]) == (None, 0)
        assert client.get("/v1/graph/topics", params={"min_weight": 3}).json()["edges"] == []

        area = client.get("/v1/graph/topics", params={"area": "aps:6"}).json()
        nodes = [(n["id"], n["kind"], n["count"]) for n in area["nodes"]]
        assert nodes == [("aps:6.1", "kapitel", 1), ("aps:6.1.9", "tag", 3)]
        assert area["edges"] == [{"a": "aps:6.1", "b": "aps:6.1.9", "weight": 1}]
        for unknown in ("aps:6.1", "aps:9"):  # Kapitel ist kein Bereich
            assert client.get("/v1/graph/topics", params={"area": unknown}).status_code == 404

        related = client.get("/v1/topics/aps:6.1.9/related").json()
        rows = [(row["tag_id"], row["shared"], row["in_registry"]) for row in related]
        assert rows == [
            ("adhoc:digitalisierung-breit", 1, True),  # aus der Registry zuerst
            ("aps:2.4.1", 2, False),
            ("aps:6.1", 1, False),
        ]
        assert related[0]["name_de"] == "Digitalisierung (breit)"
        assert client.get("/v1/topics/aps:9.9/related").status_code == 404

        # Alle Themen: jedes freigegebene Thema ein Knoten; das vorläufige Ad-hoc-Thema fehlt.
        conn.execute(label, (70437, "adhoc:ki-verwaltung", "adhoc:ki-verwaltung"))
        everything = client.get("/v1/graph/topics", params={"area": "all", "limit": 2}).json()
        nodes = [(n["id"], n["kind"], n["count"], n["group"]) for n in everything["nodes"]]
        assert nodes == [
            ("aps:2.4.1", "tag", 2, "aps:2"),
            ("aps:6.1", "kapitel", 1, "aps:6"),
            ("aps:6.1.9", "tag", 3, "aps:6"),
            ("adhoc:digitalisierung-breit", "querschnitt", 1, "adhoc"),
        ]
        assert everything["edges"] == [
            {"a": "aps:2.4.1", "b": "aps:6.1.9", "weight": 2},
            {"a": "adhoc:digitalisierung-breit", "b": "aps:6.1.9", "weight": 1},
        ]
        assert (everything["area"], everything["hidden"]) == ("all", 2)

        star = client.get("/v1/graph/topics/aps:6.1.9").json()
        assert (star["center"], star["total"]) == (
            {"tag_id": "aps:6.1.9", "name_de": "Digitalisierung"},
            3,
        )
        assert [node["affair_id"] for node in star["nodes"]] == [70435, 70437, 70436]
        params = {"limit": 1, "min_confidence": 0.85}
        assert client.get("/v1/graph/topics/aps:6.1.9", params=params).json()["total"] == 1
        assert client.get("/v1/graph/topics/aps:9.9").status_code == 404

        around = client.get("/v1/graph/affairs/70435").json()
        assert around["center"]["topics"][0]["tag_id"] == "aps:6.1.9"
        assert [(n["affair_id"], n["shared"], n["score"]) for n in around["neighbours"]] == [
            (70436, ["aps:2.4.1", "aps:6.1.9"], 1.6),
            (70437, ["aps:6.1.9"], 0.8),
        ]
        assert len(client.get("/v1/graph/affairs/70435?limit=1").json()["neighbours"]) == 1
        assert client.get("/v1/graph/affairs/1").status_code == 404


def test_navigation_search_walks_back_falls_back_and_logs(
    conn, repo_root, api_settings, monkeypatch
):
    import json

    import httpx

    from parltopics.llm import LLMClient
    from tests.mock_llm.app import completion, fake_completion

    def answer(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        return httpx.Response(
            200, json=completion(fake_completion(body["messages"]), body["model"])
        )

    def unreachable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("kein LLM")

    def use(handler):
        mock = httpx.MockTransport(handler)
        monkeypatch.setattr(
            "parltopics.api.navigate.LLMClient",
            lambda settings, transport=None: LLMClient(settings, transport=mock),
        )

    migrate(conn, repo_root / "migrations")
    sync_registry(conn, load_registry(FIXTURE), file_hash(FIXTURE))
    seed(conn)  # 70435: aktiv aps:6.1.9; der Mock bewertet die erste Unterseite am höchsten
    conn.execute(INDEX, ([70435],))
    use(answer)
    with TestClient(create_app(api_settings)) as client:
        found = client.post("/v1/search/navigate", json={"query": "Verwaltung digitalisieren"})
        result = found.json()
        assert (result["status"], result["fallback_used"]) == ("ok", False)
        # Der erste Ast (Wirtschaft) hat keine Treffer: zurück und über Infrastruktur weiter.
        titles = [step["title"] for step in result["path"]]
        assert titles == [
            "Themen",
            "Infrastruktur und Umwelt",
            "Verkehr und Kommunikation",
            "Digitalisierung",
        ]
        assert result["answer"] == "Geschäft 70435 passt zur Frage (Mock)."
        assert result["statements"] == [{"text": result["answer"], "affair_ids": [70435]}]
        (hit,) = result["hits"]
        assert (hit["affair_id"], hit["topics"][0]["tag_id"]) == (70435, "aps:6.1.9")
        assert [topic["tag_id"] for topic in result["related_topics"]] == [
            "aps:6",
            "aps:6.1",
            "aps:6.1.9",
        ]
        assert result["steps"] == 6

        conn.execute("UPDATE affair_tags SET status = 'superseded'")
        fallback = client.post("/v1/search/navigate", json={"query": "Verwaltung digitalisieren"})
        assert (fallback.json()["fallback_used"], fallback.json()["path"]) == (
            True,
            [{"page_id": "volltext", "title": "Volltextsuche"}],
        )
        nothing = client.post("/v1/search/navigate", json={"query": "Raumfahrt"}).json()
        assert (nothing["status"], nothing["answer"], nothing["hits"]) == ("no_results", None, [])

        use(unreachable)
        assert client.post("/v1/search/navigate", json={"query": "Raumfahrt"}).status_code == 503
        assert client.post("/v1/search/navigate", json={"query": "ab"}).status_code == 422
    runs = conn.execute(
        "SELECT status, fallback_used, affair_ids FROM search_runs ORDER BY id"
    ).fetchall()
    assert runs == [
        ("ok", False, [70435]),
        ("ok", True, [70435]),
        ("no_results", True, []),
        ("error", False, []),
    ]


# Ausschnitte der Datensätze, wie sie in der geteilten Datenbank liegen (Genf, Geschäft 341579).
GENEVA = {
    "id": 257,
    "body_key": "GE",
    "type": "canton",
    "name": "Genf",
    "name_de": "Genf",
    "name_fr": "Genève",
    "legislative_name": "Grand Conseil du canton de Genève",
    "legislative_name_de": "Grosser Rat",
    "legislative_seats": 100,
    "languages": "FR",
}
ELECTION = {
    "id": 341579,
    "body_key": "GE",
    "number": "E 3265",
    "title_de": None,
    "title_fr": "Election d'une juge assesseure",
    "state_name_de": None,
    "type_harmonized_de": "Wahl",
    "type_harmonized_id": 6,
    "url_external_fr": "https://ge.ch/grandconseil/search?search=E+3265",
    "end_date": None,
}


def test_stored_records_of_affairs_bodies_texts_and_docs(conn, repo_root, api_settings):
    migrate(conn, repo_root / "migrations")
    conn.execute(
        "INSERT INTO bodies (id, body_key, name, level, raw)"
        " VALUES (257, 'GE', 'Genf', 'canton', %s)",
        (Jsonb(GENEVA),),
    )
    conn.execute(
        "INSERT INTO affairs (id, body_key, title_fr, raw) VALUES"
        " (341579, 'GE', 'Election', %s), (341580, 'ZZ', 'Ohne Parlament', '{}')",
        (Jsonb(ELECTION),),
    )
    # Wie ingest.text_row: die erste Sprache in text, die übrigen in raw.
    raw = {"type_fr": "Exposé des motifs", "type_de": None, "text_it": "Elezione", "text_rm": None}
    conn.execute(
        "INSERT INTO affair_texts (id, affair_id, text_type, language, format, text, raw) VALUES"
        " (11, 341579, 'Exposé des motifs', 'fr', 'html', '<p>Election</p>', %s),"
        " (12, 341579, NULL, NULL, NULL, NULL, '{}')",
        (Jsonb(raw),),
    )
    doc = (
        "INSERT INTO affair_docs (id, parent_type, parent_id, name, doc_date, text, raw)"
        " VALUES (%s, %s, 341579, %s, %s, %s, %s)"
    )
    conn.execute(doc, (21, "affair", "Rapport", None, None, Jsonb({"category_fr": "Rapport"})))
    conn.execute(doc, (22, "affair", "Projet", "2026-10-01", "Texte du projet", Jsonb({})))
    conn.execute(doc, (23, "agenda", "Ordre du jour", "2026-10-29", None, Jsonb({})))
    with TestClient(create_app(api_settings)) as client:
        record = client.get("/v1/affairs/341579").json()
        assert (record["title"], record["state_name"], record["type_harmonized"]) == (
            {"fr": "Election d'une juge assesseure"},
            {},
            {"de": "Wahl"},
        )
        assert (record["number"], record["type_harmonized_id"], record["end_date"]) == (
            "E 3265",
            6,
            None,
        )
        assert record["url_external"] == {"fr": "https://ge.ch/grandconseil/search?search=E+3265"}
        assert record["url_api"] == "https://api.openparldata.ch/v1/affairs/341579"
        body = record["body"]
        assert (body["name"], body["legislative_name"], body["legislative_seats"]) == (
            {"de": "Genf", "fr": "Genève"},
            {"de": "Grosser Rat"},
            100,
        )
        first, empty = record["texts"]
        assert (first["text"], first["type"]) == (
            {"fr": "<p>Election</p>", "it": "Elezione"},
            {"fr": "Exposé des motifs"},
        )
        assert (empty["id"], empty["text"]) == (12, {})
        # Nach Datum, ohne Datum zuletzt; das Dokument der Agenda gehört nicht zum Geschäft.
        assert record["n_docs"] == 2
        assert [(item["id"], item["has_text"]) for item in record["docs"]] == [
            (22, True),
            (21, False),
        ]
        assert record["docs"][1]["category"] == {"fr": "Rapport"}
        lonely = client.get("/v1/affairs/341580").json()
        assert (lonely["body"], lonely["texts"], lonely["n_docs"]) == (None, [], 0)

        page = client.get("/v1/affairs/341579/docs", params={"limit": 1, "offset": 1}).json()
        assert (page["total"], [item["id"] for item in page["items"]]) == (2, [21])
        assert client.get("/v1/affairs/341580/docs").json()["items"] == []
        found = client.get("/v1/docs/22").json()
        assert (found["text"], found["parent_type"], found["parent_id"]) == (
            "Texte du projet",
            "affair",
            341579,
        )
        assert client.get("/v1/docs/23").json()["parent_type"] == "agenda"
        geneva = client.get("/v1/bodies/GE").json()
        assert (geneva["n_affairs"], geneva["n_labelled"], geneva["url_api"]) == (
            1,
            0,
            "https://api.openparldata.ch/v1/bodies/257",
        )
        for path in ("/v1/affairs/1", "/v1/affairs/1/docs", "/v1/docs/1", "/v1/bodies/XX"):
            assert client.get(path).status_code == 404, path


def test_page_summary_and_csv_export(conn, repo_root, api_settings):
    migrate(conn, repo_root / "migrations")
    sync_registry(conn, load_registry(FIXTURE), file_hash(FIXTURE))
    seed(conn)  # 70435: CHE, Motion, 2026-03-01, aps:6.1.9 mit 0.86 und gefundenem Beleg
    conn.execute(
        "INSERT INTO bodies (id, body_key, name, level, raw)"
        " VALUES (2, 'ZH', 'Zürich', 'canton', '{}')"
    )
    postulate = Jsonb({"type_harmonized_de": "Postulat"})
    conn.execute(
        "INSERT INTO affairs (id, body_key, number, title_de, type_harmonized_en, begin_date, raw)"
        " VALUES (80001, 'ZH', '=1+1', 'Velo; \"schnell\"', 'Postulate', '2025-05-01', %s),"
        " (80002, 'ZH', NULL, 'Ohne Datum', 'Postulate', NULL, %s)",
        (postulate, postulate),
    )
    label = (
        "INSERT INTO affair_tags (affair_id, tag_id, scheme, confidence, evidence,"
        " evidence_verified, task, stage, model_version, prompt_version, registry_version,"
        " input_hash) VALUES (%s, 'aps:6.1.9', 'aps', %s, %s, false, 'classify:aps', '8b',"
        " 'm', 'p', 'v', 'h')"
    )
    conn.execute(label, (80001, 0.7, "-steht da"))
    conn.execute(label, (80002, 0.65, None))

    with TestClient(create_app(api_settings)) as client:
        path = "/v1/pages/aps:6.1.9/affairs"
        summary = client.get(f"{path}/summary").json()
        totals = {key: summary[key] for key in ("rows", "affairs", "bodies", "verified")}
        assert totals == {"rows": 3, "affairs": 3, "bodies": 2, "verified": 1}
        assert (summary["first_date"], summary["last_date"]) == ("2025-05-01", "2026-03-01")
        assert summary["by_level"] == [
            {"level": "country", "count": 1},
            {"level": "canton", "count": 2},
        ]
        assert summary["by_body"] == [
            {"body_key": "ZH", "name": "Zürich", "level": "canton", "count": 2},
            {"body_key": "CHE", "name": "Schweiz", "level": "country", "count": 1},
        ]
        assert summary["by_year"] == [
            {"year": 2025, "count": 1},
            {"year": 2026, "count": 1},
            {"year": None, "count": 1},
        ]
        assert summary["by_type"] == [
            {"type": "Postulate", "type_de": "Postulat", "count": 2},
            {"type": "Motion", "type_de": None, "count": 1},
        ]
        # Jede Verteilung ohne ihren eigenen Filter: by_body zeigt weiter beide Parlamente.
        zurich = client.get(f"{path}/summary", params={"body_key": "ZH"}).json()
        assert (zurich["rows"], len(zurich["by_body"]), zurich["by_level"]) == (
            2,
            2,
            [{"level": "canton", "count": 2}],
        )
        recent = client.get(f"{path}/summary", params={"from": "2026-01-01"}).json()
        assert (recent["rows"], len(recent["by_year"])) == (1, 3)

        response = client.get(f"{path}.csv")
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        assert 'filename="aps-6-1-9.csv"' in response.headers["content-disposition"]
        assert response.text.startswith("﻿OpenParlData-ID;Nummer;Titel;")
        assert response.text.endswith("\r\n")
        rows = list(csv.reader(io.StringIO(response.text[1:], newline=""), delimiter=";"))
        assert rows[1:] == [
            ["70435", "24.3456", "Digitale Verwaltung", "Motion", "Schweiz", "Bund",
             "2026-03-01", "Digitalisierung", "0.86", "ja", "die Verwaltung digitalisieren",
             "70b"],
            ["80001", "'=1+1", 'Velo; "schnell"', "Postulat", "Zürich", "Kanton", "2025-05-01",
             "Digitalisierung", "0.70", "nein", "'-steht da", "8b"],
            ["80002", "", "Ohne Datum", "Postulat", "Zürich", "Kanton", "", "Digitalisierung",
             "0.65", "nein", "", "8b"],
        ]  # fmt: skip
        filtered = client.get(f"{path}.csv", params={"body_key": "ZH"}).text
        assert filtered.count("\r\n") == 3  # Kopf und zwei Zeilen
        for unknown in ("/v1/pages/aps:9/affairs.csv", "/v1/pages/aps:9/affairs/summary"):
            assert client.get(unknown).status_code == 404


def test_agent_search_cites_only_tool_results_and_logs(conn, repo_root, api_settings, monkeypatch):
    import json

    import httpx

    from parltopics.llm import LLMClient
    from tests.mock_llm.app import completion, fake_completion

    def answer(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        return httpx.Response(
            200, json=completion(fake_completion(body["messages"]), body["model"])
        )

    def unreachable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("kein LLM")

    def use(handler):
        mock = httpx.MockTransport(handler)
        monkeypatch.setattr(
            "parltopics.agent.loop.LLMClient",
            lambda settings, transport=None: LLMClient(settings, transport=mock),
        )

    migrate(conn, repo_root / "migrations")
    sync_registry(conn, load_registry(FIXTURE), file_hash(FIXTURE))
    seed(conn)  # 70435: «Der Bundesrat soll die Verwaltung digitalisieren.», aktiv aps:6.1.9
    conn.execute(INDEX, ([70435],))
    use(answer)  # der Mock ruft search_affairs mit der Frage auf und zitiert den ersten Treffer
    with TestClient(create_app(api_settings)) as client:
        found = client.post("/v1/agent/search", json={"query": "Verwaltung digitalisieren"})
        result = found.json()
        assert (result["status"], result["cited_affair_ids"], result["steps"]) == (
            "ok",
            [70435],
            2,
        )
        assert result["answer"] == "Geschäft [70435] passt zur Frage (Mock)."
        (hit,) = result["hits"]
        assert (hit["affair_id"], hit["topics"][0]["tag_id"]) == (70435, "aps:6.1.9")
        (call,) = result["tool_calls"]
        assert (call["name"], call["args"], call["error"]) == (
            "search_affairs",
            {"query": "Verwaltung digitalisieren"},
            None,
        )
        assert (call["result_size"] > 0, result["proposal"]) == (True, None)

        nothing = client.post("/v1/agent/search", json={"query": "Raumfahrt"}).json()
        assert (nothing["status"], nothing["cited_affair_ids"], nothing["hits"]) == (
            "no_results",
            [],
            [],
        )
        use(unreachable)
        assert client.post("/v1/agent/search", json={"query": "Raumfahrt"}).status_code == 503
        assert client.post("/v1/agent/search", json={"query": "ab"}).status_code == 422
    runs = conn.execute(
        "SELECT kind, status, cited_affair_ids, jsonb_array_length(tool_calls)"
        " FROM agent_runs ORDER BY id"
    ).fetchall()
    assert runs == [
        ("search", "ok", [70435], 1),
        ("search", "no_results", [], 1),
        ("search", "error", [], 0),
    ]
