from pathlib import Path

import pytest

from parltopics.classify.lexical import LexicalMatcher
from parltopics.registry import load_registry

ROOT = Path(__file__).resolve().parents[2]


def test_lexical_matcher_on_fixture(settings):
    registry = load_registry(settings.registry_path)
    topics = [t for t in registry.active("aps") if t.aps_level == "thema"]
    matcher = LexicalMatcher(topics)

    matches = matcher.match("Massnahmen für den Arbeitsmarkt.")
    matched_ids = {t.tag_id for t in matches}
    assert "aps:8.5.2" in matched_ids

    matches = matcher.match("E-Government und Digitalisierung der Verwaltung.")
    matched_ids = {t.tag_id for t in matches}
    assert "aps:6.1.9" in matched_ids

    assert matcher.match("") == []


def test_lexical_matcher_on_full_registry():
    tags_path = ROOT / "registry" / "tags.yaml"
    if not tags_path.exists():
        pytest.skip("tags.yaml nicht gefunden")
    registry = load_registry(tags_path)
    topics = [t for t in registry.active("aps") if t.aps_level == "thema"]
    matcher = LexicalMatcher(topics)

    # Jagdgesetz test -> aps:8.4.8 Jagd und Fischerei
    matches = matcher.match("Revision des Jagdgesetzes und Schutz des Wolfes.")
    matched_ids = {t.tag_id for t in matches}
    assert "aps:8.4.8" in matched_ids  # Jagd und Fischerei

    # KVG / Krankenkassenprämien test -> aps:5.2.4 Krankenversicherung
    matches = matcher.match("Dämpfung der Prämien gemäss KVG für Familien.")
    matched_ids = {t.tag_id for t in matches}
    assert "aps:5.2.4" in matched_ids  # Krankenversicherung

    # Velo / Veloweg test
    matches = matcher.match("Ausbau der Velowege im Kanton.")
    matched_ids = {t.tag_id for t in matches}
    assert "aps:6.1.1" in matched_ids  # Verkehrspolitik (hat alt_labels Velowege)


def test_lexical_matcher_ignores_pure_stopwords(settings):
    registry = load_registry(settings.registry_path)
    topics = [t for t in registry.active("aps") if t.aps_level == "thema"]
    matcher = LexicalMatcher(topics)

    matches = matcher.match("Der Bundesrat verfasst einen Bericht für das Parlament.")
    matched_ids = {t.tag_id for t in matches}
    assert "aps:1" not in matched_ids
