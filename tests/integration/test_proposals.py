"""Tag-Vorschläge gruppieren, prüfen und entscheiden, gegen ein echtes PostgreSQL (PRD F7)."""

import asyncio
import json
import shutil
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from parltopics.api.app import create_app
from parltopics.classify.proposals import GroupResult, group
from parltopics.db import migrate
from parltopics.registry import file_hash, load_registry
from parltopics.registry.sync import sync_registry
from tests.mock_llm.app import completion, fake_completion

pytestmark = pytest.mark.integration

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "tags_example.yaml"


def raw(conn, affair_id, name, desc="Beschreibung", reason="fehlt in der Liste"):
    conn.execute(
        "INSERT INTO tag_proposal_raw (affair_id, name_de, desc_de, reason, model_version)"
        " VALUES (%s, %s, %s, %s, 'test-8b')",
        (affair_id, name, desc, reason),
    )


@pytest.fixture
def settings(conn, repo_root, api_settings, tmp_path):
    registry_path = tmp_path / "tags.yaml"
    shutil.copy(FIXTURE, registry_path)
    migrate(conn, repo_root / "migrations")
    sync_registry(conn, load_registry(registry_path), file_hash(registry_path))
    for affair_id, title in [(1, "Online-Schalter"), (2, "Digitale Ämter"), (3, "Velonetz")]:
        conn.execute(
            "INSERT INTO affairs (id, body_key, title_de, raw) VALUES (%s, 'CHE', %s, '{}')",
            (affair_id, title),
        )
        conn.execute(
            "INSERT INTO affair_inputs (affair_id, text, language, source, input_hash)"
            " VALUES (%s, %s, 'de', 'texts', 'h')",
            (affair_id, title),
        )
    raw(conn, 1, "E-Government", "Digitale Behördenleistungen")
    raw(conn, 2, "E-government", "Online-Schalter der Verwaltung")
    raw(conn, 3, "Velowege", "Infrastruktur für Velos")
    return api_settings.model_copy(update={"registry_path": registry_path})


def proposals(conn):
    return conn.execute(
        "SELECT group_key, recommendation, related_tag_id, model_version FROM tag_proposals"
        " ORDER BY group_key"
    ).fetchall()


async def test_without_model_the_registry_labels_decide(conn, settings):
    assert await group(conn, settings, use_model=False) == GroupResult(2, 0, 0)
    assert proposals(conn) == [
        ("e-government", "duplicate_of", "aps:6.1.9", "pg_trgm"),  # Alias von Digitalisierung
        ("velowege", "new", None, "pg_trgm"),
    ]
    affairs = conn.execute(
        "SELECT p.group_key, count(*) FROM tag_proposal_affairs a"
        " JOIN tag_proposals p ON p.id = a.proposal_id GROUP BY 1 ORDER BY 1"
    ).fetchall()
    assert affairs == [("e-government", 2), ("velowege", 1)]
    raw(conn, 3, "E Government")  # gleicher Schlüssel: geht dem bestehenden Vorschlag zu
    assert await group(conn, settings, use_model=False) == GroupResult(0, 1, 0)
    assert conn.execute(
        "SELECT count(*) FROM tag_proposal_raw WHERE proposal_id IS NULL"
    ).fetchone() == (0,)


