import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from parltopics import __version__
from parltopics.api.app import create_app
from parltopics.api.queries import nest_languages
from parltopics.api.schemas import ReviewIn
from parltopics.config import Settings

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "tags_example.yaml"


def client_for(dist: Path, registry: Path = FIXTURE) -> TestClient:
    """Ohne `with`: die App startet nicht, ihr Datenbank-Pool bleibt geschlossen."""
    settings = Settings(_env_file=None, web_dist_dir=dist, registry_path=registry)
    return TestClient(create_app(settings))


@pytest.fixture
def built(tmp_path) -> Path:
    """Ein minimaler Build wie aus `vite build`."""
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><div id=root></div>", encoding="utf-8")
    (dist / "assets" / "index-abc123.js").write_text("console.log(1)", encoding="utf-8")
    (dist / "favicon.svg").write_text("<svg/>", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("geheim", encoding="utf-8")
    return dist


def test_healthz(tmp_path):
    response = client_for(tmp_path).get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}


def test_openapi_without_cdn_docs(built):
    client = client_for(built)
    assert client.get("/v1/openapi.json").status_code == 200
    for path in ("/docs", "/redoc"):
        text = client.get(path).text.lower()
        assert "swagger" not in text
        assert "redoc" not in text
        assert "cdn" not in text


def test_swagger_ui_is_served_from_the_package(built):
    client = client_for(built)
    page = client.get("/v1/docs").text
    assert "http://" not in page
    assert "https://" not in page
    assert '"validatorUrl": null' in page
    assets = re.findall(r'(?:src|href)="(/v1/docs/static/[^"]+)"', page)
    assert len(assets) == 2
    for asset in assets:
        assert client.get(asset).status_code == 200
    css = client.get("/v1/docs/static/swagger-ui.css").text
    assert "@import" not in css
    assert "url(http" not in css


def test_openapi_lists_the_endpoints_for_the_frontend(tmp_path):
    schema = client_for(tmp_path).get("/v1/openapi.json").json()
    paths = schema["paths"]
    assert {
        "/healthz",
        "/v1/pages",
        "/v1/pages/{page_id}",
        "/v1/jobs/summary",
        "/v1/topics",
        "/v1/affairs/{affair_id}/topics",
        "/v1/topics/{tag_id}/affairs",
        "/v1/reviews",
        "/v1/reviews/queue",
        "/v1/pages/{page_id}/affairs",
        "/v1/bodies",
        "/v1/search",
        "/v1/stats",
        "/v1/eval/calibration",
        "/v1/eval/gold",
        "/v1/graph/topics",
        "/v1/topics/{tag_id}/related",
        "/v1/adhoc/keywords",
        "/v1/adhoc/preview",
        "/v1/adhoc",
        "/v1/adhoc/{tag_id}/activate",
        "/v1/adhoc/{tag_id}/retire",
        "/v1/proposals",
        "/v1/proposals/{proposal_id}/decision",
        "/v1/search/navigate",
        "/v1/affairs/{affair_id}",
        "/v1/affairs/{affair_id}/docs",
        "/v1/docs/{doc_id}",
        "/v1/bodies/{body_key}",
        "/v1/graph/topics/{tag_id}",
        "/v1/graph/affairs/{affair_id}",
        "/v1/reviews/summary",
        "/v1/pages/{page_id}/affairs/summary",
        "/v1/pages/{page_id}/affairs.csv",
        "/v1/agent/search",
    } <= set(paths)
    parameters = paths["/v1/reviews/queue"]["get"]["parameters"]
    assert {"state", "tag_id", "body_key", "page_id", "reason"} <= {p["name"] for p in parameters}
    parameters = paths["/v1/topics/{tag_id}/affairs"]["get"]["parameters"]
    names = {parameter["name"] for parameter in parameters}
    assert {"tag_id", "body_key", "from", "to", "min_confidence", "limit", "offset"} <= names
    parameters = paths["/v1/pages/{page_id}/affairs"]["get"]["parameters"]
    assert {"page_id", "level", "type", "from", "to"} <= {p["name"] for p in parameters}
    parameters = paths["/v1/search"]["get"]["parameters"]
    names = {"q", "topic", "body_key", "level", "from", "to", "limit", "offset"}
    assert names <= {p["name"] for p in parameters}
    (q,) = [p for p in parameters if p["name"] == "q"]
    assert not q.get("required", False)  # ohne q: die neuesten Geschäfte
    facts = {"external_id", "title_long", "type_name", "state", "end_date"}
    assert facts <= set(schema["components"]["schemas"]["AffairTopics"]["properties"])


def test_database_endpoints_answer_503_without_database(tmp_path):
    client = client_for(tmp_path)
    paths = ("/v1/jobs/summary", "/v1/topics", "/v1/affairs/1/topics", "/v1/reviews/queue")
    for path in (*paths, "/v1/bodies", "/v1/stats", "/v1/eval/calibration", "/v1/eval/gold"):
        assert client.get(path).status_code == 503
    for path in ("/v1/affairs/1", "/v1/affairs/1/docs", "/v1/docs/1", "/v1/bodies/GE"):
        assert client.get(path).status_code == 503
    assert client.get("/healthz").status_code == 200


