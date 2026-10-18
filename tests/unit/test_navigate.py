import pytest

from parltopics.search.navigate import (
    Filters,
    Limits,
    NavigationError,
    NavigationStep,
    navigate,
    parse_selection,
    parse_step,
)

TREE = {
    "heart": ["aps:2", "aps:6", "adhoc:x"],
    "aps:6": ["aps:6.1"],
    "aps:6.1": ["aps:6.1.9"],
    "aps:2": ["aps:2.4"],
    "aps:2.4": ["aps:2.4.1"],
}
RELEVANCE = {
    "aps:6": 0.9,
    "aps:2": 0.6,
    "adhoc:x": 0.1,
    "aps:6.1": 0.8,
    "aps:6.1.9": 0.9,
    "aps:2.4": 0.7,
    "aps:2.4.1": 0.8,
}
LEAVES = {"aps:6.1.9": [101, 102], "aps:2.4.1": [201], "adhoc:x": [301]}


def make(relevant=frozenset({101}), fulltext_ids=(), relevance=RELEVANCE):
    seen_filters = []

    def score(query, page_id, kids, first):
        filters = Filters(year_from=2024) if first else None
        return NavigationStep.model_validate(
            {
                "scores": [{"page_id": k, "relevance": relevance[k]} for k in kids],
                "filters": filters.model_dump() if filters else None,
            }
        )

    def leaf_candidates(page_id, filters):
        seen_filters.append(filters)
        return LEAVES.get(page_id, [])

    def select(query, page_id, candidates):
        return [c for c in candidates if c in relevant]

    callbacks = dict(
        children=lambda page_id: TREE.get(page_id, []),
        score=score,
        leaf_candidates=leaf_candidates,
        select=select,
        fulltext=lambda query, filters: list(fulltext_ids),
    )
    return callbacks, seen_filters


def test_descends_along_the_best_branch():
    callbacks, seen_filters = make()
    result = navigate("KI in der Verwaltung seit 2024", **callbacks)
    assert result.status == "ok"
    assert result.affair_ids == [101]
    assert result.path == ["heart", "aps:6", "aps:6.1", "aps:6.1.9"]
    assert result.steps == 4
    assert not result.fallback_used
    assert seen_filters[0].year_from == 2024


def test_backtracks_to_the_next_best_sibling():
    callbacks, _ = make(relevant=frozenset({201}))
    result = navigate("Arbeitsmarkt", **callbacks)
    assert result.path == ["heart", "aps:2", "aps:2.4", "aps:2.4.1"]
    assert [v.page_id for v in result.visits] == [
        "heart",
        "aps:6",
        "aps:6.1",
        "aps:6.1.9",
        "aps:2",
        "aps:2.4",
        "aps:2.4.1",
    ]


def test_falls_back_to_fulltext_when_no_branch_is_relevant():
    low = {key: 0.1 for key in RELEVANCE}
    callbacks, _ = make(relevant=frozenset({501}), fulltext_ids=(501, 502), relevance=low)
    result = navigate("etwas anderes", **callbacks)
    assert result.fallback_used
    assert result.path == ["volltext"]
    assert result.affair_ids == [501]
    assert result.status == "ok"


def test_step_limit_triggers_the_fallback():
    callbacks, _ = make(relevant=frozenset({201}))
    result = navigate("Arbeitsmarkt", **callbacks, limits=Limits(max_steps=3))
    assert result.fallback_used
    assert result.status == "limit_reached"
    assert result.affair_ids == []


def test_nothing_found_gives_no_results():
    callbacks, _ = make(relevant=frozenset())
    result = navigate("nichts", **callbacks)
    assert result.status == "no_results"
    assert result.affair_ids == []


def test_parse_step_drops_invented_pages():
    step = parse_step(
        {
            "scores": [
                {"page_id": "aps:6", "relevance": 0.5},
                {"page_id": "aps:99", "relevance": 0.9},
            ]
        },
        {"aps:6"},
    )
    assert [s.page_id for s in step.scores] == ["aps:6"]
    with pytest.raises(NavigationError):
        parse_step({"scores": [{"page_id": "aps:99", "relevance": 0.9}]}, {"aps:6"})


def test_parse_selection_keeps_only_offered_ids():
    assert parse_selection([3, 1, 3, 9], [1, 2, 3]) == [3, 1]
