"""Navigationssuche mit Modell, Datenbank und Seitenbaum verbinden (PRD 7.10, F26).

search.navigate.navigate() steuert Schleife, Rückweg und Schrittgrenze. Hier kommen die Teile dazu:
die Unterseiten aus dem Seitenbaum, die Bewertung aller Kinder eines Knotens durch 8B
(navigate_v1), die Geschäfte am Blatt aus den aktiven Labels, die Auswahl mit belegten Aussagen
durch 70B (navigate_answer_v1) und die Volltextsuche als Rückfall. Bis der Seitenlauf (M3)
Kurzzusammenfassungen schreibt, beschreibt die Definition aus der Registry eine Seite.

navigate() ist synchron; sie läuft in einem Thread, die Modellaufrufe auf der Event-Loop der API.
Eine unbrauchbare Antwort zählt als «nichts relevant», die Suche geht dann zurück.
"""

import asyncio
import dataclasses
import time
from dataclasses import dataclass

import httpx
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import ValidationError

from parltopics.api.queries import TSQUERY
from parltopics.config import Settings
from parltopics.llm import JSONExtractionError, LLMClient, extract_json, load_prompt
from parltopics.registry import Registry
from parltopics.search.navigate import (
    FALLBACK,
    ChildScore,
    Filters,
    NavigationError,
    NavigationResult,
    NavigationStep,
    navigate,
    parse_step,
)
from parltopics.wiki.tree import Page, ancestors, children

STEP_PROMPT, ANSWER_PROMPT = "navigate_v1", "navigate_answer_v1"
SUMMARY_MAX = 200
LEVELS = {"bund": ["country"], "kanton": ["canton"], "gemeinde": ["municipality", "city"]}

FILTERS = """
  AND (%(year_from)s::int IS NULL OR extract(year FROM a.begin_date) >= %(year_from)s::int)
  AND (%(year_to)s::int IS NULL OR extract(year FROM a.begin_date) <= %(year_to)s::int)
  AND (cardinality(%(body_keys)s::text[]) = 0 OR a.body_key = ANY(%(body_keys)s::text[]))
  AND (cardinality(%(levels)s::text[]) = 0 OR b.level = ANY(%(levels)s::text[]))
  AND (%(affair_type)s::text IS NULL OR a.type_harmonized_en ILIKE %(affair_type)s::text
       OR a.raw->>'type_harmonized_de' ILIKE %(affair_type)s::text)
"""
LEAF = f"""
SELECT a.id FROM affair_tags l JOIN affairs a ON a.id = l.affair_id
LEFT JOIN bodies b ON b.body_key = a.body_key
WHERE l.tag_id = %(tag_id)s AND l.status = 'active' {FILTERS}
ORDER BY l.confidence DESC, a.begin_date DESC NULLS LAST, a.id DESC
LIMIT %(limit)s
"""
FULLTEXT = f"""
SELECT d.affair_id FROM search_documents d JOIN affairs a ON a.id = d.affair_id
LEFT JOIN bodies b ON b.body_key = a.body_key
WHERE d.document @@ {TSQUERY} {FILTERS}
ORDER BY ts_rank_cd(d.document, {TSQUERY}) DESC, a.id DESC
LIMIT %(limit)s
"""
CANDIDATES = """
SELECT a.id, a.body_key, a.begin_date,
       coalesce(a.title_de, a.title_fr, a.title_it, a.title_rm) AS title, s.summary AS summary_de
FROM affairs a
LEFT JOIN affair_summaries s ON s.affair_id = a.id AND s.language = 'de' AND s.status = 'active'
WHERE a.id = ANY(%s)
"""
LOG = """
INSERT INTO search_runs (query, filters, path, visits, steps, fallback_used, affair_ids, answer,
                         statements, model_versions, prompt_versions, duration_ms, status)
VALUES (%(query)s, %(filters)s, %(path)s, %(visits)s, %(steps)s, %(fallback_used)s,
        %(affair_ids)s, %(answer)s, %(statements)s, %(model_versions)s, %(prompt_versions)s,
        %(duration_ms)s, %(status)s)
RETURNING id
"""


def filter_params(filters: Filters | None) -> dict:
    """Filter aus dem ersten Schritt als SQL-Parameter; Ebenen in die Werte von bodies.level."""
    f = filters or Filters()
    return {
        "year_from": f.year_from,
        "year_to": f.year_to,
        "body_keys": f.body_keys,
        "levels": [level for name in f.levels for level in LEVELS[name]],
        "affair_type": f.affair_type,
    }


@dataclass(frozen=True)
class Searched:
    result: NavigationResult
    answer: str | None
    duration_ms: int
    run_id: int


