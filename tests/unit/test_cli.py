from typer.testing import CliRunner

from parltopics import __version__
from parltopics.cli import NOT_IMPLEMENTED_EXIT, app

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


def test_planned_commands_name_their_milestone():
    result = runner.invoke(app, ["export"])
    assert result.exit_code == NOT_IMPLEMENTED_EXIT


def test_classify_accepts_only_the_aps_task_in_m1():
    result = runner.invoke(app, ["classify", "--task", "classify:adhoc:x"])
    assert result.exit_code == 2
    assert "classify:aps" in result.output
