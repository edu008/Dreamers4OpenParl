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


def test_a_missing_aps_prefix_is_added_when_the_id_was_offered():
    data = {"affair_id": 1, "language": "de", "chapters": [{"chapter_id": "6.1", "confidence": 1}]}
    assert parse_stage1(data, affair_id=1, offered={"aps:6.1"}).chapters[0].chapter_id == "aps:6.1"
    tags = [{"tag_id": "6.1.9", "confidence": 0.8, "evidence": "x"}]
    result, dropped = parse_stage2(stage2(tags=tags), affair_id=70435, offered=OFFERED_TAGS)
    assert ([t.tag_id for t in result.tags], dropped) == (["aps:6.1.9"], [])


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
        ({"affair_id": 1, "language": "de"}, ValidationError),
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


def test_stage2_keeps_three_best_tags_and_two_proposals():
    offered = {f"adhoc:t{i}" for i in range(7)}
    tags = [{"tag_id": f"adhoc:t{i}", "confidence": i / 10, "evidence": "x"} for i in range(7)]
    proposals = [{"name_de": f"P{i}", "description_de": "d", "reason": "r"} for i in range(3)]
    result, dropped = parse_stage2(
        stage2(tags=tags, proposed_tags=proposals), affair_id=70435, offered=offered
    )
    assert [t.tag_id for t in result.tags] == [f"adhoc:t{i}" for i in (6, 5, 4)]
    assert sorted(dropped) == ["adhoc:t0", "adhoc:t1", "adhoc:t2", "adhoc:t3"]
    assert [p.name_de for p in result.proposed_tags] == ["P0", "P1"]


def test_stage2_counts_a_repeated_tag_once_with_its_highest_confidence():
    tags = [
        {"tag_id": "aps:6.1.9", "confidence": 0.5, "evidence": "schwach"},
        {"tag_id": "aps:6.1.4", "confidence": 0.7, "evidence": "b"},
        {"tag_id": "aps:6.1.9", "confidence": 0.9, "evidence": "stark"},
    ]
    result, dropped = parse_stage2(stage2(tags=tags), affair_id=70435, offered=OFFERED_TAGS)
    assert [(t.tag_id, t.evidence) for t in result.tags] == [
        ("aps:6.1.9", "stark"),
        ("aps:6.1.4", "b"),
    ]
    assert dropped == []


@pytest.mark.parametrize(
    "overrides",
    [
        {"tags": [{"tag_id": "aps:6.1.9", "confidence": 1.5, "evidence": "x"}]},
        {"tags": [{"tag_id": "aps:6.1.9", "confidence": 0.5, "evidence": ""}]},
        {"unexpected": True},
    ],
)
def test_stage2_rejects_invalid_values(overrides):
    with pytest.raises(ValidationError):
        parse_stage2(stage2(**overrides), affair_id=70435, offered=OFFERED_TAGS)


def test_a_long_quote_is_shortened_and_keeps_the_tag():
    quote = "Der Bundesrat kann ausnahmsweise verzichten " * 10
    tags = [{"tag_id": "aps:6.1.9", "confidence": 0.9, "evidence": quote}]
    result, _ = parse_stage2(stage2(tags=tags), affair_id=70435, offered=OFFERED_TAGS)
    (tag,) = result.tags
    assert len(tag.evidence) <= 300
    assert tag.evidence.endswith("…")
    assert quote.startswith(tag.evidence[:-1] + " ")  # Schnitt an einer Wortgrenze


def test_stage2_rejects_wrong_affair():
    with pytest.raises(OutputError):
        parse_stage2(stage2(), affair_id=1, offered=OFFERED_TAGS)


def test_stage2_summary_never_costs_the_tags():
    def parse(data):
        output, _ = parse_stage2(data, affair_id=70435, offered=OFFERED_TAGS)
        return output

    missing = stage2()
    del missing["summary_de"]
    assert parse(missing).summary_de is None
    assert parse(stage2(summary_de="  ")).summary_de is None
    long = parse(stage2(summary_de="Wort " * 100))
    assert len(long.summary_de) <= 300
    assert long.summary_de.endswith("…")
    assert [tag.tag_id for tag in long.tags] == ["aps:6.1.9"]


def test_stage1_accepts_no_matching_chapter():
    output = parse_stage1(
        {"affair_id": 1, "language": "de", "chapters": []}, affair_id=1, offered={"aps:6.1"}
    )
    assert output.chapters == []


def test_single_puts_institutions_behind_topics_and_keeps_three():
    from parltopics.classify.schemas import parse_single

    def t(tag_id, confidence):
        return {"tag_id": tag_id, "confidence": confidence, "evidence": "x"}

    data = {
        "affair_id": 1,
        "language": "de",
        "tags": [t("aps:1.2.4", 0.9), t("aps:6.1.1", 0.5), t("aps:6.1.3", 0.6)],
        "institution_tags": [t("aps:1.2.2", 0.8)],
    }
    topics = {"aps:6.1.1", "aps:6.1.3", "aps:6.4.6"}
    institutions = {"aps:1.2.4", "aps:1.2.2"}
    result, dropped = parse_single(data, affair_id=1, topics=topics, institutions=institutions)
    assert [x.tag_id for x in result.tags] == ["aps:6.1.3", "aps:6.1.1", "aps:1.2.4"]
    assert result.institution_tags == []
    assert dropped == ["aps:1.2.2"]


def test_single_keeps_an_institution_when_no_topic_fits():
    from parltopics.classify.schemas import parse_single

    data = {
        "affair_id": 1,
        "language": "de",
        "tags": [],
        "institution_tags": [{"tag_id": "aps:1.2.4", "confidence": 0.9, "evidence": "x"}],
    }
    result, _ = parse_single(data, affair_id=1, topics={"aps:6.1.1"}, institutions={"aps:1.2.4"})
    assert [x.tag_id for x in result.tags] == ["aps:1.2.4"]
