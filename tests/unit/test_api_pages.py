import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from parltopics.api import app as app_module
from parltopics.api.app import create_app
from parltopics.config import Settings

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "tags_example.yaml"


def client_for(registry: Path = FIXTURE) -> TestClient:
    return TestClient(create_app(Settings(registry_path=registry, web_dist_dir=registry.parent)))


def titles(data: dict) -> dict[str, str]:
    return {page["page_id"]: page["title"] for page in data["pages"]}


def test_root_has_a_display_title_but_keeps_its_internal_id():
    data = client_for().get("/v1/pages").json()
    root = data["pages"][0]
    assert root["page_id"] == "heart"
    assert root["path"] == "HEART.md"
    assert root["title"] == "Themen"
    assert data["lang"] == "de"


def test_titles_follow_the_language_and_fall_back_to_german():
    data = client_for().get("/v1/pages", params={"lang": "fr"}).json()
    found = titles(data)
    assert data["lang"] == "fr"
    assert found["heart"] == "Thèmes"
    assert found["aps:6"] == "Infrastructure et environnement"
    assert found["aps:2"] == "Wirtschaft"  # kein Französisch in der Registry


def test_unknown_language_is_rejected():
    assert client_for().get("/v1/pages", params={"lang": "xx"}).status_code == 422


def test_page_detail_returns_ancestors_children_and_links():
    client = client_for()
    leaf = client.get("/v1/pages/aps:2.4.1").json()
    assert leaf["page"]["title"] == "Arbeitsmarkt"
    assert [page["page_id"] for page in leaf["ancestors"]] == ["heart", "aps:2", "aps:2.4"]
    assert leaf["children"] == []

    chapter = client.get("/v1/pages/aps:2.4").json()
    assert [page["page_id"] for page in chapter["children"]] == ["aps:2.4.1"]
    assert [page["page_id"] for page in chapter["linked"]] == ["adhoc:digitalisierung-breit"]

    adhoc = client.get("/v1/pages/adhoc:digitalisierung-breit").json()
    assert [page["page_id"] for page in adhoc["linked"]] == ["aps:2.4", "aps:6.1"]


def test_page_detail_uses_the_requested_language():
    data = client_for().get("/v1/pages/aps:6", params={"lang": "fr"}).json()
    assert data["page"]["title"] == "Infrastructure et environnement"
    assert data["ancestors"][0]["title"] == "Thèmes"


def test_unknown_page_is_404():
    response = client_for().get("/v1/pages/aps:99")
    assert response.status_code == 404
    assert "aps:99" in response.json()["detail"]


def test_registry_is_parsed_once_and_reloaded_when_the_file_changes(tmp_path, monkeypatch):
    registry = tmp_path / "tags.yaml"
    shutil.copy(FIXTURE, registry)
    calls = []
    real = app_module.load_registry
    monkeypatch.setattr(app_module, "load_registry", lambda path: calls.append(path) or real(path))
    client = client_for(registry)

    client.get("/v1/pages")
    client.get("/v1/pages/aps:2")
    client.get("/v1/pages", params={"lang": "fr"})
    assert len(calls) == 1

    registry.write_text(
        registry.read_text(encoding="utf-8").replace("Arbeitsmarkt", "Arbeitsmarkt neu"),
        encoding="utf-8",
    )
    assert titles(client.get("/v1/pages").json())["aps:2.4.1"] == "Arbeitsmarkt neu"
    assert len(calls) == 2


def test_a_broken_registry_is_not_cached(tmp_path):
    registry = tmp_path / "tags.yaml"
    registry.write_text("registry_version: [", encoding="utf-8")
    client = client_for(registry)
    assert client.get("/v1/pages").status_code == 503
    shutil.copy(FIXTURE, registry)
    assert client.get("/v1/pages").status_code == 200


@pytest.mark.parametrize("path", ["/v1/pages/heart", "/v1/pages/aps:2"])
def test_detail_pages_exist_for_root_and_areas(path):
    assert client_for().get(path).status_code == 200