def test_language_fields_are_nested_like_openparldata():
    record = {
        "id": 257,
        "name": "Genf",  # flach und geschachtelt: die geschachtelte Form gilt
        "name_de": "Genf",
        "name_fr": "Genève",
        "state_name_de": None,
        "state_name_fr": None,
        "type_harmonized_id": 6,
        "end_date": None,
    }
    assert nest_languages(record) == {
        "id": 257,
        "type_harmonized_id": 6,
        "end_date": None,
        "name": {"de": "Genf", "fr": "Genève"},
        "state_name": {},
    }


def test_reviews_need_no_token_only_the_database(tmp_path):
    body = {"affair_id": 1, "tag_id": "aps:6.1.9", "action": "confirm", "user_name": "Mia"}
    assert client_for(tmp_path).post("/v1/reviews", json=body).status_code == 503


@pytest.mark.parametrize(
    "broken",
    [
        {"action": "change"},
        {"new_tag_id": "aps:2.4.1"},
        {"action": "change", "new_tag_id": "aps:6.1.9"},
        {"action": "delete"},
        {"user_name": "  "},
    ],
)
def test_review_body_is_checked(broken):
    body = {"affair_id": 1, "tag_id": "aps:6.1.9", "action": "confirm", "user_name": " Mia "}
    assert ReviewIn(**body).user_name == "Mia"
    with pytest.raises(ValidationError):
        ReviewIn(**{**body, **broken})


def test_without_build_a_hint_page_without_external_urls(tmp_path):
    response = client_for(tmp_path / "fehlt").get("/")
    assert response.status_code == 200
    assert "make web-build" in response.text
    assert "http://" not in response.text
    assert "https://" not in response.text


def test_spa_routes_return_index_and_files_are_served(built):
    client = client_for(built)
    for route in ("/", "/admin/themen/aps:6.1.9", "/admin", "/geschaefte/70435"):
        response = client.get(route)
        assert response.status_code == 200, route
        assert 'id="root"' in response.text or "id=root" in response.text
        assert response.headers["cache-control"] == "no-cache"
    asset = client.get("/assets/index-abc123.js")
    assert asset.text == "console.log(1)"
    assert "immutable" in asset.headers["cache-control"]
    assert client.get("/favicon.svg").text == "<svg/>"
    assert client.head("/").status_code == 200


def test_missing_assets_and_api_paths_are_404_not_index(built):
    client = client_for(built)
    assert client.get("/assets/fehlt.js").status_code == 404
    response = client.get("/v1/gibt-es-nicht")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")


@pytest.mark.parametrize("path", ["/../secret.txt", "/..%2fsecret.txt", "/%2e%2e/secret.txt"])
def test_no_files_outside_dist(built, path):
    response = client_for(built).get(path)
    assert "geheim" not in response.text


def test_page_tree_from_registry(tmp_path):
    response = client_for(tmp_path).get("/v1/pages")
    assert response.status_code == 200
    data = response.json()
    assert data["registry_version"]
    pages = {page["page_id"]: page for page in data["pages"]}
    assert data["pages"][0]["page_id"] == "heart"
    assert pages["aps:6.1.9"]["path"] == "tags/aps-6.1.9-digitalisierung.md"
    assert pages["aps:6.1.9"]["parent_id"] == "aps:6.1"
    assert pages["adhoc:digitalisierung-breit"]["linked_from"] == ["aps:2.4", "aps:6.1"]


def test_page_detail_shows_definition_aliases_and_related_topics(tmp_path):
    client = client_for(tmp_path)
    detail = client.get("/v1/pages/aps:6.1.9").json()
    assert detail["definition"] == "Geschäfte zur Digitalisierung (Testdaten)"
    assert detail["alt_labels"] == ["E-Government", "Digitale Transformation"]
    assert [page["page_id"] for page in detail["related"]] == ["adhoc:digitalisierung-breit"]
    french = client.get("/v1/pages/aps:6.1.9", params={"lang": "fr"}).json()
    assert french["page"]["title"] == "Numérisation"
    assert french["definition"] == "Geschäfte zur Digitalisierung (Testdaten)"  # nur Deutsch
    heart = client.get("/v1/pages/heart").json()
    assert (heart["definition"], heart["alt_labels"], heart["related"]) == (None, [], [])


def test_page_tree_reports_a_broken_registry(tmp_path):
    broken = tmp_path / "tags.yaml"
    broken.write_text("registry_version: [", encoding="utf-8")
    response = client_for(tmp_path, registry=broken).get("/v1/pages")
    assert response.status_code == 503
    assert "Seitenbaum nicht verfügbar" in response.json()["detail"]


def test_invalid_path_is_404_not_500(built):
    assert client_for(built).get("/%00").status_code == 404


def test_adhoc_keywords_come_from_the_model_or_503(tmp_path, monkeypatch):
    import json

    import httpx

    from parltopics.llm import LLMClient
    from tests.mock_llm.app import completion, fake_completion

    def answer(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        return httpx.Response(200, json=completion(fake_completion(body["messages"]), "m"))

    def unreachable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("kein LLM")

    body = {"name_de": "Velowege", "description_de": "Geschäfte zum Veloverkehr"}
    for handler, status in ((answer, 200), (unreachable, 503)):
        mock = httpx.MockTransport(handler)
        monkeypatch.setattr(
            "parltopics.classify.adhoc.LLMClient",
            lambda settings, transport=None, mock=mock: LLMClient(settings, transport=mock),
        )
        response = client_for(tmp_path).post("/v1/adhoc/keywords", json=body)
        assert response.status_code == status
    assert client_for(tmp_path).post("/v1/adhoc/keywords", json={"name_de": "V"}).status_code == 422
