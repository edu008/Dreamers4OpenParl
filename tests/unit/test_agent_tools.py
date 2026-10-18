import json

import pytest
from pydantic import ValidationError

from parltopics.agent.tools import (
    MAX_TOOL_CALLS,
    TOOLS,
    SearchAffairsArgs,
    UnknownToolError,
    parse_tool_call,
    tool_definitions,
)

EXPECTED = {
    "search_affairs",
    "list_tags",
    "get_affair",
    "count_affairs",
    "navigate_tree",
    "read_page",
    "generate_keywords",
    "propose_adhoc_topic",
}


def test_tool_set_matches_the_prd():
    assert {spec.name for spec in TOOLS} == EXPECTED
    assert len(TOOLS) == len(EXPECTED)
    assert MAX_TOOL_CALLS == 6


def test_no_tool_writes():
    assert not any(spec.writes for spec in TOOLS)


def test_definitions_are_openai_tools():
    definitions = tool_definitions()
    json.dumps(definitions)
    for definition in definitions:
        assert definition["type"] == "function"
        function = definition["function"]
        assert function["description"]
        assert function["parameters"]["type"] == "object"
        assert function["parameters"].get("additionalProperties") is False


def test_parse_tool_call_from_json_string():
    args = parse_tool_call("search_affairs", '{"query": "KI Verwaltung", "year_from": 2024}')
    assert isinstance(args, SearchAffairsArgs)
    assert args.limit == 10


@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        ("search_affairs", {"query": ""}),
        ("search_affairs", {"query": "x", "limit": 500}),
        ("search_affairs", {"query": "x", "drop_table": True}),
        ("count_affairs", {"group_by": "partei"}),
        ("propose_adhoc_topic", {"name": "KI", "description": "kurz", "keywords": []}),
    ],
)
def test_invalid_arguments_are_rejected(name, arguments):
    with pytest.raises(ValidationError):
        parse_tool_call(name, arguments)


def test_unknown_tool_is_rejected():
    with pytest.raises(UnknownToolError):
        parse_tool_call("delete_affair", {"affair_id": 1})
