"""Ad-hoc-Themen: Stichwörter und Suchausdruck (PRD 7.4, F8)."""

import json
from pathlib import Path

import httpx

from parltopics.classify.adhoc import (
    MAX_TERMS,
    Keywords,
    suggest_keywords,
    tag_keywords,
    websearch,
)
from parltopics.registry import load_registry
from tests.mock_llm.app import completion, fake_completion

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "tags_example.yaml"


def test_tag_keywords_also_take_a_name_without_its_bracket():
    """«Digitalisierung (breit)» als Phrase trifft kaum; der Name ohne Zusatz trifft."""
    tag = load_registry(FIXTURE).get("adhoc:digitalisierung-breit")
    assert tag_keywords(tag).de[:2] == ["Digitalisierung (breit)", "Digitalisierung"]


def test_websearch_quotes_phrases_and_drops_operators():
    terms = ["Velo", "Velo fahren", '"Pedelec"', "-Auto", " "]
    assert websearch(terms) == 'Velo or "Velo fahren" or Pedelec or Auto'
    assert websearch([]) == ""


def test_keywords_are_cleaned_and_capped():
    keywords = Keywords(de=["Velo", " Velo ", "", "Velo  fahren", *map(str, range(40))])
    assert keywords.de[:2] == ["Velo", "Velo fahren"]
    assert len(keywords.de) == MAX_TERMS
    assert (keywords.fr, keywords.it) == ([], [])


async def test_suggest_keywords_asks_the_large_model(settings):
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        requests.append(body)
        return httpx.Response(
            200, json=completion(fake_completion(body["messages"]), body["model"])
        )

    keywords = await suggest_keywords(
        settings, "Velowege", "Geschäfte zum Veloverkehr", transport=httpx.MockTransport(handler)
    )
    assert keywords.fr == ["vélo"]
    assert requests[0]["model"] == "test-70b"
    assert "Velowege" in requests[0]["messages"][-1]["content"]