async def test_with_model_its_recommendation_counts(conn, settings):
    def answer(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        return httpx.Response(
            200, json=completion(fake_completion(body["messages"]), body["model"])
        )

    result = await group(conn, settings, transport=httpx.MockTransport(answer))
    assert result == GroupResult(2, 0, 2)
    model = settings.llm_name_large
    assert proposals(conn) == [
        ("e-government", "child_of", "aps:6.1.9", model),
        ("velowege", "new", None, model),
    ]


def test_review_accepts_merges_and_rejects(conn, settings):
    raw(conn, 3, "Bienenschutz", "Schutz der Bienen")
    asyncio.run(group(conn, settings, use_model=False))
    decide = "/v1/proposals/{}/decision"
    with TestClient(create_app(settings)) as client:
        listing = client.get("/v1/proposals").json()
        assert listing["total"] == 3
        first, *others = listing["items"]  # meiste Geschäfte zuerst
        assert (first["name_de"], first["n_affairs"], first["recommendation"]) == (
            "E-Government",
            2,
            "duplicate_of",
        )
        assert first["related_name_de"] == "Digitalisierung"
        assert set(first["variants"]) == {"E-Government", "E-government"}
        assert [affair["affair_id"] for affair in first["affairs"]] == [2, 1]
        velo, bees = sorted(others, key=lambda item: item["name_de"], reverse=True)

        accepted = client.post(
            decide.format(velo["id"]),
            json={"decision": "accepted", "user_name": "Mia", "name_de": "Velowege"},
        ).json()
        assert (accepted["tag_id"], accepted["jobs"]) == ("adhoc:velowege", 1)
        assert accepted["proposal"]["decision"] == "accepted"
        tag = load_registry(settings.registry_path).get("adhoc:velowege")
        assert (tag.status, tag.proposal.recommendation, tag.created.by) == (
            "proposed",
            "new",
            "Mia",
        )
        again = client.post(
            decide.format(velo["id"]), json={"decision": "rejected", "user_name": "M"}
        )
        assert again.status_code == 409

        merged = client.post(
            decide.format(first["id"]), json={"decision": "merged", "user_name": "M"}
        )
        assert merged.json()["proposal"]["related_tag_id"] == "aps:6.1.9"
        no_tag = client.post(
            decide.format(bees["id"]), json={"decision": "merged", "user_name": "M"}
        )
        assert no_tag.status_code == 422
        rejected = client.post(
            decide.format(bees["id"]), json={"decision": "rejected", "user_name": "M"}
        )
        assert rejected.json()["proposal"]["decided_by"] == "M"

        assert client.get("/v1/proposals").json()["total"] == 0
        assert client.get("/v1/proposals", params={"state": "done"}).json()["total"] == 3
        unknown = client.post(decide.format(999), json={"decision": "rejected", "user_name": "M"})
        assert unknown.status_code == 404


def test_undo_reopens_a_decision_and_retires_the_accepted_tag(conn, settings):
    asyncio.run(group(conn, settings, use_model=False))
    decide = "/v1/proposals/{}/decision"
    undo = {"decision": "undo", "user_name": "Leo"}
    with TestClient(create_app(settings)) as client:
        egov, velo = client.get("/v1/proposals").json()["items"]
        assert client.post(decide.format(velo["id"]), json=undo).status_code == 409  # offen

        accept = {"decision": "accepted", "user_name": "Mia"}
        client.post(decide.format(velo["id"]), json=accept)
        undone = client.post(decide.format(velo["id"]), json=undo).json()
        assert undone["tag_id"] == "adhoc:velowege"
        proposal = undone["proposal"]
        assert (proposal["status"], proposal["decision"], proposal["decided_by"]) == (
            "open",
            None,
            "Leo",
        )
        assert load_registry(settings.registry_path).get("adhoc:velowege").status == "retired"
        assert client.post(decide.format(velo["id"]), json=undo).status_code == 409

        again = client.post(decide.format(velo["id"]), json={**accept, "user_name": "Ana"})
        assert (again.json()["tag_id"], again.json()["jobs"]) == ("adhoc:velowege", 1)
        tag = load_registry(settings.registry_path).get("adhoc:velowege")
        assert [(change.by, change.status) for change in tag.changes] == [
            ("Leo", "retired"),
            ("Ana", "proposed"),
        ]

        client.post(decide.format(egov["id"]), json={"decision": "rejected", "user_name": "Mia"})
        undone = client.post(decide.format(egov["id"]), json=undo).json()
        assert (undone["tag_id"], undone["proposal"]["status"]) == (None, "open")
        assert [item["id"] for item in client.get("/v1/proposals").json()["items"]] == [egov["id"]]


def test_undo_leaves_a_topic_alone_that_someone_created_again(conn, settings):
    asyncio.run(group(conn, settings, use_model=False))
    decide = "/v1/proposals/{}/decision"
    with TestClient(create_app(settings)) as client:
        _, velo = client.get("/v1/proposals").json()["items"]
        client.post(decide.format(velo["id"]), json={"decision": "accepted", "user_name": "Mia"})
        client.post("/v1/adhoc/adhoc:velowege/retire", json={"user_name": "Leo"})
        topic = {
            "name_de": "Velowege",
            "description_de": "Geschäfte zu Velowegen, neu gefasst",
            "keywords": {"de": ["Velo"]},
            "user_name": "Ana",
        }
        assert client.post("/v1/adhoc", json=topic).status_code == 200

        undo = {"decision": "undo", "user_name": "Leo"}
        undone = client.post(decide.format(velo["id"]), json=undo).json()
        assert (undone["tag_id"], undone["proposal"]["status"]) == (None, "open")
        tag = load_registry(settings.registry_path).get("adhoc:velowege")
        assert (tag.status, tag.definition.de) == ("proposed", topic["description_de"])
