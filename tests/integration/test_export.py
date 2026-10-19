"""Export affair_topics.ndjson.gz und DVS-Liste gegen ein echtes PostgreSQL (PRD F11, F12)."""

import csv
import gzip
import io
import json

import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb
from typer.testing import CliRunner

from parltopics.api.app import create_app
from parltopics.db import migrate
from parltopics.export import AffairTopic, write_affair_topics, write_dvs_list
from parltopics.registry import file_hash, load_registry
from parltopics.registry.sync import sync_registry
from tests.integration.test_api import FIXTURE, seed

pytestmark = pytest.mark.integration
DVS = "adhoc:digitalisierung-breit"


@pytest.fixture
def labelled(conn, repo_root):
    migrate(conn, repo_root / "migrations")
    sync_registry(conn, load_registry(FIXTURE), file_hash(FIXTURE))
    seed(conn)  # 70435 (CHE): aktiv aps:6.1.9, verlaufen aps:2.4.1
    conn.execute(
        "INSERT INTO bodies (id, body_key, name, level, raw) VALUES"
        " (2, 'ZH', 'Zürich', 'canton', '{}'), (3, '261', 'Zürich', 'city', '{}')"
    )
    affairs = [
        (80001, "ZH", {}),  # Kanton, laufend
        (80002, "ZH", {"end_date": "2025-01-01T00:00:00"}),  # abgeschlossen
        (80003, "261", {}),  # Stadt
        (80004, "CHE", {"active": False}),  # als inaktiv markiert
        (80005, "CHE", {}),
    ]
    for affair_id, body_key, raw in affairs:
        conn.execute(
            "INSERT INTO affairs (id, body_key, title_de, raw) VALUES (%s, %s, %s, %s)",
            (affair_id, body_key, f"Geschäft {affair_id}", Jsonb(raw)),
        )
    label = (
        "INSERT INTO affair_tags (affair_id, tag_id, scheme, confidence, task, stage,"
        " model_version, prompt_version, registry_version, input_hash)"
        " VALUES (%s, %s, 'adhoc', 0.7, 'classify:adhoc', '70b', 'm', 'p', 'v', 'h')"
    )
    for affair_id in (80001, 80002, 80003, 80004):
        conn.execute(label, (affair_id, DVS))
    conn.execute(label, (80005, "adhoc:ki-verwaltung"))  # Thema noch proposed: nicht nach aussen
    return conn


def test_export_writes_active_labels_of_released_topics_and_the_index(labelled, tmp_path):
    assert write_affair_topics(labelled, tmp_path) == 5
    with gzip.open(tmp_path / "affair_topics.ndjson.gz", "rt", encoding="utf-8") as file:
        rows = [AffairTopic.model_validate_json(line) for line in file]
    assert sorted((row.affair_id, row.topic_external_id) for row in rows) == [
        (70435, "aps:6.1.9"),
        (80001, DVS),
        (80002, DVS),
        (80003, DVS),
        (80004, DVS),
    ]
    assert rows[0].topic_de and rows[0].model_version
    (entry,) = json.loads((tmp_path / "index.json").read_text("utf-8"))["files"]
    assert (entry["entity"], entry["row_count"]) == ("affair_topics", 5)
    assert entry["size"] == (tmp_path / "affair_topics.ndjson.gz").stat().st_size


def test_dvs_list_has_running_affairs_of_country_and_cantons(labelled, tmp_path, api_settings):
    assert write_dvs_list(labelled, tmp_path, [DVS]) == 1
    text = (tmp_path / "dvs_liste.csv").read_text(encoding="utf-8")
    rows = list(csv.reader(io.StringIO(text.removeprefix("﻿"), newline=""), delimiter=";"))
    assert [row[0] for row in rows[1:]] == ["80001"]

    with TestClient(create_app(api_settings)) as client:

        def found(**params):
            items = client.get(f"/v1/pages/{DVS}/affairs", params=params).json()["items"]
            return sorted(item["affair_id"] for item in items)

        both = {"level": ["country", "canton"]}
        assert found(**both, running=True) == [80001]
        assert found(**both) == [80001, 80002, 80004]
        assert found(level="city") == [80003]
        assert found() == [80001, 80002, 80003, 80004]
        summary = client.get(f"/v1/pages/{DVS}/affairs/summary", params={"running": True}).json()
        assert summary["affairs"] == 2  # 80001 im Kanton und 80003 in der Stadt


def test_cli_export_writes_both_files(labelled, tmp_path, api_settings, monkeypatch):
    from parltopics.cli import app

    monkeypatch.setattr("parltopics.cli.get_settings", lambda: api_settings)
    result = CliRunner().invoke(app, ["export", "--out", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "5 Labels" in result.output and "1 Zeilen" in result.output
    assert {path.name for path in tmp_path.iterdir()} == {
        "affair_topics.ndjson.gz",
        "dvs_liste.csv",
        "index.json",
    }
    unknown = CliRunner().invoke(app, ["export", "--out", str(tmp_path), "--dvs-topic", "aps:9"])
    assert unknown.exit_code == 2
