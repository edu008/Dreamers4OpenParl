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
