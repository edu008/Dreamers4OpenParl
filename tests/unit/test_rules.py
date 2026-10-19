"""Regeln für Routinegeschäfte (Vorschlag B)."""

import pytest

from parltopics.classify.rules import match_rule


@pytest.mark.parametrize(
    ("text", "rule", "tag_id"),
    [
        ("Vereidigung eines Parlamentsmitglieds\nText", "vereidigung", "aps:1.2.4"),
        ("Prestation de serment de Mme X, élue juge au Tribunal civil", "vereidigung", "aps:1.2.6"),
        ("Rücktritt von Samuel Wyss als Mitglied des Grossen Rates", "ruecktritt", "aps:1.2.4"),
        ("Rücktritt von Dr. Y als Leitender Staatsanwalt", "ruecktritt", "aps:1.2.6"),
        ("Einbürgerungen 2019; 1. Serie", "einbuergerung", "aps:7.1.5"),
        ("Budget 2027 der Stadt Wil", "budget", "aps:8.2.1"),
        ("Voranschlag 2025; Genehmigung", "budget", "aps:8.2.1"),
        ("Jahresrechnung 2025", "rechnung", "aps:8.2.2"),
    ],
)
def test_routine_titles(text, rule, tag_id):
    found = match_rule(text)
    assert (found.rule, found.tag_id) == (rule, tag_id)
    assert found.evidence == text.split("\n")[0]


@pytest.mark.parametrize(
    "text",
    [
        "Auswirkungen auf das Budget 2027 der Schulen",  # Budget nicht am Anfang
        "Interpellation: Rücktritt aus dem Pensionskassenvertrag",
        "Budgetdebatte ohne Jahr",
        "",
        None,
    ],
)
def test_other_titles_go_to_the_model(text):
    assert match_rule(text) is None
