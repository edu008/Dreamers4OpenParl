"""Testfragen des Agenten (PRD F21, Abschnitt 13) schreibgeschützt gegen eine Datenbank stellen.

Aufruf: uv run python scripts/agent_eval.py [--env-file PFAD] [--only 3,7]

Die Sitzung ist schreibgeschützt (default_transaction_read_only): Der Lauf nutzt loop.run statt
loop.search, damit nichts in agent_runs landet, und navigate_tree schreibt hier keine Zeile in
search_runs. Je Frage eine JSON-Zeile in data/eval/, am Ende eine Markdown-Tabelle auf stdout.
"""

import argparse
import asyncio
import datetime as dt
import json
import re
import time
from pathlib import Path

import openai
import psycopg
import yaml

from parltopics.agent import loop
from parltopics.agent.execute import Tools
from parltopics.api import navigate
from parltopics.config import Settings
from parltopics.llm import LLMClient
from parltopics.registry import load_registry
from parltopics.wiki.tree import build_tree

ROOT = Path(__file__).resolve().parents[1]
QUESTIONS = ROOT / "tests" / "eval" / "agent_questions.yaml"
OUT = ROOT / "data" / "eval"
NUMBER = re.compile(r"\d+(?:['’  ]\d{3})*")  # 28'854 ist eine Zahl


async def ask_agent(settings: Settings, conn, registry, tree, question: dict) -> dict:
    """Eine Frage; die IDs aus den Werkzeugen zählt der Lauf selbst nach, unabhängig von loop."""
    messages, version = loop.first_messages(settings, question["query"])
    tools = Tools(settings, conn, registry, tree)
    seen: set[int] = set()

    async def execute(name, args):
        result, ids = await tools(name, args)
        seen.update(ids)
        return result, ids

    begin = time.monotonic()
    row = {**question, "model": settings.llm_name_large, "prompt": version}
    try:
        async with LLMClient(settings) as client:

            async def ask(messages: list[dict]) -> str:
                return (await client.chat(messages, large=True, attempts=2)).content

            outcome = await loop.run(messages, ask, execute)
    except openai.APIError as error:
        return row | {"status": "error", "error": f"{type(error).__name__}: {error}"}
    notes = [m["content"] for m in messages[2:] if m["role"] == "user"]  # Ergebnisse, Rückfragen
    answer = loop.Answer(answer=outcome.answer or "-", cited_ids=outcome.cited_ids)
    # Jede Zahl der Antwort (auch eine ID ohne Klammern) muss in einem Werkzeug-Ergebnis stehen.
    sourced = set(re.findall(r"\d+", "\n".join([question["query"], *notes])))
    numbers = [re.sub(r"\D", "", n) for n in NUMBER.findall(outcome.answer or "")]
    return row | {
        "status": outcome.status,
        "steps": outcome.steps,
        "seconds": round(time.monotonic() - begin, 1),
        "tools": [call["name"] for call in outcome.tool_calls],
        "tool_errors": [call["error"] for call in outcome.tool_calls if "error" in call],
        "answer": outcome.answer,
        "cited_ids": outcome.cited_ids,
        "not_from_tools": [i for i in loop.cited(answer) if i not in seen],
        "numbers_without_source": [n for n in numbers if n not in sourced],
        "unknown_ids_asked_again": any(n.startswith("Diese IDs hat kein") for n in notes),
        "sent_back_without_tool": any(n.startswith(loop.NO_TOOL) for n in notes),
        "proposal": outcome.proposal,
        "tool_calls": outcome.tool_calls,
        "replies": [m["content"] for m in messages if m["role"] == "assistant"],
        "notes": notes,
    }


def table(rows: list[dict]) -> str:
    head = "| # | Sprache | Art | Status | Schritte | Werkzeuge | s | Zitate | nur Werkzeug-IDs |"
    lines = [f"{head} Zahlen ohne Quelle |", "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        tools = ", ".join(r.get("tools", [])) or "–"
        ids_ok = "ja" if not r.get("not_from_tools") else f"nein: {r['not_from_tools']}"
        lines.append(
            f"| {r['id']} | {r['lang']} | {r['kind']} | {r['status']} | {r.get('steps', '–')} "
            f"| {tools} | {r.get('seconds', '–')} | {len(r.get('cited_ids', []))} | {ids_ok} "
            f"| {', '.join(r.get('numbers_without_source', [])) or '–'} |"
        )
    return "\n".join(lines)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--only", help="Fragen-IDs, z. B. 3,7")
    options = parser.parse_args()
    settings = Settings(_env_file=options.env_file)
    questions = yaml.safe_load(QUESTIONS.read_text(encoding="utf-8"))
    if options.only:
        wanted = {int(i) for i in options.only.split(",")}
        questions = [q for q in questions if q["id"] in wanted]
    registry = load_registry(settings.registry_path)
    tree = build_tree(registry)
    navigate.LOG = "SELECT 0"  # schreibgeschützt: navigate_tree ohne Zeile in search_runs
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"agent-{dt.datetime.now():%Y%m%d-%H%M}.jsonl"
    rows = []
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        conn.execute("SET default_transaction_read_only = on")
        for question in questions:
            row = await ask_agent(settings, conn, registry, tree, question)
            rows.append(row)
            with path.open("a", encoding="utf-8") as file:
                file.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
            print(f"{row['id']}: {row['status']} {row.get('seconds', '')}s", flush=True)
    print(f"\n{path}\n\n{table(rows)}")


if __name__ == "__main__":
    asyncio.run(main())
