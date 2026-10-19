import asyncio
import datetime as dt
from pathlib import Path

import pytest
from pydantic import ValidationError

from parltopics.agent.execute import BODY_NAMES, Tools, translations
from parltopics.agent.loop import (
    DROPPED,
    Answer,
    cited,
    first_messages,
    keep_known,
    parse_reply,
    run,
)
from parltopics.agent.tools import (
    MAX_TOOL_CALLS,
    CountAffairsArgs,
    ListTagsArgs,
    SearchAffairsArgs,
    ToolError,
)
from parltopics.config import Settings
from parltopics.llm import JSONExtractionError
from parltopics.registry import load_registry

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "tags_example.yaml"
ACTION = '{"action": "search_affairs", "args": {"query": "Velo"}}'


def start() -> list[dict]:
    return [{"role": "system", "content": "Regeln"}, {"role": "user", "content": "Velo?"}]


def scripted(*replies: str):
    """Ein Modell, das die Antworten der Reihe nach gibt."""
    queue = list(replies)

    async def ask(messages: list[dict]) -> str:
        return queue.pop(0)

    return ask


async def one_affair(name, args):
    return [{"affair_id": 1}], [1]


class FakeDB:
    """Eine Verbindung: Parlamente für BODY_NAMES, sonst die Gruppen einer Zählung."""

    def __init__(self, bodies: list[tuple], groups: list[dict]):
        self.bodies, self.groups, self.rows = bodies, groups, []

    def cursor(self, row_factory=None):
        return self

    def execute(self, sql, params=None):
        self.rows = self.bodies if sql is BODY_NAMES else self.groups
        return self

    def fetchall(self):
        return self.rows


class FakeFulltext:
    """Volltext: Geschäft 7 nur für Anfragen mit «Numérisation»; merkt sich die Anfragen."""

    def __init__(self):
        self.queries = []

    def cursor(self, row_factory=None):
        return self

    def execute(self, sql, params):
        if isinstance(params, dict):  # die Suche; sonst die Köpfe der Treffer (queries.hits)
            self.queries.append(params["q"])
            return [(7,)] if "Numérisation" in params["q"] else []
        head = {"title": "Numérisation", "body_key": "GE", "body_name": "Genf", "type": None}
        return [
            {"affair_id": i, "body_level": "canton", "begin_date": None, "type_de": None, **head}
            for i in params[0]
        ]


def test_replies_are_tool_calls_or_answers():
    action = parse_reply('Gern: {"action": "list_tags", "args": {"query": "Velo"}}')
    assert (action.action, action.args) == ("list_tags", {"query": "Velo"})
    answer = parse_reply('{"answer": "Siehe [1].", "cited_ids": [1]}')
    assert (answer.answer, answer.cited_ids) == ("Siehe [1].", [1])
    with pytest.raises(JSONExtractionError):
        parse_reply("keine Ahnung")
    with pytest.raises(ValidationError):
        parse_reply('{"answer": ""}')


def test_citations_without_a_tool_result_are_removed():
    answer = Answer(answer="Ja [1], auch [99].", cited_ids=[99])
    assert keep_known(answer, {1}) == ("Ja [1], auch.", [1])
    assert keep_known(Answer(answer="[99]"), {1}) == (None, [])
    # Live-Test: 70B schrieb oft «ID: 61926» statt [61926]; das zählt als Zitat, bleibt im Satz.
    plain = Answer(answer="Motion (ID: 1, 2017) und Postulat (ID 99), nicht COVID 19.")
    assert cited(plain) == [1, 99]
    assert keep_known(plain, {1}) == (plain.answer, [1])


def test_loop_retries_bad_output_calls_a_tool_and_checks_citations():
    messages = start()
    ask = scripted(
        "kein JSON",
        ACTION,
        '{"answer": "Velo [1] und [99].", "cited_ids": [1, 99]}',
        '{"answer": "Velo [1] und [99].", "cited_ids": [1, 99]}',  # bleibt bei der 99
    )
    outcome = asyncio.run(run(messages, ask, one_affair))
    assert (outcome.answer, outcome.cited_ids, outcome.status) == ("Velo [1] und.", [1], "ok")
    assert outcome.steps == 4
    (call,) = outcome.tool_calls
    assert (call["name"], call["args"], call["result_size"]) == (
        "search_affairs",
        {"query": "Velo"},
        len('[{"affair_id": 1}]'),
    )
    assert messages[2]["content"] == DROPPED  # Unbrauchbares bleibt nicht im Gespräch
    assert messages[5]["content"].startswith("Ergebnis von search_affairs (Daten")
    assert "[99]" in messages[7]["content"]  # die Rückfrage nennt die unbekannte ID
    assert "Gelieferte IDs: [1]" in messages[7]["content"]  # und die gelieferten


