"""Ad-hoc-Themen ohne Embeddings (PRD 7.4, F8, ARCHITEKTUR 4.5).

70B schlägt Stichwörter in DE/FR/IT vor, ein Mensch prüft sie. Die Volltextsuche liefert die
Kandidaten; dazu kommt die feste Stichprobe von 2 % (jedes 50. Geschäft) ohne Stichworttreffer,
die schätzt, wie viel die Stichwörter verpassen. Für beide entstehen Jobs classify:adhoc:<name>,
in denen der Worker nur fragt, ob dieses eine Thema passt (ADR 0009). open_adhoc_jobs öffnet sie
für jedes Ad-hoc-Tag der Registry, beim Anlegen, beim Freischalten (Nachklassifizierung), im
täglichen Lauf und von Hand; das Thema steht nirgends im Code. retire zieht es zurück (F10): Jobs
zu, Labels ohne menschlichen Entscheid superseded. create mit demselben Namen holt es zurück.
"""

import re
from dataclasses import dataclass
from datetime import date
from typing import Annotated, Literal

import httpx
import psycopg
from pydantic import AfterValidator, BaseModel

from parltopics.classify.queue import OpenResult, adhoc_task, close_jobs, open_jobs
from parltopics.classify.worker import ADHOC_PROMPT, SAMPLE_EVERY
from parltopics.config import Settings
from parltopics.llm import LLMClient, extract_json, load_prompt
from parltopics.registry import Registry, Tag, file_hash, load_registry, tag_hash
from parltopics.registry.edit import NotAdhoc, add_adhoc_tag, check_step, set_status
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


BRACKETS = re.compile(r"\s*\([^)]*\)")
LAST_KEYWORDS = """
SELECT params->'keywords' FROM classification_runs
WHERE task = %s AND params ? 'keywords' ORDER BY id DESC LIMIT 1
"""


def tag_keywords(tag: Tag) -> Keywords:
    """Stichwörter aus den Bezeichnungen des Tags: Name, Synonyme und versteckte Bezeichnungen je
    Sprache; ein Name auch ohne Klammerzusatz, «Digitalisierung (breit)» trifft sonst kaum."""

    def names(name: str | None) -> list[str]:
        return [name, BRACKETS.sub("", name).strip()] if name else []

    label, alt = tag.pref_label, tag.alt_labels
    return Keywords(
        de=[*names(label.de), *alt.de, *tag.hidden_labels],
        fr=[*names(label.fr), *alt.fr],
        it=[*names(label.it), *alt.it],
    )


def last_keywords(conn: psycopg.Connection, task: str) -> Keywords | None:
    """Die Stichwörter des letzten Kandidatenlaufs dieser Aufgabe, damit ein neuer Lauf dieselben
    Kandidaten findet; jeder Lauf speichert sie in classification_runs.params."""
    row = conn.execute(LAST_KEYWORDS, (task,)).fetchone()
    return Keywords.model_validate(row[0]) if row else None


@dataclass(frozen=True)
class Opened:
    tag_id: str
    registry_version: str
    run: OpenResult
    candidates: int
    sample: int


Scope = Literal["candidates", "all"]