async def search(
    settings: Settings,
    conn: psycopg.Connection,
    registry: Registry,
    tree: dict[str, Page],
    query: str,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> Searched:
    """Eine Navigationssuche mit Protokoll in search_runs. openai.APIError: Modell fehlt."""
    loop = asyncio.get_running_loop()
    step_prompt = load_prompt(settings.prompts_dir, STEP_PROMPT)
    answer_prompt = load_prompt(settings.prompts_dir, ANSWER_PROMPT)
    limits = settings.navigate_limits()
    known = {tag.tag_id: tag for tag in registry.tags}

    def summary(page: Page) -> str:
        tag = known.get(page.tag_id or "")
        return tag.definition.de[:SUMMARY_MAX] if tag else ""

    async with LLMClient(settings, transport=transport) as client:

        def ask(messages: list[dict], large: bool) -> str:  # aus dem Thread der Suche
            call = client.chat(messages, large=large, attempts=2)
            return asyncio.run_coroutine_threadsafe(call, loop).result().content

        def score(text: str, page_id: str, kids: list[str], first: bool) -> NavigationStep:
            offered = [
                {"page_id": kid, "title": tree[kid].title, "summary_short": summary(tree[kid])}
                for kid in kids
            ]
            user = {"query": text, "node": tree[page_id], "children": offered}
            reply = ask(step_prompt.messages({"first_step": first}, user), large=False)
            try:
                return parse_step(extract_json(reply), set(kids))
            except (JSONExtractionError, ValidationError, NavigationError):
                return NavigationStep(scores=[ChildScore(page_id=kid, relevance=0) for kid in kids])

        def leaf_candidates(page_id: str, filters: Filters | None) -> list[int]:
            tag_id = tree[page_id].tag_id
            if tag_id is None:
                return []
            params = {**filter_params(filters), "tag_id": tag_id, "limit": limits.max_candidates}
            return [row[0] for row in conn.execute(LEAF, params)]

        def select(text: str, page_id: str, candidates: list[int]) -> dict:
            if page_id == FALLBACK:
                path = ["Volltextsuche"]
            else:
                chain = [*reversed(ancestors(tree, page_id)), page_id]
                path = [tree[step].title for step in chain]
            rows = conn.cursor(row_factory=dict_row).execute(CANDIDATES, (candidates,))
            by_id = {row["id"]: row for row in rows}
            affairs = [by_id[affair_id] for affair_id in candidates if affair_id in by_id]
            user = {"query": text, "path": path, "affairs": affairs}
            reply = ask(answer_prompt.messages({}, user), large=True)
            try:
                return extract_json(reply)
            except JSONExtractionError:
                return {}

        def fulltext(text: str, filters: Filters | None) -> list[int]:
            params = {**filter_params(filters), "q": text, "limit": limits.max_candidates}
            return [row[0] for row in conn.execute(FULLTEXT, params)]

        start = time.monotonic()
        result = await asyncio.to_thread(
            navigate,
            query,
            children=lambda page_id: [page.page_id for page in children(tree, page_id)],
            score=score,
            leaf_candidates=leaf_candidates,
            select=select,
            fulltext=fulltext,
            limits=limits,
        )
    duration_ms = round((time.monotonic() - start) * 1000)
    answer = " ".join(s.text for s in result.statements) if result.status == "ok" else None
    log = {
        "query": query,
        "filters": Jsonb(result.filters.model_dump()) if result.filters else None,
        "path": result.path,
        "visits": Jsonb([dataclasses.asdict(visit) for visit in result.visits]),
        "steps": result.steps,
        "fallback_used": result.fallback_used,
        "affair_ids": result.affair_ids,
        "answer": answer or None,
        "statements": Jsonb([statement.model_dump() for statement in result.statements]),
        "model_versions": Jsonb({"step": settings.llm_name, "answer": settings.llm_name_large}),
        "prompt_versions": Jsonb({"step": step_prompt.version, "answer": answer_prompt.version}),
        "duration_ms": duration_ms,
        "status": result.status,
    }
    run_id = await asyncio.to_thread(lambda: conn.execute(LOG, log).fetchone()[0])
    return Searched(result, answer or None, duration_ms, run_id)


def log_error(conn: psycopg.Connection, query: str, duration_ms: int) -> None:
    """Fehlgeschlagene Suche (Modell nicht erreichbar) ins Protokoll, ohne Antwort."""
    conn.execute(
        "INSERT INTO search_runs (query, duration_ms, status) VALUES (%s, %s, 'error')",
        (query, duration_ms),
    )
