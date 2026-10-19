"""Seitenlauf (PRD 7.9, F23–F25, ARCHITEKTUR 5): Kennzahlen und Zusammenfassungen der Seiten von
den Tag-Seiten bis Heart, mit Belegprüfung, input_hash und Weitergabe nach oben.

run_pages() in tree.py steuert Reihenfolge, Schwellen und Status. Hier kommen die Teile dazu:
Seiten in wiki_pages anlegen, Änderungen je Tag zählen, Kennzahlen, Eingaben wählen, das Modell
(70B für alle Seiten: 8B lieferte im Test mit echten Daten kein gültiges JSON und erfand IDs),
die Belegprüfung und das Schreiben der Seite.
run_pages ist synchron; es läuft in einem Thread, die Modellaufrufe auf der Event-Loop.

shortcut: ein Prozess je Lauf (Lauf-Sperre im Kommando), die Status gehen erst am Ende des Laufs
nach wiki_pages, und Seiten weggefallener Tags bleiben stehen (keine Weiterleitung). Für mehrere
Worker die Seiten wie Jobs übernehmen (ARCHITEKTUR 5.5).
"""

import asyncio
import datetime as dt
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass

import httpx
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import ValidationError

from parltopics.api import queries
from parltopics.config import Settings
from parltopics.llm import JSONExtractionError, LLMClient, extract_json, load_prompt
from parltopics.llm.client import ChatResult
from parltopics.llm.prompts import Prompt
from parltopics.registry import Registry
from parltopics.wiki.schemas import PageSummaryOutput, SummaryError, numbers_in, parse_page_summary
from parltopics.wiki.tree import (
    Page,
    PageOutcome,
    PageState,
    RunResult,
    children,
    page_ids,
    run_pages,
    subtree_tag_ids,
)

TAG_PROMPT, PARENT_PROMPT = "summarize_tag_v1", "summarize_parent_v1"
CHARS_PER_TOKEN = 3  # vorsichtige Schätzung ohne Tokenizer (ARCHITEKTUR 5.4)
SHORT_MAX = 200  # Kurzzusammenfassung, wie PageSummaryOutput
LEVEL_NAMES = {"country": "Bund", "canton": "Kanton", "city": "Stadt", "municipality": "Gemeinde"}
SUMMARY = "coalesce(s.summary, a.title_de, a.title_fr, a.title_it, a.title_rm, '') AS summary_de"

