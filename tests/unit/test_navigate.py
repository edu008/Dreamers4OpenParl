import pytest

from parltopics.search.navigate import (
    Filters,
    Limits,
    NavigationError,
    NavigationStep,
    navigate,
    parse_answer,
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
    seen_filters, model_calls = [], []

    def score(query, page_id, kids, first):
        model_calls.append(page_id)
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
        model_calls.append(page_id)
        chosen = [c for c in candidates if c in relevant]
        return {
            "selected_ids": chosen,
            "statements": [{"text": "Passt zur Frage.", "affair_ids": [c]} for c in chosen],
        }

    callbacks = dict(
        children=lambda page_id: TREE.get(page_id, []),
        score=score,
        leaf_candidates=leaf_candidates,
        select=select,
        fulltext=lambda query, filters: list(fulltext_ids),
    )
    return callbacks, seen_filters, model_calls


def test_descends_along_the_best_branch():
    callbacks, seen_filters, _ = make()
    result = navigate("KI in der Verwaltung seit 2024", **callbacks)
    assert result.status == "ok"
    assert result.affair_ids == [101]
    assert result.path == ["heart", "aps:6", "aps:6.1", "aps:6.1.9"]
    assert result.steps == 4
    assert not result.fallback_used
    assert seen_filters[0].year_from == 2024
    assert [s.affair_ids for s in result.statements] == [[101]]


def test_backtracks_to_the_next_best_sibling():
    callbacks, _, _ = make(relevant=frozenset({201}))
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
    callbacks, _, _ = make(relevant=frozenset({501}), fulltext_ids=(501, 502), relevance=low)
    result = navigate("etwas anderes", **callbacks)
    assert result.fallback_used
    assert result.path == ["volltext"]
    assert result.affair_ids == [501]
    assert result.status == "ok"


def test_step_limit_triggers_the_fallback():
    callbacks, _, _ = make(relevant=frozenset({201}))
    result = navigate("Arbeitsmarkt", **callbacks, limits=Limits(max_steps=3))
    assert result.fallback_used
    assert result.status == "limit_reached"
    assert result.affair_ids == []


@pytest.mark.parametrize("max_steps", [1, 3, 8])
def test_fallback_counts_towards_the_step_limit(max_steps):
    low = {key: 0.9 for key in RELEVANCE}
    callbacks, _, model_calls = make(relevant=frozenset({501}), fulltext_ids=(501,), relevance=low)
    result = navigate("nichts im Baum", **callbacks, limits=Limits(max_steps=max_steps))
    assert result.steps == len(model_calls) <= max_steps
    assert model_calls[-1] == "volltext"


def test_nothing_found_gives_no_results():
    callbacks, _, _ = make(relevant=frozenset())
    result = navigate("nichts", **callbacks)
    assert result.status == "no_results"
    assert result.affair_ids == []
    assert result.statements == []


def test_parse_step_drops_invented_and_duplicate_pages():
    step = parse_step(
        {
            "scores": [
                {"page_id": "aps:6", "relevance": 0.5},
                {"page_id": "aps:6", "relevance": 0.8},
                {"page_id": "aps:99", "relevance": 0.9},
            ]
        },
        {"aps:6"},
    )
    assert [(s.page_id, s.relevance) for s in step.scores] == [("aps:6", 0.8)]
    with pytest.raises(NavigationError):
        parse_step({"scores": [{"page_id": "aps:99", "relevance": 0.9}]}, {"aps:6"})


def test_duplicate_scores_do_not_use_both_branches():
    def score(query, page_id, kids, first):
        return NavigationStep.model_validate(
            {
                "scores": [
                    {"page_id": "aps:6", "relevance": 0.9},
                    {"page_id": "aps:6", "relevance": 0.8},
                    {"page_id": "aps:2", "relevance": 0.6},
                ]
            }
            if page_id == "heart"
            else {"scores": [{"page_id": k, "relevance": 0.9} for k in kids]}
        )

    callbacks, _, _ = make()
    callbacks["score"] = score
    result = navigate("Frage", **callbacks)
    assert result.visits[0].ranked == ["aps:6", "aps:2"]


def test_parse_selection_keeps_only_offered_ids():
    assert parse_selection([3, 1, 3, 9], [1, 2, 3]) == [3, 1]


def test_parse_answer_keeps_only_statements_about_selected_affairs():
    answer = parse_answer(
        {
            "selected_ids": [1, 9],
            "statements": [
                {"text": "Belegt.", "affair_ids": [1]},
                {"text": "Nicht gewählt.", "affair_ids": [2]},
                {"text": "Erfunden.", "affair_ids": [9]},
                {"text": "Ohne Beleg."},
            ],
        },
        offered=[1, 2],
    )
    assert answer.selected_ids == [1]
    assert [s.text for s in answer.statements] == ["Belegt."]
    empty = parse_answer(
        {"selected_ids": [], "statements": [{"text": "x", "affair_ids": [1]}]}, [1]
    )
    assert empty.statements == []
