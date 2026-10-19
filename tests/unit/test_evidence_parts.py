from parltopics.classify.queue import evidence_parts


def test_ellipsis_splits_and_short_parts_drop():
    parts = evidence_parts("Der Bundesrat wird beauftragt … die Prämienverbilligung … zu")
    assert parts == ["Der Bundesrat wird beauftragt", "die Prämienverbilligung"]


def test_typographic_quotes_and_dashes_are_unified():
    assert evidence_parts("«Netto-Null» – bis 2050") == ['"Netto-Null" - bis 2050']