def test_loop_forces_an_answer_after_the_tool_limit_or_the_timeout():
    async def ask(messages: list[dict]) -> str:
        if messages[-1]["content"].startswith("Keine Werkzeugaufrufe mehr"):
            return '{"answer": "Keine passenden Geschäfte gefunden", "cited_ids": []}'
        return ACTION

    outcome = asyncio.run(run(start(), ask, one_affair))
    assert (len(outcome.tool_calls), outcome.steps) == (MAX_TOOL_CALLS, MAX_TOOL_CALLS + 2)
    assert (outcome.status, outcome.answer) == (
        "limit_reached",
        "Keine passenden Geschäfte gefunden",
    )
    late = asyncio.run(run(start(), ask, one_affair, timeout=0))
    assert (late.tool_calls, late.status) == ([], "limit_reached")


def test_bad_tool_arguments_go_back_to_the_model():
    ask = scripted(
        '{"action": "count_affairs", "args": {"group_by": "partei"}}',
        '{"answer": "Keine passenden Geschäfte gefunden", "cited_ids": []}',
    )
    outcome = asyncio.run(run(start(), ask, one_affair))
    (call,) = outcome.tool_calls
    assert call["error"] and outcome.status == "no_results"
    # Eine gelungene Zählung belegt eine Antwort mit Zahlen, auch ohne Zitate.
    count = '{"action": "count_affairs", "args": {"group_by": "level"}}'
    counted = asyncio.run(run(start(), scripted(count, '{"answer": "Kantone: 3"}'), one_affair))
    assert (counted.status, counted.cited_ids) == ("ok", [])


def test_a_draft_backs_an_answer_without_citations():
    async def draft(name, args):
        return {"name_de": "KI", "candidates": 12, "examples": []}, []

    args = '{"name": "KI", "description": "KI in Behörden", "keywords": ["KI"]}'
    propose = f'{{"action": "propose_adhoc_topic", "args": {args}}}'
    answer = '{"answer": "Entwurf mit 12 Kandidaten."}'
    outcome = asyncio.run(run(start(), scripted(propose, answer), draft))
    assert (outcome.status, outcome.proposal["candidates"]) == ("ok", 12)


def test_an_answer_without_any_tool_is_sent_back_once():
    unbacked = '{"answer": "Keine passenden Geschäfte gefunden", "cited_ids": []}'
    messages = start()
    ask = scripted(unbacked, ACTION, '{"answer": "Velo [1].", "cited_ids": [1]}')
    outcome = asyncio.run(run(messages, ask, one_affair))
    assert (outcome.status, outcome.cited_ids, outcome.steps) == ("ok", [1], 3)
    assert messages[3]["content"].startswith("Du hast noch kein Werkzeug aufgerufen")
    assert messages[2]["content"] == DROPPED  # erfundene Inhalte bleiben nicht im Gespräch
    stubborn = asyncio.run(run(start(), scripted(unbacked, unbacked), one_affair))
    assert (stubborn.status, stubborn.steps, stubborn.tool_calls) == ("no_results", 2, [])


def test_list_tags_matches_names_aliases_and_definitions():
    tools = Tools(settings=None, conn=None, registry=load_registry(FIXTURE), tree={})
    found, ids = asyncio.run(tools.list_tags(ListTagsArgs(query="Digitale Transformation")))
    assert (found[0]["tag_id"], ids) == ("aps:6.1.9", [])
    assert all(tag["status"] in ("active", "proposed") for tag in found)


def test_tags_must_come_from_a_tool_and_include_their_subtopics():
    tools = Tools(settings=None, conn=None, registry=load_registry(FIXTURE), tree={})
    count = CountAffairsArgs(group_by="level", tags=["aps:6.1"])
    with pytest.raises(ToolError, match="list_tags"):  # erfunden: kein Werkzeug lieferte aps:6.1
        asyncio.run(tools("count_affairs", count))
    found, _ = asyncio.run(tools("list_tags", ListTagsArgs(query="Verkehr")))
    assert "aps:6.1" in {tag["tag_id"] for tag in found}
    assert {"aps:6.1", "aps:6.1.9"} <= set(tools._expand(["aps:6.1"]))


