import pytest
from pydantic import ValidationError

from parltopics.classify.schemas import OutputError, parse_stage1, parse_stage2

OFFERED_TAGS = {"aps:6.1.9", "aps:6.1.4", "adhoc:digitalisierung-breit"}


def stage2(**overrides) -> dict:
    data = {
        "affair_id": 70435,
        "language": "de",
        "summary_de": "Die Motion verlangt einen Bericht zur digitalen Verwaltung.",
        "tags": [{"tag_id": "aps:6.1.9", "confidence": 0.86, "evidence": "Der Bundesrat wird …"}],
        "proposed_tags": [],
    }
    data.update(overrides)
    return data


def test_stage1_valid():
    data = {
        "affair_id": 1,
        "language": "fr",
        "chapters": [{"chapter_id": "aps:6.1", "confidence": 0.7}],
    }
    assert parse_stage1(data, affair_id=1, offered={"aps:6.1"}).chapters[0].chapter_id == "aps:6.1"


def test_stage1_keeps_three_best_chapters():
    chapters = [{"chapter_id": f"aps:{i}.1", "confidence": i / 10} for i in range(1, 6)]
    data = {"affair_id": 1, "language": "de", "chapters": chapters}
    offered = {c["chapter_id"] for c in chapters}
    result = parse_stage1(data, affair_id=1, offered=offered)
    assert [c.chapter_id for c in result.chapters] == ["aps:5.1", "aps:4.1", "aps:3.1"]


@pytest.mark.parametrize(
    ("data", "error"),
    [
        (
            {
                "affair_id": 2,
                "language": "de",
                "chapters": [{"chapter_id": "aps:6.1", "confidence": 1}],
            },
            OutputError,
        ),
        (
            {
                "affair_id": 1,
                "language": "de",
                "chapters": [{"chapter_id": "aps:9.9", "confidence": 1}],
            },
            OutputError,
        ),
        ({"affair_id": 1, "language": "de", "chapters": []}, ValidationError),
        (
            {
                "affair_id": 1,
                "language": "en",
                "chapters": [{"chapter_id": "aps:6.1", "confidence": 1}],
            },
            ValidationError,
        ),
    ],
)
def test_stage1_rejects(data, error):
    with pytest.raises(error):
        parse_stage1(data, affair_id=1, offered={"aps:6.1"})


def test_stage2_valid():
    result, dropped = parse_stage2(stage2(), affair_id=70435, offered=OFFERED_TAGS)
    assert [t.tag_id for t in result.tags] == ["aps:6.1.9"]
    assert dropped == []


def test_stage2_drops_tags_that_were_not_offered():
    tags = [
        {"tag_id": "aps:6.1.9", "confidence": 0.9, "evidence": "a"},
        {"tag_id": "aps:9.9.9", "confidence": 0.8, "evidence": "b"},
    ]
    result, dropped = parse_stage2(stage2(tags=tags), affair_id=70435, offered=OFFERED_TAGS)
    assert [t.tag_id for t in result.tags] == ["aps:6.1.9"]
    assert dropped == ["aps:9.9.9"]


def test_stage2_keeps_five_best_tags_and_two_proposals():
    offered = {f"adhoc:t{i}" for i in range(7)}
    tags = [{"tag_id": f"adhoc:t{i}", "confidence": i / 10, "evidence": "x"} for i in range(7)]
    proposals = [{"name_de": f"P{i}", "description_de": "d", "reason": "r"} for i in range(3)]
    result, dropped = parse_stage2(
        stage2(tags=tags, proposed_tags=proposals), affair_id=70435, offered=offered
    )
    assert [t.tag_id for t in result.tags] == [f"adhoc:t{i}" for i in (6, 5, 4, 3, 2)]
    assert sorted(dropped) == ["adhoc:t0", "adhoc:t1"]
    assert [p.name_de for p in result.proposed_tags] == ["P0", "P1"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"tags": [{"tag_id": "aps:6.1.9", "confidence": 1.5, "evidence": "x"}]},
        {"tags": [{"tag_id": "aps:6.1.9", "confidence": 0.5, "evidence": "x" * 301}]},
        {"tags": [{"tag_id": "aps:6.1.9", "confidence": 0.5, "evidence": ""}]},
        {"unexpected": True},
        {"summary_de": ""},
        {"summary_de": "x" * 301},
    ],
)
def test_stage2_rejects_invalid_values(overrides):
    with pytest.raises(ValidationError):
        parse_stage2(stage2(**overrides), affair_id=70435, offered=OFFERED_TAGS)


def test_stage2_rejects_wrong_affair():
    with pytest.raises(OutputError):
        parse_stage2(stage2(), affair_id=1, offered=OFFERED_TAGS)


def test_stage2_requires_summary():
    data = stage2()
    del data["summary_de"]
    with pytest.raises(ValidationError):
        parse_stage2(data, affair_id=70435, offered=OFFERED_TAGS)
