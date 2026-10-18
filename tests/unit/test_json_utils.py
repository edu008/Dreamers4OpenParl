import pytest

from parltopics.llm import JSONExtractionError, extract_json


def test_plain_json():
    assert extract_json('{"affair_id": 1, "tags": []}') == {"affair_id": 1, "tags": []}


def test_fenced_json():
    text = 'Hier das Ergebnis:\n```json\n{"affair_id": 2}\n```\nDanke.'
    assert extract_json(text) == {"affair_id": 2}


def test_text_around_json():
    assert extract_json('Antwort: {"a": {"b": [1, 2]}} Ende') == {"a": {"b": [1, 2]}}


def test_braces_in_prose_before_json():
    assert extract_json('Menge {x} und dann {"ok": true}') == {"ok": True}


@pytest.mark.parametrize("text", ["", "kein JSON", "[1, 2, 3]", '{"offen": '])
def test_no_object_raises(text):
    with pytest.raises(JSONExtractionError):
        extract_json(text)


def test_control_characters_inside_strings():
    """Echter Fall (Lauf 6, 19.10.2026): 70B schrieb NUL statt „ä“ in einen Beleg.

    Ohne Toleranz fiel der Parser auf das innere Tag-Objekt zurück und die Antwort galt als
    ungültig. NUL wird entfernt (PostgreSQL lehnt es ab), andere Steuerzeichen bleiben.
    """
    text = '{"affair_id": 1, "tags": [{"tag_id": "aps:6.1.3", "evidence": "gem\x00ss\tASTRA"}]}'
    assert extract_json(text) == {
        "affair_id": 1,
        "tags": [{"tag_id": "aps:6.1.3", "evidence": "gemss\tASTRA"}],
    }
