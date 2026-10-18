from fastapi.testclient import TestClient

from parltopics import __version__
from parltopics.api.app import app

client = TestClient(app)


def test_healthz():
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__}


def test_pages_load_no_external_assets():
    html = client.get("/").text
    css = client.get("/static/style.css").text
    assert "ParlTopics" in html
    for text in (html, css):
        assert "http://" not in text
        assert "https://" not in text


def test_openapi_without_cdn_docs():
    assert client.get("/v1/openapi.json").status_code == 200
    assert client.get("/docs").status_code == 404