SYNC = """
INSERT INTO wiki_pages (page_id, kind, tag_id, parent_id, linked_from, path, title)
VALUES (%(page_id)s, %(kind)s, %(tag_id)s, %(parent_id)s, %(linked_from)s, %(path)s, %(title)s)
ON CONFLICT (page_id) DO UPDATE SET kind = EXCLUDED.kind, tag_id = EXCLUDED.tag_id,
    parent_id = EXCLUDED.parent_id, linked_from = EXCLUDED.linked_from, path = EXCLUDED.path,
    title = EXCLUDED.title, updated_at = now()
"""
# Ein zitiertes Geschäft hat sein aktives Label für das Tag der Seite verloren.
REMOVED = """
UPDATE wiki_pages p SET cited_label_removed = true
WHERE p.kind IN ('tag', 'querschnitt') AND EXISTS (
    SELECT 1 FROM unnest(p.cited_affair_ids) AS c(affair_id)
    WHERE NOT EXISTS (SELECT 1 FROM affair_tags l
                      WHERE l.affair_id = c.affair_id AND l.tag_id = p.tag_id
                        AND l.status = 'active'))
"""
STATES = """
SELECT page_id, status, pending_changes, built_at, cited_label_removed, last_error FROM wiki_pages
"""
# Neue, geänderte und aus dem Zeitfenster gefallene Geschäfte je Tag-Seite seit dem letzten Bau.
CHANGES = """
SELECT p.page_id, count(*) AS n
FROM wiki_pages p JOIN affair_tags l ON l.tag_id = p.tag_id JOIN affairs a ON a.id = l.affair_id
WHERE p.kind IN ('tag', 'querschnitt') AND p.built_at IS NOT NULL
  AND (l.created_at > p.built_at OR l.reviewed_at > p.built_at
       OR (a.begin_date >= p.window_start AND a.begin_date < %(window_start)s))
GROUP BY p.page_id
"""
IN_WINDOW = """
SELECT count(DISTINCT l.affair_id) FROM affair_tags l JOIN affairs a ON a.id = l.affair_id
WHERE l.tag_id = ANY(%(tag_ids)s) AND l.status = 'active' AND a.begin_date >= %(window_start)s
"""
AFFAIRS = f"""
SELECT a.id, a.body_key, a.begin_date, l.id AS label_id, l.input_hash, {SUMMARY}
FROM affair_tags l JOIN affairs a ON a.id = l.affair_id
LEFT JOIN affair_summaries s ON s.affair_id = a.id AND s.language = 'de' AND s.status = 'active'
WHERE l.tag_id = ANY(%(tag_ids)s) AND l.status = 'active' AND a.begin_date >= %(window_start)s
ORDER BY a.begin_date DESC, a.id DESC
LIMIT %(limit)s
"""
SAMPLES = f"""
SELECT a.id, a.body_key, a.begin_date, {SUMMARY}
FROM affairs a
LEFT JOIN affair_summaries s ON s.affair_id = a.id AND s.language = 'de' AND s.status = 'active'
WHERE a.begin_date >= %(window_start)s AND a.id IN (
    SELECT l.affair_id FROM affair_tags l WHERE l.tag_id = ANY(%(tag_ids)s) AND l.status = 'active')
ORDER BY a.begin_date DESC, a.id DESC
LIMIT %(limit)s
"""
CLEAR = """
UPDATE wiki_pages SET summary_short = NULL, summary_long = NULL, statements = '[]',
    cited_affair_ids = '{}', cited_page_ids = '{}', summary_hash = NULL, input_hash = NULL,
    window_start = %(window_start)s, window_end = %(window_end)s, updated_at = now()
WHERE page_id = %(page_id)s
"""
WRITE = """
UPDATE wiki_pages SET summary_short = %(summary_short)s, summary_long = %(summary_long)s,
    statements = %(statements)s, cited_affair_ids = %(cited_affair_ids)s,
    cited_page_ids = %(cited_page_ids)s, summary_hash = %(summary_hash)s,
    input_hash = %(input_hash)s, window_start = %(window_start)s, window_end = %(window_end)s,
    model_version = %(model_version)s, prompt_version = %(prompt_version)s,
    registry_version = %(registry_version)s, updated_at = now()
WHERE page_id = %(page_id)s
"""

Ask = Callable[[list[dict]], ChatResult]


