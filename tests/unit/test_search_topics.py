"""Themen in einer Suchanfrage erkennen: Registry, Tippfehler, Vorschlag von 8B (F15)."""

import json
from pathlib import Path

import httpx
import pytest

from parltopics.api.queries import terms_sql
from parltopics.llm import JSONExtractionError
from parltopics.registry import load_registry
from parltopics.search import topics
from parltopics.wiki.tree import build_tree
from tests.mock_llm.app import completion

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "tags_example.yaml"
DIGITAL = ["Digitalisierung", "Numérisation", "Digitalizzazione"]


def vocabulary(registry=None) -> topics.Vocabulary:
    registry = registry or load_registry(FIXTURE)
    return topics.Vocabulary(registry, build_tree(registry))


def found(query: str, vocab=None) -> list[tuple]:
    plan = topics.understand(vocab or vocabulary(), query)
    return [(f.tag_id, f.typed, f.label, f.typo) for f in plan.found]


def test_topics_are_found_by_name_without_accents_and_with_typos():
    assert found("Digitalisierung") == [("aps:6.1.9", "Digitalisierung", "Digitalisierung", False)]
    assert found("numerisation") == [("aps:6.1.9", "numerisation", "Numérisation", False)]
    assert found("Digitalisierug") == [("aps:6.1.9", "Digitalisierug", "Digitalisierung", True)]
    assert found("Wirtschaf") == [("aps:2", "Wirtschaf", "Wirtschaft", True)]
    assert found("Arbei") == []  # unter sechs Buchstaben nur genau
    assert found("Arbeitsmarktes") == [("aps:2.4.1", "Arbeitsmarktes", "Arbeitsmarkt", True)]
    # zusammengeschrieben wie die Bezeichnung mit Bindestrich; zusammengelegte Tags zählen nicht
    assert found("egovernment") == [("aps:6.1.9", "egovernment", "E-Government", False)]
    assert found("KI in der Verwaltung") == []  # nur vorgeschlagen, nicht aktiv
    assert found("Quidditch") == []


def test_the_preferred_label_wins_and_the_rank_uses_the_name_the_query_means():
    registry = load_registry(FIXTURE)
    registry.get("adhoc:digitalisierung-breit").alt_labels.fr.append("Numérisation")
    vocab = vocabulary(registry)
    assert found("numérisation", vocab)[0][0] == "aps:6.1.9"  # bevorzugt vor alternativ
    (group,) = topics.understand(vocab, "Digitalisierung").groups
    assert list(group.names.values()) == DIGITAL  # beim Namen genannt: alle Namen für den Rang
    assert "E-Government" in group.terms["de"] and group.terms[None] == ["Digitalisirung"]
    (group,) = topics.understand(vocab, "E-Government").groups
    assert group.names == {"de": "E-Government"}  # ein Synonym: nur es zählt für den Rang


def test_parts_between_or_keep_their_other_words_and_operators_keep_the_query():
    plan = topics.understand(vocabulary(), "Arbeit or Digitalisierung der Schule")
    first, second = plan.branches
    assert ([g.tag_id for g in first.groups], first.rest) == (["aps:2.4"], ())
    assert ([g.tag_id for g in second.groups], second.rest) == (["aps:6.1.9"], ("der", "schule"))
    # Geschäfte mit Label nur für den Teil, der genau ein Thema ist: Kapitel samt Thema
    assert {"aps:2.4", "aps:2.4.1"} <= set(plan.labelled) and "aps:6.1.9" not in plan.labelled
    assert plan.terms()["fr"] == ["Numérisation"] and topics.as_typed("Arbeit").terms() == {}
    for query in ('"Digitalisierung"', "Digitalisierung -Velo"):
        assert topics.understand(vocabulary(), query).found == ()


def test_the_search_sql_names_every_topic_in_its_language_and_the_rest_in_all():
    plan = topics.understand(vocabulary(), "Digitalisierung der Schule")
    match, rank, params = terms_sql(plan)
    assert "websearch_to_tsquery('french'" in match and "ts_lexize('german_stem'" in match
    assert "Numérisation" in params.values() and ["der", "schule"] in params.values()
    assert rank.count("websearch_to_tsquery('italian'") == 2  # die Anfrage und «Digitalizzazione»


def llm(reply: str, requests: list) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        requests.append(body)
        return httpx.Response(200, json=completion(reply, body["model"]))

    return httpx.MockTransport(handler)


async def test_8b_suggests_topics_only_from_the_registry_and_once_per_query(settings):
    topics._suggested.clear()
    requests: list[dict] = []
    reply = '{"topics": ["digitalisierung", "gibt-es-nicht", "wirtschaf", "arbeit"]}'
    query = "Behördeninformatik"
    plan = await topics.suggest(settings, vocabulary(), query, transport=llm(reply, requests))
    # ein falsch abgeschriebener Schlüssel zählt, wenn er eine Bezeichnung trifft; höchstens zwei
    assert [(f.tag_id, f.source) for f in plan.found] == [("aps:6.1.9", "llm"), ("aps:2", "llm")]
    assert (plan.model_version, requests[0]["model"]) == ("test-8b", "test-8b")
    assert plan.prompt_version.startswith("search_topics_v1+")
    system, user = requests[0]["messages"]
    assert "digitalisierung | Digitalisierung | Numérisation" in system["content"]
    assert query in user["content"]
    assert (plan.branches[0].text, plan.branches[1].text) == (query, None)
    again = await topics.suggest(settings, vocabulary(), query.lower(), transport=llm("", requests))
    assert ([f.tag_id for f in again.found], len(requests)) == (["aps:6.1.9", "aps:2"], 1)
    with pytest.raises(JSONExtractionError):
        await topics.suggest(settings, vocabulary(), "Raumfahrt", transport=llm("keine Ahnung", []))
