"""Seitenlauf und Markdown-Export mit Datenbank und Mock-LLM (PRD 7.9, F14, F23–F25)."""

import asyncio
import datetime as dt
import json

import httpx
import pytest
import yaml
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from parltopics.api.app import create_app
from parltopics.db import migrate
from parltopics.llm import LLMClient
from parltopics.registry import file_hash, load_registry
from parltopics.registry.sync import sync_registry
from parltopics.wiki.markdown import export_wiki
from parltopics.wiki.run import run
from parltopics.wiki.tree import build_tree, page_path, year_list_path
from tests.integration.test_api import FIXTURE, seed
from tests.mock_llm.app import completion, fake_completion

pytestmark = pytest.mark.integration
NOW = dt.datetime(2026, 10, 19, 6, 0, tzinfo=dt.UTC)
SUMMARY = "Zusammenfassung der Seite (Mock)."
WEB = "http://wiki.test"


class Mock(httpx.MockTransport):
    """Mock-LLM, das die angefragten Modelle mitzählt."""

    def __init__(self) -> None:
        self.models: list[str] = []
        super().__init__(self.answer)

    def answer(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        self.models.append(body["model"])
        return httpx.Response(
            200, json=completion(fake_completion(body["messages"]), body["model"])
        )


@pytest.fixture
def ready(conn, repo_root, api_settings):
    migrate(conn, repo_root / "migrations")
    registry = load_registry(FIXTURE)
    sync_registry(conn, registry, file_hash(FIXTURE))
    seed(conn)  # 70435 (CHE, 2026-03-01): aktiv aps:6.1.9, mit Kurzzusammenfassung
    settings = api_settings.model_copy(update={"page_min_affairs": 1})
    return settings, registry, build_tree(registry)


def page(conn, page_id):
    return conn.execute(
        "SELECT status, summary_short, cited_affair_ids, cited_page_ids, n_affairs,"
        " prompt_version FROM wiki_pages WHERE page_id = %s",
        (page_id,),
    ).fetchone()


def test_page_run_builds_bottom_up_skips_unchanged_and_reopens(conn, ready):
    settings, registry, tree = ready
    mock = Mock()

    first = asyncio.run(run(settings, conn, registry, tree, transport=mock, now=NOW))
    built = {pid for pid, outcome in first.outcomes.items() if outcome == "changed"}
    assert built == {"aps:6.1.9", "aps:6.1", "aps:6", "heart"}  # Weitergabe bis Heart
    assert set(first.outcomes) == set(tree)  # neue Seiten beginnen als open
    assert (set(mock.models), len(mock.models)) == ({settings.llm_name_large}, 4)  # alle mit 70B
    status, short, affairs, pages, n_affairs, version = page(conn, "aps:6.1.9")
    assert (status, short, affairs, pages, n_affairs) == ("done", SUMMARY, [70435], [], 1)
    assert version.startswith("summarize_tag_v1+")
    assert page(conn, "aps:6.1")[3] == ["aps:6.1.9"]  # Kapitel stützt sich auf die Tag-Seite
    assert page(conn, "aps:2.4.1")[1] is None  # ohne aktive Labels keine Zusammenfassung
    events = conn.execute(
        "SELECT count(*), count(*) FILTER (WHERE summary_changed) FROM wiki_page_events"
    ).fetchone()
    assert events == (2 * len(tree), 4)

    second = asyncio.run(run(settings, conn, registry, tree, transport=mock, now=NOW))
    assert (second.outcomes, len(mock.models)) == ({}, 4)  # nichts geändert, kein Aufruf

    conn.execute("UPDATE affair_tags SET status = 'rejected' WHERE tag_id = 'aps:6.1.9'")
    third = asyncio.run(run(settings, conn, registry, tree, transport=mock, now=NOW))
    assert third.outcomes == dict.fromkeys(["aps:6.1.9", "aps:6.1", "aps:6", "heart"], "changed")
    assert (page(conn, "aps:6.1.9")[1], page(conn, "heart")[1], len(mock.models)) == (None, None, 4)


def test_page_detail_shows_the_summary(conn, ready, api_settings):
    settings, registry, tree = ready
    with TestClient(create_app(api_settings)) as client:
        assert client.get("/v1/pages/aps:6.1.9").json()["summary"] is None  # noch kein Lauf
        asyncio.run(run(settings, conn, registry, tree, transport=Mock(), now=NOW))
        summary = client.get("/v1/pages/aps:6.1.9").json()["summary"]
        assert (summary["page_status"], summary["summary_short"], summary["n_affairs"]) == (
            "done",
            SUMMARY,
            1,
        )
        assert summary["statements"][0]["affair_ids"] == [70435]
        assert summary["window_end"] == "2026-10-19"


def test_cli_pages_runs_once_and_reports(conn, ready, monkeypatch):
    from parltopics.cli import app

    settings, _, tree = ready
    mock = Mock()
    monkeypatch.setattr("parltopics.cli.get_settings", lambda: settings)
    monkeypatch.setattr(
        "parltopics.wiki.run.LLMClient",
        lambda settings, transport=None: LLMClient(settings, transport=mock),
    )
    result = CliRunner().invoke(app, ["pages"])
    assert result.exit_code == 0, result.output
    assert f"{len(tree)} von {len(tree)} Seiten gebaut, 4 geändert" in result.output
    assert len(mock.models) == 4


def markdown(root):
    return {p.relative_to(root).as_posix(): p.read_text("utf-8") for p in root.rglob("*.md")}


def export(conn, ready, out):
    _, registry, tree = ready
    return export_wiki(conn, registry, tree, out, web_url=WEB, window_months=12, today=NOW.date())


def test_markdown_export_writes_the_tree_twice_without_diff(conn, ready, tmp_path):
    settings, registry, tree = ready
    asyncio.run(run(settings, conn, registry, tree, transport=Mock(), now=NOW))
    first = export(conn, ready, tmp_path)
    files = markdown(tmp_path)
    assert first == (len(files), len(files))
    assert export(conn, ready, tmp_path) == (len(files), 0)  # zweiter Lauf ohne Diff
    assert markdown(tmp_path) == files

    tag = files[tree["aps:6.1.9"].path]
    head = yaml.safe_load(tag.split("---\n")[1])
    assert (head["tag_id"], head["scheme"], head["n_affairs"], head["page_status"]) == (
        "aps:6.1.9",
        "aps",
        1,
        "done",
    )
    assert head["registry_version"] == registry.registry_version
    assert SUMMARY in tag and f"[70435]({WEB}/geschaefte/70435)" in tag  # Beleg verlinkt
    assert "(../parlamente/CHE.md)" in tag
    assert "(../querschnitt/adhoc-digitalisierung-breit.md)" in tag  # related aus der Registry
    assert f"(../{tree['aps:6.1.9'].path})" in files[tree["aps:6.1"].path]  # Kapitel → Tag-Seite
    assert f"(../{tree['aps:6.1.9'].path}) | 1 |" in files["parlamente/CHE.md"]
    assert "HEART.md" in files and not any(name.startswith("geschaefte/") for name in files)
    merged = files[page_path(registry.get("adhoc:e-government"))]
    assert "aufgegangen" in merged and "(adhoc-digitalisierung-breit.md)" in merged
    assert "nicht mehr vergeben" in files[page_path(registry.get("aps:6.1.10"))]


def test_markdown_export_splits_large_tag_pages_by_year(conn, ready, tmp_path, monkeypatch):
    monkeypatch.setattr("parltopics.wiki.tree.YEAR_SPLIT_THRESHOLD", 0)
    export(conn, ready, tmp_path)
    page = ready[2]["aps:6.1.9"]
    hub = (tmp_path / page.path).read_text("utf-8")
    assert f"]({page.path.removeprefix('tags/').removesuffix('.md')}/2026.md)" in hub
    assert "/geschaefte/70435)" in (tmp_path / year_list_path(page, 2026)).read_text("utf-8")
    assert "/geschaefte/70435)" not in hub  # Liste nur in der Jahresdatei


def test_cli_wiki_exports_the_tree_and_one_affair(conn, ready, monkeypatch, tmp_path):
    from parltopics.cli import app

    settings, _, tree = ready
    monkeypatch.setattr("parltopics.cli.get_settings", lambda: settings)
    result = CliRunner().invoke(app, ["wiki", "--out", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert f"{len(markdown(tmp_path))} Dateien" in result.output

    result = CliRunner().invoke(app, ["wiki", "--out", str(tmp_path), "--affair", "70435"])
    assert result.exit_code == 0, result.output
    affair = (tmp_path / "geschaefte" / "70435.md").read_text("utf-8")
    assert f"(../{tree['aps:6.1.9'].path})" in affair
    assert CliRunner().invoke(app, ["wiki", "--out", str(tmp_path), "--affair", "1"]).exit_code == 1
