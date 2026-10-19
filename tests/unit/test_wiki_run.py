import datetime as dt

from parltopics.wiki.run import allowed_numbers, months_before, prompt_stats, tidy


def test_a_too_long_short_summary_is_cut_at_a_word():
    long = "Die Parlamente berieten " + "sehr " * 60 + "viel."
    cut = tidy({"summary_short": long, "statements": []})["summary_short"]
    assert len(cut) <= 200 and cut.endswith("sehr…")
    assert tidy({"summary_short": "kurz"}) == {"summary_short": "kurz"}


def test_months_before_wraps_years_and_clamps_days():
    assert months_before(dt.date(2026, 10, 19), 12) == dt.date(2025, 10, 19)
    assert months_before(dt.date(2026, 1, 31), 1) == dt.date(2025, 12, 28)
    assert months_before(dt.date(2026, 3, 15), 14) == dt.date(2025, 1, 15)


def test_numbers_in_the_prompt_come_only_from_the_stats():
    stats = {
        "affairs": 120,
        "in_window": 30,
        "bodies": 4,
        "by_level": [{"level": "canton", "count": 30}],
        "by_year": [{"year": 2026, "count": 30}, {"year": None, "count": 2}],
        "by_body": [{"body_key": "ZH", "name": "Zürich", "count": 30}],
        "by_type": [{"type": "Motion", "type_de": "Motion", "count": 12}],
    }
    shown = prompt_stats(stats, 12)
    assert (shown["nach Ebene"], shown["nach Jahr"]) == ("Kanton 30", "2026: 30")
    numbers = allowed_numbers(shown, dt.date(2025, 10, 19), dt.date(2026, 10, 19))
    assert {"120", "30", "4", "12", "2026", "2025", "19"} <= numbers
    assert "99" not in numbers
