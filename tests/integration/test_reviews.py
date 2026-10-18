"""Review-Entscheide über POST /v1/reviews gegen ein echtes PostgreSQL (PRD F9)."""

import pytest
from fastapi.testclient import TestClient

from parltopics.api.app import create_app
from parltopics.db import migrate
from parltopics.registry import file_hash, load_registry
from parltopics.registry.sync import sync_registry
from tests.integration.test_api import FIXTURE, seed

pytestmark = pytest.mark.integration

TOKEN = {"Authorization": "Bearer geheim"}


@pytest.fixture
def client(conn, repo_root, api_settings):
    migrate(conn, repo_root / "migrations")
    sync_registry(conn, load_registry(FIXTURE), file_hash(FIXTURE))
    seed(conn)  # aktiv: aps:6.1.9 (0.86); verlaufen: aps:2.4.1
    with TestClient(create_app(api_settings)) as client:
        yield client


def review(client, action, tag_id="aps:6.1.9", **extra):
    body = {"affair_id": 70435, "tag_id": tag_id, "action": action, "user_name": " Mia ", **extra}
    return client.post("/v1/reviews", json=body, headers=TOKEN)


def state(response, tag_id="aps:6.1.9"):
    """(status, review_status, reviewed_by, stage) des neuesten nicht verlaufenen Labels."""
    labels = [
        label
        for label in response.json()["labels"]
        if label["tag_id"] == tag_id and label["status"] != "superseded"
    ]
    if not labels:
        return None
    label = max(labels, key=lambda label: label["id"])
    return label["status"], label["review_status"], label["reviewed_by"], label["stage"]


def logged(conn):
    return conn.execute("SELECT action, new_tag_id, user_name FROM reviews ORDER BY id").fetchall()


def test_confirm_and_undo(client, conn):
    response = review(client, "confirm")
    assert response.status_code == 200
    assert state(response) == ("active", "confirmed", "Mia", "70b")
    assert response.json()["labels"][0]["reviewed_at"] is not None
    response = review(client, "undo")
    assert state(response) == ("active", None, None, "70b")
    assert response.json()["labels"][0]["reviewed_at"] is None
    assert review(client, "undo").status_code == 404  # nichts mehr zurückzunehmen
    assert logged(conn) == [("confirm", None, "Mia"), ("undo", None, "Mia")]


def test_reject_and_undo_restores_the_label(client):
    assert state(review(client, "reject")) == ("rejected", "rejected", "Mia", "70b")
    assert review(client, "confirm").status_code == 404  # kein aktives Label mehr
    assert state(review(client, "undo")) == ("active", None, None, "70b")


def test_change_sets_a_human_label_and_two_undos_restore_the_old_state(client, conn):
    response = review(client, "change", new_tag_id="aps:2.4.1", comment="Arbeitsmarkt")
    assert response.status_code == 200
    assert state(response) == ("rejected", "changed", "Mia", "70b")
    assert state(response, "aps:2.4.1") == ("active", "confirmed", "Mia", "human")
    added = next(label for label in response.json()["labels"] if label["stage"] == "human")
    assert (added["confidence"], added["evidence"], added["input_hash"]) == (1.0, None, "h1")
    assert added["model_version"] == "human"

    assert state(review(client, "undo", tag_id="aps:2.4.1"), "aps:2.4.1") is None
    assert state(review(client, "undo")) == ("active", None, None, "70b")
    assert logged(conn) == [
        ("change", "aps:2.4.1", "Mia"),
        ("undo", None, "Mia"),
        ("undo", None, "Mia"),
    ]
    old_id = conn.execute(
        "SELECT id FROM affair_tags WHERE tag_id = 'aps:6.1.9' AND status = 'active'"
    ).fetchone()[0]
    first = conn.execute("SELECT affair_tag_id, comment FROM reviews ORDER BY id LIMIT 1")
    assert first.fetchone() == (old_id, "Arbeitsmarkt")


def test_add_once_per_topic(client):
    response = review(client, "add", tag_id="adhoc:digitalisierung-breit")
    assert state(response, "adhoc:digitalisierung-breit") == ("active", "confirmed", "Mia", "human")
    assert review(client, "add", tag_id="adhoc:digitalisierung-breit").status_code == 409
    assert review(client, "add").status_code == 409  # aps:6.1.9 hat schon ein aktives Label


def test_unknown_labels_and_topics_change_nothing(client, conn):
    assert review(client, "confirm", tag_id="aps:2.4.1").status_code == 404  # nur verlaufen
    for tag_id in ("aps:9.9", "adhoc:ki-verwaltung", "aps:6.1.10"):  # fehlt, proposed, retired
        assert review(client, "add", tag_id=tag_id).status_code == 404
    assert review(client, "change", new_tag_id="aps:9.9").status_code == 404
    affair = client.get("/v1/affairs/70435/topics")
    assert state(affair) == ("active", None, None, "70b")  # change zurückgerollt
    assert logged(conn) == []


def test_undo_without_migration_0004_is_503_and_changes_nothing(client, conn):
    conn.execute("ALTER TABLE reviews DROP CONSTRAINT reviews_action_check")
    conn.execute(
        "ALTER TABLE reviews ADD CONSTRAINT reviews_action_check"
        " CHECK (action IN ('confirm', 'reject', 'change', 'add'))"
    )
    review(client, "confirm")
    response = review(client, "undo")
    assert response.status_code == 503
    assert "0004" in response.json()["detail"]
    assert state(client.get("/v1/affairs/70435/topics")) == ("active", "confirmed", "Mia", "70b")


def test_wrong_token_is_401(client):
    body = {"affair_id": 70435, "tag_id": "aps:6.1.9", "action": "confirm", "user_name": "Mia"}
    wrong = {"Authorization": "Bearer falsch"}
    assert client.post("/v1/reviews", json=body, headers=wrong).status_code == 401
