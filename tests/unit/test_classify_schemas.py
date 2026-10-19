import pytest
from pydantic import ValidationError

from parltopics.classify.schemas import OutputError, TagAssignment, parse_stage1, parse_stage2

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


def test_tag_assignment_fit_calibrates_confidence():
    # kern_explizit max 0.90 (mit und ohne expliziter Zahl, Vorschlag D)
    t1 = TagAssignment(evidence="Zitat", fit="kern_explizit", tag_id="aps:6.1.9", confidence=0.95)
    assert t1.confidence == 0.90
    t1_cat = TagAssignment.model_validate(
        {"evidence": "Zitat", "fit": "kernthema", "tag_id": "aps:6.1.9"}
    )
    assert t1_cat.confidence == 0.90
    assert t1_cat.fit == "kern_explizit"

    # nebenaspekt_explizit max 0.75
    t2 = TagAssignment(
        evidence="Zitat", fit="nebenaspekt_explizit", tag_id="aps:6.1.9", confidence=0.88
    )
    assert t2.confidence == 0.75

    # implizit_abgeleitet max 0.55
    t3 = TagAssignment(
        evidence="Zitat", fit="implizit_abgeleitet", tag_id="aps:6.1.9", confidence=0.90
    )
    assert t3.confidence == 0.55

    # unsicher / weak max 0.35
    t4 = TagAssignment(evidence="Zitat", fit="weak", tag_id="aps:6.1.9", confidence=0.80)
    assert t4.confidence == 0.35
    assert t4.fit == "unsicher"

    # ohne fit bleibt Original-Konfidenz
    t5 = TagAssignment(evidence="Zitat", tag_id="aps:6.1.9", confidence=0.86)
    assert t5.confidence == 0.86


def test_stage2_respects_max_tags():
    tags = [{"evidence": "z", "tag_id": f"aps:6.1.{i}", "confidence": 0.8} for i in range(5)]
    offered = {f"aps:6.1.{i}" for i in range(5)}
    result, dropped = parse_stage2(stage2(tags=tags), affair_id=70435, offered=offered, max_tags=2)
    assert len(result.tags) == 2
    assert len(dropped) == 3


def test_stage2_separates_sachthema_and_actors():
    """Vorschlag A: Akteure (Bundesrat, Parlament, Kantone) in tags verdrängen Sachthemen nicht."""
    offered = {"aps:1.2.1", "aps:1.2.4", "aps:1.2.8", "aps:6.1.2"}
    tags = [
        {"tag_id": "aps:1.2.1", "confidence": 0.90, "evidence": "Bundesrat"},
        {"tag_id": "aps:1.2.8", "confidence": 0.88, "evidence": "Kantone"},
        {"tag_id": "aps:1.2.4", "confidence": 0.85, "evidence": "Parlament"},
        {"tag_id": "aps:6.1.2", "confidence": 0.75, "evidence": "Zahnradbahn Altstätten-Gais"},
    ]
    result, dropped = parse_stage2(stage2(tags=tags), affair_id=70435, offered=offered)
    assert [t.tag_id for t in result.tags] == ["aps:6.1.2"]
    assert set(dropped) == {"aps:1.2.1", "aps:1.2.4", "aps:1.2.8"}

    # Explizites institution_tags wird ergänzt, wenn das Geschäft auch die Institution regelt
    data_with_inst = stage2(
        tags=[{"tag_id": "aps:6.1.2", "confidence": 0.90, "evidence": "Bahn"}],
        institution_tags=[
            {"tag_id": "aps:1.2.4", "confidence": 0.85, "evidence": "Geschäftsordnung"}
        ],
    )
    res2, _ = parse_stage2(data_with_inst, affair_id=70435, offered=offered)
    assert [t.tag_id for t in res2.tags] == ["aps:6.1.2", "aps:1.2.4"]
