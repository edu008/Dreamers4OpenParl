import pytest

from parltopics.wiki.schemas import SummaryError, parse_page_summary

ALLOWED = {
    "allowed_affairs": {70435, 71002},
    "allowed_pages": {"aps:6.1.9"},
    "allowed_numbers": {"12", "2025", "1234"},
}


def summary(*statements, short="Digitalisierung prägt die Vorstösse.") -> dict:
    return {"summary_short": short, "statements": list(statements)}


def test_supported_statements_are_kept():
    data = summary(
        {"text": "12 Geschäfte betreffen die Verwaltung.", "affair_ids": [70435]},
        {"text": "Das Thema hängt mit der Unterseite zusammen.", "page_ids": ["aps:6.1.9"]},
    )
    output, dropped = parse_page_summary(data, **ALLOWED)
    assert len(output.statements) == 2
    assert dropped == []


@pytest.mark.parametrize(
    "statement",
    [
        {"text": "Ohne Beleg."},
        {"text": "Erfundene ID.", "affair_ids": [99999]},
        {"text": "Unbekannte Seite.", "page_ids": ["aps:9.9"]},
        {"text": "Es sind 47 Geschäfte.", "affair_ids": [70435]},
    ],
)
def test_unsupported_statements_are_dropped(statement):
    data = summary({"text": "Belegt.", "affair_ids": [71002]}, statement)
    output, dropped = parse_page_summary(data, **ALLOWED)
    assert [s.text for s in output.statements] == ["Belegt."]
    assert len(dropped) == 1


def test_thousand_separators_are_normalised():
    data = summary({"text": "Insgesamt 1'234 Geschäfte.", "affair_ids": [70435]})
    output, _ = parse_page_summary(data, **ALLOWED)
    assert len(output.statements) == 1


def test_no_supported_statement_fails_the_page():
    with pytest.raises(SummaryError):
        parse_page_summary(summary({"text": "Ohne Beleg."}), **ALLOWED)


def test_short_summary_must_not_invent_numbers():
    data = summary({"text": "Belegt.", "affair_ids": [70435]}, short="Seit 2019 viele Vorstösse.")
    with pytest.raises(SummaryError):
        parse_page_summary(data, **ALLOWED)