def open_adhoc_jobs(
    conn: psycopg.Connection,
    settings: Settings,
    registry: Registry,
    tag_id: str,
    *,
    kind: str,
    by: str,
    bodies: list[str] | None = None,
    since: date | None = None,
    limit: int | None = None,
    scope: Scope = "candidates",
    keywords: Keywords | None = None,
) -> Opened:
    """Öffnet die Ja/Nein-Jobs eines Ad-hoc-Tags (ADR 0009); alles kommt aus Registry und Läufen.

    candidates: Stichworttreffer und die 2 %-Stichprobe der übrigen Geschäfte (PRD 7.4). Die
    Stichwörter sind die übergebenen, sonst die des letzten Laufs, sonst die Bezeichnungen des Tags.
    all: jedes Geschäft im Scope (bodies, since, limit), für einen bewussten Volllauf. Die
    Versionen sind die, die der Worker schreibt: Ein erledigter Job öffnet sich erst wieder, wenn
    sich Prompt, Beschreibung, Synonyme oder Text ändern.
    """
    task = adhoc_task(tag_id)
    versions = {
        "registry_version": registry.registry_version,
        "scheme_hash": tag_hash(registry.get(tag_id)),
        "prompt_version": load_prompt(settings.prompts_dir, ADHOC_PROMPT).version,
    }
    scoped = {"conn": conn, "task": task, "bodies": bodies, "since": since, "limit": limit}
    if scope == "all":
        run = open_jobs(**scoped, kind=kind, extra={"scope": "all", "by": by}, **versions)
        return Opened(tag_id, registry.registry_version, run, 0, 0)
    if keywords is None:
        keywords = last_keywords(conn, task) or tag_keywords(registry.get(tag_id))
    candidates, sample = find_affairs(conn, keywords, bodies=bodies, since=since)
    run = open_jobs(
        **scoped,
        kind=kind,
        affair_ids=candidates + sample,
        extra={
            "keywords": keywords.model_dump(),
            "candidates": len(candidates),
            "sample": len(sample),
            "by": by,
        },
        **versions,
    )
    return Opened(tag_id, registry.registry_version, run, len(candidates), len(sample))


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
) -> Opened:
    """Legt das Tag als proposed an und öffnet die Jobs für Kandidaten und Stichprobe."""
    tag_id, registry = add_adhoc_tag(
        settings.registry_path, name_de=name_de, definition_de=definition_de, by=by, broader=broader
    )
    _sync(conn, settings, registry)
    return open_adhoc_jobs(
        conn,
        settings,
        registry,
        tag_id,
        kind="adhoc",
        by=by,
        bodies=bodies,
        since=since,
        keywords=keywords,
    )


def activate(conn: psycopg.Connection, settings: Settings, tag_id: str, *, by: str) -> Opened:
    """Schaltet ein bewährtes Ad-hoc-Tag frei und öffnet die Nachklassifizierung (kind reclassify)
    über Kandidaten und Stichprobe. Unter proposed erledigte Jobs bleiben erledigt: Prompt und
    Tag sind dieselben. Ein Tag aus einem Vorschlag bekommt so erst hier seine Kandidaten."""
    with conn.transaction():
        registry = _set_status(conn, settings, tag_id, "active", by)
        return open_adhoc_jobs(conn, settings, registry, tag_id, kind="reclassify", by=by)


# Menschliche Entscheide haben Vorrang wie in queue.SUPERSEDE: bestätigte und von Hand gesetzte
# Labels bleiben aktiv und zählen weiter im Gold-Set.
RETIRE_LABELS = """
UPDATE affair_tags SET status = 'superseded'
WHERE tag_id = %s AND status = 'active' AND review_status IS NULL
"""
STATUS = "SELECT status FROM tags WHERE tag_id = %s AND scheme = 'adhoc' FOR UPDATE"


@dataclass(frozen=True)
class Retired:
    registry_version: str
    jobs: int  # geschlossen, auch erledigte
    labels: int  # ohne menschlichen Entscheid, von active auf superseded


def retire(conn: psycopg.Connection, settings: Settings, tag_id: str, *, by: str) -> Retired:
    """Zieht ein Ad-hoc-Tag zurück, Rückweg zu create und activate (F10); gelöscht wird nichts."""
    with conn.transaction():
        registry = _set_status(conn, settings, tag_id, "retired", by)
        jobs = close_jobs(conn, adhoc_task(tag_id))
        labels = conn.execute(RETIRE_LABELS, (tag_id,)).rowcount
    return Retired(registry.registry_version, jobs, labels)


def _set_status(
    conn: psycopg.Connection, settings: Settings, tag_id: str, status: str, by: str
) -> Registry:
    """Statuswechsel in Datei und Datenbank, in der Transaktion des Aufrufers.

    Ob er erlaubt ist, entscheidet die Datenbank; die gesperrte Zeile lässt zwei gleiche Aufrufe
    nacheinander laufen. Steht der Wechsel schon in der Datei, weil danach die Transaktion
    scheiterte, holt ein zweiter Aufruf nur den Rest nach.
    """
    row = conn.execute(STATUS, (tag_id,)).fetchone()
    if row is None:
        raise NotAdhoc(f"{tag_id} ist kein Ad-hoc-Tag der Registry")
    check_step(tag_id, row[0], status)
    registry = load_registry(settings.registry_path)
    if registry.get(tag_id).status != status:
        registry = set_status(settings.registry_path, tag_id, status, by=by)
    _sync(conn, settings, registry)
    return registry


def _sync(conn: psycopg.Connection, settings: Settings, registry: Registry) -> None:
    sync_registry(conn, registry, file_hash(settings.registry_path))
