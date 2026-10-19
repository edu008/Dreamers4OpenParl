from functools import partial

import httpx
from typer.testing import CliRunner

from parltopics import __version__
from parltopics.cli import app
from parltopics.llm import LLMClient

runner = CliRunner()


def test_help_lists_all_commands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in [
        "db",
        "registry",
        "llm",
        "download",
        "ingest",
        "inputs",
        "classify",
        "worker",
        "jobs",
        "adhoc",
        "export",
        "wiki",
        "eval",
    ]:
        assert command in result.output


def test_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.output.strip() == __version__


def test_registry_validate_repository_file(repo_root):
    result = runner.invoke(app, ["registry", "validate", str(repo_root / "registry" / "tags.yaml")])
    assert result.exit_code == 0, result.output
    assert "gültig" in result.output
    assert "scheme_hash" in result.output


def test_registry_validate_reports_errors(tmp_path):
    path = tmp_path / "tags.yaml"
    path.write_text("registry_version: x\nschemes: {}\n", encoding="utf-8")
    assert runner.invoke(app, ["registry", "validate", str(path)]).exit_code == 1


def test_classify_accepts_only_the_aps_task_in_m1():
    result = runner.invoke(app, ["classify", "--task", "classify:adhoc:x"])
    assert result.exit_code == 2
    assert "classify:aps" in result.output


def test_llm_check_lists_the_models_of_the_endpoint_on_a_404(monkeypatch, settings):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/models":
            model = {"id": "apertus-v1-5-8b", "object": "model", "created": 0, "owned_by": "x"}
            return httpx.Response(200, json={"object": "list", "data": [model]})
        return httpx.Response(404, json={"error": {"message": "model not found"}})

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr("parltopics.cli.get_settings", lambda: settings)
    monkeypatch.setattr("parltopics.llm.LLMClient", partial(LLMClient, transport=transport))
    result = runner.invoke(app, ["llm", "check"])
    assert result.exit_code == 1
    assert "NotFoundError" in result.output
    assert "Modelle am Endpunkt: apertus-v1-5-8b" in result.output
