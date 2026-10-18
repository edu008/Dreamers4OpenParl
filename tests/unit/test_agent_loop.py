import asyncio
from pathlib import Path

import pytest
from pydantic import ValidationError

from parltopics.agent.execute import Tools
from parltopics.agent.loop import Answer, first_messages, keep_known, parse_reply, run
from parltopics.agent.tools import MAX_TOOL_CALLS, CountAffairsArgs, ListTagsArgs, ToolError
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
    assert messages[5]["content"].startswith("Ergebnis von search_affairs (Daten")
    assert "99" in messages[7]["content"]  # die Rückfrage nennt die unbekannte ID


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


def test_an_answer_without_any_tool_is_sent_back_once():
    unbacked = '{"answer": "Keine passenden Geschäfte gefunden", "cited_ids": []}'
    messages = start()
    ask = scripted(unbacked, ACTION, '{"answer": "Velo [1].", "cited_ids": [1]}')
    outcome = asyncio.run(run(messages, ask, one_affair))
    assert (outcome.status, outcome.cited_ids, outcome.steps) == ("ok", [1], 3)
    assert messages[3]["content"].startswith("Du hast noch kein Werkzeug aufgerufen")
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


def test_first_messages_list_every_tool_and_the_question():
    settings = Settings(_env_file=None, prompts_dir=ROOT / "prompts")
    messages, version = first_messages(settings, "Was macht der Bund?")
    assert version.startswith("agent_system_v1+")
    system = messages[0]["content"]
    for name in ("search_affairs", "count_affairs", "navigate_tree", "propose_adhoc_topic"):
        assert f"- {name}:" in system
    shape = '{"group_by": "body_key" | "level" | "year", "tags": ["…"], "body_keys": ["…"]'
    assert shape in system and "Pflicht: group_by" in system
    assert messages[1] == {"role": "user", "content": "Was macht der Bund?"}
