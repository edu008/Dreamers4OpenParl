"""Review-Entscheide über POST /v1/reviews gegen ein echtes PostgreSQL (PRD F9)."""

import pytest
from fastapi.testclient import TestClient

from parltopics.api.app import create_app
from parltopics.db import migrate
from parltopics.registry import file_hash, load_registry
from parltopics.registry.sync import sync_registry
from tests.integration.test_api import FIXTURE, seed

pytestmark = pytest.mark.integration


@pytest.fixture
def client(conn, repo_root, api_settings):
    migrate(conn, repo_root / "migrations")
    sync_registry(conn, load_registry(FIXTURE), file_hash(FIXTURE))
    seed(conn)  # aktiv: aps:6.1.9 (0.86); verlaufen: aps:2.4.1
    with TestClient(create_app(api_settings)) as client:
        yield client


def review(client, action, tag_id="aps:6.1.9", **extra):
    body = {"affair_id": 70435, "tag_id": tag_id, "action": action, "user_name": " Mia ", **extra}
    return client.post("/v1/reviews", json=body)


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


def add_label(conn, affair_id, tag_id, confidence, evidence, verified):
    conn.execute(
        "INSERT INTO affair_tags (affair_id, tag_id, scheme, confidence, evidence,"
        " evidence_verified, task, stage, model_version, prompt_version, registry_version,"
        " input_hash) VALUES (%s, %s, split_part(%s, ':', 1), %s, %s, %s, 'classify:aps', '8b',"
        " 'm', 'p1', 'v', 'h')",
        (affair_id, tag_id, tag_id, confidence, evidence, verified),
    )


def test_queue_lists_open_labels_with_reasons_and_decided_ones_as_done(client, conn):
    conn.execute(
        "INSERT INTO bodies (id, body_key, name, level, raw)"
        " VALUES (2, 'ZH', 'Zürich', 'canton', '{}')"
    )
    conn.execute(
        "INSERT INTO affairs (id, body_key, title_de, raw)"
        " VALUES (70450, 'CHE', 'Stichprobe', '{}'), (70451, 'ZH', 'Ohne Beleg', '{}')"
    )
    add_label(conn, 70435, "aps:2.4.1", 0.4, "steht nicht im Text", False)
    add_label(conn, 70450, "aps:6.1.9", 0.9, "belegt", True)  # 70450 % 50 == 0
    add_label(conn, 70451, "adhoc:digitalisierung-breit", 0.7, None, False)

    queue = client.get("/v1/reviews/queue").json()
    assert (queue["threshold"], queue["total"]) == (0.6, 3)  # aps:6.1.9 an 70435 ohne Grund
    rows = [(row["affair_id"], row["label"]["tag_id"], row["reasons"]) for row in queue["items"]]
    assert rows == [
        (70435, "aps:2.4.1", ["low_confidence", "evidence_unverified"]),
        (70451, "adhoc:digitalisierung-breit", ["no_evidence"]),
        (70450, "aps:6.1.9", ["sample"]),
    ]
    assert (queue["items"][1]["body_name"], queue["items"][1]["title"]) == ("Zürich", "Ohne Beleg")
    only = client.get("/v1/reviews/queue", params={"tag_id": "aps:6.1.9"}).json()
    assert [item["affair_id"] for item in only["items"]] == [70450]
    assert client.get("/v1/reviews/queue", params={"body_key": "ZH"}).json()["total"] == 1
    page = client.get("/v1/reviews/queue", params={"limit": 1, "offset": 1}).json()
    assert (page["total"], [item["affair_id"] for item in page["items"]]) == (3, [70451])

    review(client, "confirm", tag_id="aps:2.4.1")
    # an 70435 gibt es kein aktives adhoc-Label: nichts ändert sich
    assert review(client, "reject", tag_id="adhoc:digitalisierung-breit").status_code == 404
    assert client.get("/v1/reviews/queue").json()["total"] == 2
    done = client.get("/v1/reviews/queue", params={"state": "done"}).json()
    (item,) = done["items"]
    label = item["label"]
    assert (label["tag_id"], label["review_status"], label["reviewed_by"]) == (
        "aps:2.4.1",
        "confirmed",
        "Mia",
    )
    assert item["reasons"] == ["low_confidence", "evidence_unverified"]
