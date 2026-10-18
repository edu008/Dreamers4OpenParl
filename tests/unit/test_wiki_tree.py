import copy
import datetime as dt
from pathlib import Path

import pytest
import yaml

from parltopics.registry import Registry
from parltopics.wiki.tree import (
    HEART_ID,
    PageState,
    Thresholds,
    TreeError,
    build_tree,
    children,
    linked_querschnitt,
    needs_year_split,
    opened,
    page_ids,
    run_pages,
    should_open,
    year_list_path,
)

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "tags_example.yaml"
NOW = dt.datetime(2026, 10, 18, 12, 0, tzinfo=dt.UTC)


def registry_data() -> dict:
    return yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture
def pages():
    return build_tree(Registry.model_validate(registry_data()))


def done_states(pages, days_ago=1):
    built = NOW - dt.timedelta(days=days_ago)
    return {page_id: PageState(status="done", built_at=built) for page_id in pages}


def test_tree_has_heart_and_one_page_per_active_tag(pages):
    assert page_ids(pages.values()) == [
        "heart",
        "aps:2",
        "aps:2.4",
        "aps:2.4.1",
        "aps:6",
        "aps:6.1",
        "aps:6.1.9",
        "adhoc:digitalisierung-breit",
    ]
    assert [p.page_id for p in children(pages, HEART_ID)] == [
        "aps:2",
        "aps:6",
        "adhoc:digitalisierung-breit",
    ]


def test_paths_are_stable_and_carry_the_tag_id(pages):
    assert pages[HEART_ID].path == "HEART.md"
    assert pages["aps:6"].path == "bereiche/aps-6-infrastruktur-umwelt.md"
    assert pages["aps:6.1"].path == "kapitel/aps-6.1-verkehr-kommunikation.md"
    assert pages["aps:6.1.9"].path == "tags/aps-6.1.9-digitalisierung.md"
    assert pages["adhoc:digitalisierung-breit"].path == "querschnitt/adhoc-digitalisierung-breit.md"
    renamed = registry_data()
    next(t for t in renamed["tags"] if t["tag_id"] == "aps:6.1.9")["pref_label"]["de"] = "Neu"
    assert build_tree(Registry.model_validate(renamed))["aps:6.1.9"].path == pages["aps:6.1.9"].path


def test_querschnitt_hangs_under_heart_and_is_linked_from_chapters(pages):
    breit = pages["adhoc:digitalisierung-breit"]
    assert breit.kind == "querschnitt"
    assert breit.parent_id == HEART_ID
    assert breit.linked_from == ("aps:2.4", "aps:6.1")
    assert [p.page_id for p in linked_querschnitt(pages, "aps:6.1")] == [breit.page_id]
    assert [p.page_id for p in children(pages, "aps:6.1")] == ["aps:6.1.9"]


def test_year_split(pages):
    assert not needs_year_split(1000)
    assert needs_year_split(1001)
    assert year_list_path(pages["aps:6.1.9"], 2025) == "tags/aps-6.1.9-digitalisierung/2025.md"


def test_inactive_parent_breaks_the_tree():
    data = copy.deepcopy(registry_data())
    next(t for t in data["tags"] if t["tag_id"] == "aps:6.1")["status"] = "retired"
    with pytest.raises(TreeError, match=r"aps:6\.1"):
        build_tree(Registry.model_validate(data))


def test_new_affair_opens_the_path_up_to_heart(pages):
    result = run_pages(
        pages,
        done_states(pages),
        {"aps:6.1.9": 1},
        NOW,
        rebuild=lambda page: "changed",
        thresholds=Thresholds(tag_changes=1),
    )
    assert opened(result) == ["aps:6.1.9", "aps:6.1", "aps:6", "heart"]
    assert [e.to_status for e in result.events] == ["open", "pending", "done"] * 4
    assert all(result.states[p].status == "done" for p in opened(result))


def test_below_threshold_the_page_stays_done(pages):
    result = run_pages(
        pages, done_states(pages), {"aps:6.1.9": 1}, NOW, rebuild=lambda p: "changed"
    )
    assert opened(result) == []
    assert result.states["aps:6.1.9"].status == "done"
    assert result.states["aps:6.1.9"].pending_changes == 1


def test_unchanged_summary_stops_the_propagation(pages):
    result = run_pages(
        pages, done_states(pages), {"aps:6.1.9": 5}, NOW, rebuild=lambda page: "unchanged"
    )
    assert opened(result) == ["aps:6.1.9"]


def test_querschnitt_propagates_to_heart_only(pages):
    result = run_pages(
        pages,
        done_states(pages),
        {"adhoc:digitalisierung-breit": 5},
        NOW,
        rebuild=lambda p: "changed",
    )
    assert opened(result) == ["adhoc:digitalisierung-breit", "heart"]


def test_weekly_refresh_and_removed_evidence(pages):
    tag_page = pages["aps:6.1.9"]
    week_old = PageState("done", pending_changes=1, built_at=NOW - dt.timedelta(days=8))
    fresh = PageState("done", pending_changes=1, built_at=NOW - dt.timedelta(days=1))
    removed = PageState("done", pending_changes=0, built_at=NOW, cited_label_removed=True)
    assert should_open(tag_page, week_old, NOW)
    assert not should_open(tag_page, fresh, NOW)
    assert should_open(tag_page, removed, NOW)


def test_new_failed_and_pending_pages(pages):
    tag_page = pages["aps:6.1.9"]
    assert should_open(tag_page, PageState(), NOW)
    assert not should_open(tag_page, PageState("failed", built_at=NOW), NOW)
    assert should_open(tag_page, PageState("failed", pending_changes=1, built_at=NOW), NOW)
    assert not should_open(tag_page, PageState("pending", pending_changes=9, built_at=NOW), NOW)


def test_a_failed_page_stops_its_branch_but_not_the_run(pages):
    def rebuild(page):
        if page.page_id == "aps:6.1.9":
            raise TimeoutError("Endpunkt antwortet nicht")
        return "changed"

    states = done_states(pages)
    result = run_pages(
        pages,
        states,
        {"aps:6.1.9": 5, "adhoc:digitalisierung-breit": 5},
        NOW,
        rebuild=rebuild,
    )
    failed = result.states["aps:6.1.9"]
    assert failed.status == "failed"
    assert failed.last_error == "Endpunkt antwortet nicht"
    assert [e.to_status for e in result.events if e.page_id == "aps:6.1.9"] == [
        "open",
        "pending",
        "failed",
    ]
    assert result.states["aps:6.1"].pending_changes == 0
    assert opened(result) == ["aps:6.1.9", "adhoc:digitalisierung-breit", "heart"]
    assert states["aps:6.1.9"].status == "done"
