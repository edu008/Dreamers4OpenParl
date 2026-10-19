"""Ad-hoc-Themen ohne Embeddings (PRD 7.4, F8, ARCHITEKTUR 4.5).

70B schlägt Stichwörter in DE/FR/IT vor, ein Mensch prüft sie. Die Volltextsuche liefert die
Kandidaten; dazu kommt die feste Stichprobe von 2 % (jedes 50. Geschäft) ohne Stichworttreffer,
die schätzt, wie viel die Stichwörter verpassen. Für beide entstehen Jobs classify:adhoc:<name>,
die der Worker wie Stufe 2 mit nur diesem Thema bearbeitet. Das Tag bleibt proposed, bis ein
Mensch es freischaltet; danach läuft es in Stufe 2 von classify:aps mit. retire zieht es zurück
(F10): Jobs zu, Labels superseded. create mit demselben Namen holt es zurück.
"""

from dataclasses import dataclass
from datetime import date
from typing import Annotated

import httpx
import psycopg
from pydantic import AfterValidator, BaseModel

from parltopics.classify.queue import OpenResult, adhoc_task, close_jobs, open_jobs
from parltopics.classify.worker import SAMPLE_EVERY, STAGE_PROMPTS
from parltopics.config import Settings
from parltopics.llm import LLMClient, extract_json, load_prompt
from parltopics.registry import Registry, file_hash, tag_hash
from parltopics.registry.edit import add_adhoc_tag, set_status
from parltopics.registry.sync import sync_registry

KEYWORDS_PROMPT = "adhoc_keywords_v1"
MAX_TERMS = 30  # je Sprache, wie im Prompt verlangt


def _clean(terms: list[str]) -> list[str]:
    """Leerraum zusammenziehen, Leere und Doppel weg, höchstens MAX_TERMS."""
    cleaned = (" ".join(term.split()) for term in terms)
    return list(dict.fromkeys(term for term in cleaned if term))[:MAX_TERMS]


Terms = Annotated[list[str], AfterValidator(_clean)]


class Keywords(BaseModel):
    """Suchbegriffe je Sprache; Mehrwortbegriffe gelten als Phrase."""

    de: Terms = []
    fr: Terms = []
    it: Terms = []


def websearch(terms: list[str]) -> str:
    """Begriffe als Ausdruck für websearch_to_tsquery: Phrasen in Anführungszeichen, mit or."""
    safe = (term.replace('"', " ").strip().lstrip("-") for term in terms)  # - hiesse «ohne»
    return " or ".join(f'"{term}"' if " " in term else term for term in safe if term)


MATCH = """(websearch_to_tsquery('german', %(de)s) || websearch_to_tsquery('french', %(fr)s)
            || websearch_to_tsquery('italian', %(it)s))"""
SCOPE = """
  AND (%(bodies)s::text[] IS NULL OR a.body_key = ANY(%(bodies)s::text[]))
  AND (%(since)s::date IS NULL OR a.begin_date >= %(since)s::date)
"""
CANDIDATES = f"""
SELECT d.affair_id FROM search_documents d JOIN affairs a ON a.id = d.affair_id
WHERE d.document @@ {MATCH} {SCOPE}
ORDER BY a.begin_date DESC NULLS LAST, a.id DESC
"""
SAMPLE = f"""
SELECT a.id FROM affairs a JOIN affair_inputs i ON i.affair_id = a.id
LEFT JOIN search_documents d ON d.affair_id = a.id
WHERE mod(a.id, {SAMPLE_EVERY}) = 0 AND NOT coalesce(d.document @@ {MATCH}, false) {SCOPE}
ORDER BY a.id
"""


def find_affairs(
    conn: psycopg.Connection, keywords: Keywords, *, bodies: list[str] | None, since: date | None
) -> tuple[list[int], list[int]]:
    """Kandidaten (Stichworttreffer, neueste zuerst) und Stichprobe ohne Treffer."""
    params = {
        "de": websearch(keywords.de),
        "fr": websearch(keywords.fr),
        "it": websearch(keywords.it),
        "bodies": bodies,
        "since": since,
    }
    candidates = [row[0] for row in conn.execute(CANDIDATES, params)]
    sample = [row[0] for row in conn.execute(SAMPLE, params)]
    return candidates, sample


async def suggest_keywords(
    settings: Settings,
    name: str,
    description: str,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> Keywords:
    """Stichwörter von 70B (generate_keywords); ein Mensch prüft sie vor dem Start."""
    prompt = load_prompt(settings.prompts_dir, KEYWORDS_PROMPT)
    messages = prompt.messages({}, {"name": name, "description": description})
    async with LLMClient(settings, transport=transport) as client:
        # Ein Mensch wartet auf die Antwort: ein zweiter Versuch statt langer Wiederholung.
        reply = await client.chat(messages, large=True, attempts=2)
    return Keywords.model_validate(extract_json(reply.content))


@dataclass(frozen=True)
class Created:
    tag_id: str
    registry_version: str
    run: OpenResult
    candidates: int
    sample: int


def create(
    conn: psycopg.Connection,
    settings: Settings,
    *,
    name_de: str,
    definition_de: str,
    keywords: Keywords,
    by: str,
    broader: list[str] | None = None,
    bodies: list[str] | None = None,
    since: date | None = None,
) -> Created:
    """Legt das Tag als proposed an und öffnet die Jobs für Kandidaten und Stichprobe."""
    tag_id, registry = add_adhoc_tag(
        settings.registry_path, name_de=name_de, definition_de=definition_de, by=by, broader=broader
    )
    _sync(conn, settings, registry)
    candidates, sample = find_affairs(conn, keywords, bodies=bodies, since=since)
    run = open_jobs(
        conn,
        task=adhoc_task(tag_id),
        bodies=bodies,
        since=since,
        limit=None,
        kind="adhoc",
        registry_version=registry.registry_version,
        scheme_hash=tag_hash(registry.get(tag_id)),
        prompt_version=load_prompt(settings.prompts_dir, STAGE_PROMPTS[1]).version,
        affair_ids=candidates + sample,
        extra={
            "keywords": keywords.model_dump(),
            "candidates": len(candidates),
            "sample": len(sample),
            "by": by,
        },
    )
    return Created(tag_id, registry.registry_version, run, len(candidates), len(sample))


def activate(conn: psycopg.Connection, settings: Settings, tag_id: str, *, by: str) -> Registry:
    """Schaltet ein bewährtes Ad-hoc-Tag frei: ab dann in Stufe 2 von classify:aps."""
    registry = set_status(settings.registry_path, tag_id, "active", by=by)
    _sync(conn, settings, registry)
    return registry


RETIRE_LABELS = """
UPDATE affair_tags SET status = 'superseded' WHERE tag_id = %s AND status = 'active'
"""


@dataclass(frozen=True)
class Retired:
    registry_version: str
    jobs: int  # geschlossen, auch erledigte
    labels: int  # von active auf superseded


def retire(conn: psycopg.Connection, settings: Settings, tag_id: str, *, by: str) -> Retired:
    """Zieht ein Ad-hoc-Tag zurück, Rückweg zu create und activate (F10); gelöscht wird nichts."""
    registry = set_status(settings.registry_path, tag_id, "retired", by=by)
    with conn.transaction():
        _sync(conn, settings, registry)
        jobs = close_jobs(conn, adhoc_task(tag_id))
        labels = conn.execute(RETIRE_LABELS, (tag_id,)).rowcount
    return Retired(registry.registry_version, jobs, labels)


def _sync(conn: psycopg.Connection, settings: Settings, registry: Registry) -> None:
    sync_registry(conn, registry, file_hash(settings.registry_path))