def test_counts_name_their_scope_and_parliaments_must_exist():
    db = FakeDB(bodies=[("BS", "Basel-Stadt", "canton")], groups=[{"key": 2026, "count": 3}])
    tools = Tools(settings=None, conn=db, registry=load_registry(FIXTURE), tree={})
    by_year = CountAffairsArgs(group_by="year", body_keys=["BS"])
    with pytest.raises(ToolError, match="all_affairs"):  # Live-Test: Zählung aller als Thema
        asyncio.run(tools("count_affairs", by_year))
    every = by_year.model_copy(update={"all_affairs": True})
    found, _ = asyncio.run(tools("count_affairs", every))
    assert found["gezählt"]["parlamente"] == ["BS Basel-Stadt (canton)"]
    assert found["gezählt"]["themen"].startswith("keine: alle Geschäfte")
    db.bodies = [("TI", "Tessin", "canton")]  # «Tessin» passt nur zum Namen, nicht zum Kürzel
    search = SearchAffairsArgs(query="Gewässerschutz", body_keys=["Tessin"])
    with pytest.raises(ToolError, match=r"\['Tessin'\].*TI Tessin \(canton\)"):
        asyncio.run(tools("search_affairs", search))


def test_translations_are_the_labels_of_the_best_matching_tag():
    registry = load_registry(FIXTURE)
    digital = ["Digitalisierung", "Numérisation", "Digitalizzazione", "E-Government"]
    digital += ["Digitale Transformation", "Digitalisirung"]
    assert translations(registry, "Quidditch") == []
    assert translations(registry, "e-government") == digital  # adhoc:e-government: zusammengelegt
    # Ganze Wörter: «Arbeit» trifft das Kapitel, nicht «Arbeitsmarkt»; jeder Teil zwischen «or».
    assert translations(registry, "Arbeit or digitalisirung") == ["Arbeit", *digital]
    # Die bevorzugte Bezeichnung schlägt das Sammelthema, das sie als alternative führt.
    registry.get("adhoc:digitalisierung-breit").alt_labels.fr.append("Numérisation")
    assert translations(registry, "numérisation der Verwaltung") == digital


def test_search_fills_up_with_the_topic_in_other_languages():
    tools = Tools(settings=None, conn=FakeFulltext(), registry=load_registry(FIXTURE), tree={})
    # Testfragen F21: der deutsche Begriff findet in Genf nichts, die Bezeichnung auf Französisch
    found, ids = asyncio.run(tools.search_affairs(SearchAffairsArgs(query="Digitalisierung")))
    assert (ids, found[0]["parliament"]) == ([7], "Genf")
    assert tools.conn.queries[0] == "Digitalisierung" and "Numérisation" in tools.conn.queries[1]
    tools.conn.queries.clear()  # genug Treffer oder kein Thema: keine zweite Suche
    asyncio.run(tools.search_affairs(SearchAffairsArgs(query="Numérisation", limit=1)))
    asyncio.run(tools.search_affairs(SearchAffairsArgs(query="Quidditch")))
    assert tools.conn.queries == ["Numérisation", "Quidditch"]


def test_first_messages_list_every_tool_and_the_question():
    settings = Settings(_env_file=None, prompts_dir=ROOT / "prompts")
    messages, version = first_messages(settings, "Was macht der Bund?")
    assert version.startswith("agent_system_v2+")
    system = messages[0]["content"]
    assert "Bleibe politisch neutral" in system and "keine Empfehlungen" in system  # PRD 7.9
    for name in ("search_affairs", "count_affairs", "navigate_tree", "propose_adhoc_topic"):
        assert f"- {name}:" in system
    shape = '{"group_by": "body_key" | "level" | "year", "tags": ["…"], "body_keys": ["…"]'
    assert shape in system and "Pflicht: group_by" in system
    assert '"all_affairs": false}' in system  # das Modell übernimmt die Form: Standard bleibt aus
    assert f"Heute ist der {dt.date.today().isoformat()}." in system
    assert messages[1] == {"role": "user", "content": "Was macht der Bund?"}
