from datetime import datetime
from functools import partial
from pathlib import Path

import httpx
import typer
from typer.testing import CliRunner

from parltopics import __version__
from parltopics.cli import app
from parltopics.llm import LLMClient

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "tags_example.yaml"

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
        "daily",
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


STEPS = ["ingest", "inputs", "registry_sync", "classify", "proposals_group", "pages", "export"]
# nach APS je aktivem Ad-hoc-Tag der Test-Registry ein classify (ADR 0009)
DAILY_STEPS = [*STEPS[:4], "classify", *STEPS[4:], "wiki"]


def test_daily_runs_every_step_in_order_and_stops_at_the_first_failure(monkeypatch, settings):
    calls = []

    def step(name, fail=False):
        def run(**kwargs):
            calls.append((name, kwargs))
            if fail:
                raise typer.Exit(code=1)

        return run

    for name in {*DAILY_STEPS}:
        monkeypatch.setattr(f"parltopics.cli.{name}", step(name))
    fixture = settings.model_copy(update={"registry_path": FIXTURE})
    monkeypatch.setattr("parltopics.cli.get_settings", lambda: fixture)
    result = runner.invoke(app, ["daily", "--body", "CHE", "--since", "2026-01-01"])
    assert result.exit_code == 0, result.output
    assert [name for name, _ in calls] == DAILY_STEPS
    scope = {"body": ["CHE"], "since": datetime(2026, 1, 1)}
    assert (calls[1][1], calls[3][1]) == (scope, {"task": "classify:aps", **scope})
    assert calls[4][1] == {"task": "classify:adhoc:digitalisierung-breit", **scope}

    calls.clear()
    monkeypatch.setattr("parltopics.cli.classify", step("classify", fail=True))
    assert runner.invoke(app, ["daily"]).exit_code == 1
    assert [name for name, _ in calls] == DAILY_STEPS[:4]  # nach dem Fehler läuft nichts mehr


def test_classify_refuses_tasks_without_an_adhoc_tag():
    for task in ("classify:adhoc:gibt-es-nicht", "foo"):
        result = runner.invoke(app, ["classify", "--task", task])
        assert result.exit_code == 2
        assert "classify:adhoc:<tag>" in result.output


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