def months_before(day: dt.date, months: int) -> dt.date:
    """Gleicher Tag (höchstens der 28.) so viele Monate früher."""
    month = day.month - 1 - months
    return dt.date(day.year + month // 12, month % 12 + 1, min(day.day, 28))


def digest(*parts: object) -> str:
    return hashlib.sha256(json.dumps(parts, default=str, sort_keys=True).encode()).hexdigest()[:16]


def prompt_stats(stats: dict, window_months: int) -> dict[str, object]:
    """Kennzahlen für den Prompt aus den gespeicherten Seitenkennzahlen (Zahlen nur von hier)."""
    years = [row for row in stats["by_year"] if row["year"]][-5:]
    return {
        "Geschäfte insgesamt": stats["affairs"],
        f"Geschäfte in den letzten {window_months} Monaten": stats["in_window"],
        "Parlamente": stats["bodies"],
        "nach Ebene": ", ".join(
            f"{LEVEL_NAMES.get(row['level'], row['level'] or 'ohne Ebene')} {row['count']}"
            for row in stats["by_level"]
        )
        or "keine",
        "nach Jahr": ", ".join(f"{row['year']}: {row['count']}" for row in years) or "keine",
        "häufigste Parlamente": ", ".join(
            f"{row['name'] or row['body_key']} {row['count']}" for row in stats["by_body"][:5]
        )
        or "keine",
        "häufigste Typen": ", ".join(
            f"{row['type_de'] or row['type']} {row['count']}" for row in stats["by_type"][:5]
        )
        or "keine",
    }


def allowed_numbers(stats: dict[str, object], window_start: dt.date, window_end: dt.date) -> set:
    numbers = numbers_in(window_start.isoformat()) | numbers_in(window_end.isoformat())
    for name, value in stats.items():
        numbers |= numbers_in(f"{name} {value}")
    return numbers


def refresh_stats(conn: psycopg.Connection, tree: dict[str, Page], window_start: dt.date) -> None:
    """Kennzahlen jeder Seite, bei jedem Lauf und ohne Modell (ARCHITEKTUR 5.2)."""
    for page_id in page_ids(tree.values()):
        tag_ids = subtree_tag_ids(tree, page_id)
        stats = queries.page_summary(conn, tag_ids)
        params = {"tag_ids": tag_ids, "window_start": window_start}
        stats["in_window"] = conn.execute(IN_WINDOW, params).fetchone()[0]
        conn.execute(
            "UPDATE wiki_pages SET n_affairs = %s, stats = %s WHERE page_id = %s",
            (
                stats["affairs"],
                Jsonb(stats, dumps=lambda obj: json.dumps(obj, default=str)),
                page_id,
            ),
        )


def tidy(data: dict) -> dict:
    """Kürzt eine zu lange Kurzzusammenfassung an einer Wortgrenze; beide Modelle halten die
    200 Zeichen im Test oft nicht ein. Die Belegprüfung bleibt davon unberührt."""
    short = data.get("summary_short")
    if not isinstance(short, str) or len(short) <= SHORT_MAX:
        return data
    cut = short[: SHORT_MAX - 1].rsplit(" ", 1)[0].rstrip(",;:")
    return {**data, "summary_short": f"{cut}…"}


def summarize(
    ask: Ask, prompt: Prompt, system: dict, user: dict, **allowed: set
) -> tuple[PageSummaryOutput, str]:
    """Modell fragen und Belege prüfen; einmal mit Hinweis wiederholen, sonst Fehler (failed)."""
    messages = prompt.messages(system, user)
    reply = ask(messages)
    try:
        output, _ = parse_page_summary(tidy(extract_json(reply.content)), **allowed)
        return output, reply.model
    except (JSONExtractionError, ValidationError, SummaryError) as error:
        hint = (
            f"Die Antwort war unbrauchbar ({str(error).splitlines()[0][:200]}). Jede Aussage"
            " braucht Belege aus den mitgelieferten IDs, Zahlen nur aus den Kennzahlen."
            " Antworte nur mit dem JSON."
        )
        messages = [
            *messages,
            {"role": "assistant", "content": reply.content},
            {"role": "user", "content": hint},
        ]
    reply = ask(messages)
    output, _ = parse_page_summary(tidy(extract_json(reply.content)), **allowed)
    return output, reply.model


@dataclass
class Builder:
    """Baut eine Seite: Eingaben, input_hash, Modell, Belegprüfung, Speichern."""

    settings: Settings
    conn: psycopg.Connection
    registry: Registry
    tree: dict[str, Page]
    ask: Ask
    prompts: dict[str, Prompt]
    window_start: dt.date
    window_end: dt.date

    def __call__(self, page: Page) -> PageOutcome:
        cursor = self.conn.cursor(row_factory=dict_row)
        row = cursor.execute(
            "SELECT summary_hash, input_hash, stats FROM wiki_pages WHERE page_id = %s",
            (page.page_id,),
        ).fetchone()
        stats = prompt_stats(row["stats"], self.settings.page_window_months)
        window = {"window_start": self.window_start}
        tag = self.registry.get(page.tag_id) if page.tag_id else None
        if page.kind in ("tag", "querschnitt"):
            params = {**window, "tag_ids": [page.tag_id], "limit": self.settings.page_max_affairs}
            affairs = cursor.execute(AFFAIRS, params).fetchall()
            enough = len(affairs) >= self.settings.page_min_affairs
            prompt, system = self.prompts["tag"], {}
            user = {**window, "window_end": self.window_end, "tag": tag, "stats": stats}
            user["affairs"] = affairs
            parts = [(a["id"], a["label_id"], a["input_hash"]) for a in affairs]
        else:
            kids = cursor.execute(
                "SELECT page_id, title, summary_short, summary_long, summary_hash FROM wiki_pages"
                " WHERE page_id = ANY(%s) AND summary_short IS NOT NULL ORDER BY page_id",
                ([kid.page_id for kid in children(self.tree, page.page_id)],),
            ).fetchall()
            tag_ids = subtree_tag_ids(self.tree, page.page_id)
            params = {**window, "tag_ids": tag_ids, "limit": self.settings.page_samples}
            affairs = cursor.execute(SAMPLES, params).fetchall()
            enough = bool(kids) or len(affairs) >= self.settings.page_min_affairs
            prompt, system = self.prompts["parent"], {"kind": page.kind}
            user = {"title": page.title, "page_id": page.page_id, "stats": stats, "children": kids}
            user["samples"] = affairs
            parts = [[k["page_id"], k["summary_hash"]] for k in kids] + [a["id"] for a in affairs]
        if not enough:  # unter PAGE_MIN_AFFAIRS: nur Kennzahlen und Liste, kein Modell
            cursor.execute(
                CLEAR, {**window, "window_end": self.window_end, "page_id": page.page_id}
            )
            return "changed" if row["summary_hash"] else "unchanged"
        self._fit(prompt, system, user, "affairs" if "affairs" in user else "samples")
        entry = tag.model_dump_json() if tag else None
        input_hash = digest(page.page_id, prompt.version, self.window_end, entry, parts)
        if input_hash == row["input_hash"] and row["summary_hash"]:
            return "unchanged"
        output, model = summarize(
            self.ask,
            prompt,
            system,
            user,
            allowed_affairs={a["id"] for a in affairs},
            allowed_pages={k["page_id"] for k in user.get("children", [])},
            allowed_numbers=allowed_numbers(stats, self.window_start, self.window_end),
        )
        statements = [statement.model_dump() for statement in output.statements]
        summary_hash = digest(output.summary_short, statements)
        cursor.execute(
            WRITE,
            {
                "page_id": page.page_id,
                "summary_short": output.summary_short,
                "summary_long": " ".join(statement["text"] for statement in statements),
                "statements": Jsonb(statements),
                "cited_affair_ids": sorted({i for s in statements for i in s["affair_ids"]}),
                "cited_page_ids": sorted({p for s in statements for p in s["page_ids"]}),
                "summary_hash": summary_hash,
                "input_hash": input_hash,
                **window,
                "window_end": self.window_end,
                "model_version": model,
                "prompt_version": prompt.version,
                "registry_version": self.registry.registry_version,
            },
        )
        return "changed" if summary_hash != row["summary_hash"] else "unchanged"

    def _fit(self, prompt: Prompt, system: dict, user: dict, key: str) -> None:
        """Kürzt die Geschäftsliste von hinten, bis der Prompt in PAGE_PROMPT_MAX_TOKENS passt."""
        while len(user[key]) > 1:
            size = sum(len(m["content"]) for m in prompt.messages(system, user))
            if size // CHARS_PER_TOKEN <= self.settings.page_prompt_max_tokens:
                return
            user[key] = user[key][:-1]


def sync_pages(conn: psycopg.Connection, tree: dict[str, Page]) -> None:
    """Je Seite des Baums eine Zeile in wiki_pages, Eltern vor Kindern; neue beginnen als open."""
    with conn.transaction():
        for page_id in page_ids(tree.values()):
            page = tree[page_id]
            conn.execute(
                SYNC,
                {
                    "page_id": page.page_id,
                    "kind": page.kind,
                    "tag_id": page.tag_id,
                    "parent_id": page.parent_id,
                    "linked_from": list(page.linked_from),
                    "path": page.path,
                    "title": page.title,
                },
            )


def save(
    conn: psycopg.Connection, result: RunResult, outcomes: dict[str, str], run_key: str
) -> None:
    """Status der Seiten und alle Statuswechsel in wiki_page_events."""
    with conn.transaction():
        for page_id, state in result.states.items():
            conn.execute(
                "UPDATE wiki_pages SET status = %s, pending_changes = %s, built_at = %s,"
                " cited_label_removed = %s, last_error = %s, worker_id = NULL, locked_at = NULL"
                " WHERE page_id = %s",
                (
                    state.status,
                    state.pending_changes,
                    state.built_at,
                    state.cited_label_removed,
                    state.last_error,
                    page_id,
                ),
            )
        for event in result.events:
            changed = (
                outcomes.get(event.page_id) == "changed" if event.to_status == "done" else None
            )
            conn.execute(
                "INSERT INTO wiki_page_events (page_id, from_status, to_status, summary_changed,"
                " run_key) VALUES (%s, %s, %s, %s, %s)",
                (event.page_id, event.from_status, event.to_status, changed, run_key),
            )


@dataclass(frozen=True)
class PageRun:
    result: RunResult
    outcomes: dict[str, str]  # changed, unchanged oder failed je gebauter Seite
    run_key: str


def run_once(
    settings: Settings,
    conn: psycopg.Connection,
    registry: Registry,
    tree: dict[str, Page],
    ask: Ask,
    now: dt.datetime,
) -> PageRun:
    """Ein Seitenlauf ohne Event-Loop: anlegen, zählen, Kennzahlen, run_pages, speichern."""
    window_end = now.date()
    window_start = months_before(window_end, settings.page_window_months)
    sync_pages(conn, tree)
    conn.execute(REMOVED)
    states = {
        row["page_id"]: PageState(
            status=row["status"],
            pending_changes=row["pending_changes"],
            built_at=row["built_at"],
            cited_label_removed=row["cited_label_removed"],
            last_error=row["last_error"],
        )
        for row in conn.cursor(row_factory=dict_row).execute(STATES)
        if row["page_id"] in tree
    }
    changed = dict(conn.execute(CHANGES, {"window_start": window_start}).fetchall())
    refresh_stats(conn, tree, window_start)
    prompts = {
        "tag": load_prompt(settings.prompts_dir, TAG_PROMPT),
        "parent": load_prompt(settings.prompts_dir, PARENT_PROMPT),
    }
    build = Builder(settings, conn, registry, tree, ask, prompts, window_start, window_end)
    outcomes: dict[str, str] = {}

    def rebuild(page: Page) -> PageOutcome:
        outcomes[page.page_id] = "failed"
        outcomes[page.page_id] = outcome = build(page)
        return outcome

    result = run_pages(tree, states, changed, now, rebuild, settings.page_thresholds())
    run_key = now.strftime("%Y%m%dT%H%M%SZ")
    save(conn, result, outcomes, run_key)
    return PageRun(result, outcomes, run_key)


async def run(
    settings: Settings,
    conn: psycopg.Connection,
    registry: Registry,
    tree: dict[str, Page],
    *,
    transport: httpx.AsyncBaseTransport | None = None,
    now: dt.datetime | None = None,
) -> PageRun:
    """Seitenlauf mit Modell; der Lauf selbst läuft in einem Thread, die Aufrufe auf der Loop."""
    loop = asyncio.get_running_loop()
    async with LLMClient(settings, transport=transport) as client:

        def ask(messages: list[dict]) -> ChatResult:
            call = client.chat(messages, large=True, attempts=2)
            return asyncio.run_coroutine_threadsafe(call, loop).result()

        when = now or dt.datetime.now(dt.UTC)
        return await asyncio.to_thread(run_once, settings, conn, registry, tree, ask, when)
