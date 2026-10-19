"""Rechnungen des Evaluationsberichts (PRD F16, 13)."""

import pytest

from parltopics.evaluation.metrics import Counts, Share, bands, node, path_recall, score


def test_a_share_always_shows_its_denominator():
    assert str(Share(2, 3)) == "2/3 (67 %)"
    assert str(Share(0, 0)) == "–"
    assert Counts(tp=2, fp=1, fn=3).precision == Share(2, 3)
    assert Counts(tp=2, fp=1, fn=3).recall == Share(2, 5)


@pytest.mark.parametrize(
    ("tag_id", "level", "expected"),
    [
        ("aps:6.1.9", "bereich", "aps:6"),
        ("aps:6.1.9", "kapitel", "aps:6.1"),
        ("aps:6.1.9", "thema", "aps:6.1.9"),
        ("aps:6.1", "thema", None),
        ("adhoc:velowege", "bereich", None),
    ],
)
def test_levels_come_from_the_tag_id(tag_id, level, expected):
    assert node(tag_id, level) == expected


def test_a_wrong_topic_in_the_right_chapter_is_a_partial_hit():
    gold = {1: {"aps:6.1.9": False, "aps:6.1.3": True}}
    labels = {1: {"aps:6.1.9"}}
    assert score(labels, gold, "thema") == Counts(tp=0, fp=1, fn=1)
    assert score(labels, gold, "kapitel") == Counts(tp=1)
    assert score(labels, gold, "bereich") == Counts(tp=1)


def test_a_rejected_topic_without_a_confirmed_sibling_is_wrong_on_every_level():
    gold = {1: {"aps:6.1.9": False}}
    assert score({1: {"aps:6.1.9"}}, gold, "bereich") == Counts(fp=1)


def test_only_decided_pairs_count():
    gold = {1: {"aps:2.4.1": True}, 2: {"aps:6.1.9": True}}
    labels = {1: {"aps:2.4.1", "aps:6.4.6", "adhoc:velowege"}, 3: {"aps:2.4.1"}}
    # aps:6.4.6 und adhoc:velowege ohne Entscheid, Geschäft 3 ohne Gold, Geschäft 2 ohne Label
    assert score(labels, gold, "thema") == Counts(tp=1, fn=1)


def test_bands_follow_prd_13_and_show_the_precision_from_each_threshold():
    decisions = [
        (0.5, False, False),
        (0.6, True, True),  # Untergrenze gehört ins Band
        (0.65, False, False),
        (0.7, True, False),
        (0.95, True, True),
        (1.0, False, False),
    ]
    result = {(band.low, band.high): band for band in bands(decisions)}
    assert list(result) == [(0.0, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, None)]
    assert result[(0.0, 0.6)].labels == Share(0, 1)
    assert result[(0.6, 0.7)].labels == Share(1, 2)
    assert result[(0.6, 0.7)].sample == Share(1, 1)
    assert result[(0.8, 0.9)].labels == Share(0, 0)
    assert result[(0.9, None)].labels == Share(1, 2)
    assert result[(0.6, 0.7)].from_low == Share(3, 5)
    assert result[(0.9, None)].from_low == Share(1, 2)


def test_the_candidate_path_splits_keyword_and_classifier_recall():
    recall = path_recall(positives={1, 2, 3, 4}, candidates={1, 2, 3, 9}, labelled={1, 2, 4})
    assert recall.candidates == Share(3, 4)  # 4 hat keinen Stichworttreffer
    assert recall.classifier == Share(2, 3)  # 3 ist Kandidat, aber ohne Label
    assert recall.overall == Share(3, 4)  # 4 fand die Stichprobe
