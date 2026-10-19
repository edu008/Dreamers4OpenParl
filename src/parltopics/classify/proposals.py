"""Tag-Vorschläge gruppieren, gegen die Registry prüfen und entscheiden (PRD 7.3, F7).

Worker schreiben Rohvorschläge in tag_proposal_raw. group() fasst sie nach normalisiertem Namen
zusammen; ein Vorschlag mit gleichem oder ähnlichem Schlüssel (pg_trgm) nimmt neue Rohvorschläge
auf. Für eine neue Gruppe liefert der Abgleich mit allen Bezeichnungen der Registry die
ähnlichsten Themen, und Apertus 70B empfiehlt new, duplicate_of oder child_of. Ohne brauchbare
Antwort entscheiden die Bezeichnungen allein. Ein Mensch entscheidet: accepted legt ein
Ad-hoc-Tag (proposed) an und öffnet Jobs für die betroffenen Geschäfte, merged und rejected halten
nur den Entscheid fest. undo nimmt den Entscheid zurück (F10): Der Vorschlag ist wieder offen, ein
mit accepted angelegtes Tag wird zurückgezogen.
"""

import contextlib
import logging
from collections import Counter
from dataclasses import dataclass
from typing import Literal

import httpx
import openai
import psycopg
from psycopg.rows import dict_row
from pydantic import BaseModel, Field, ValidationError

from parltopics.classify.adhoc import retire
from parltopics.classify.queue import OpenResult, adhoc_task, open_jobs, task_tag
from parltopics.classify.worker import STAGE_PROMPTS
from parltopics.config import Settings
from parltopics.llm import JSONExtractionError, LLMClient, Prompt, extract_json, load_prompt
from parltopics.registry import Registry, Tag, file_hash, load_registry, tag_hash
from parltopics.registry.aps_import import aps_slug
from parltopics.registry.edit import WrongStatus, add_adhoc_tag
from parltopics.registry.sync import sync_registry

log = logging.getLogger("parltopics.proposals")

CHECK_PROMPT = "proposal_check_v1"
SAME_PROPOSAL = 0.6  # pg_trgm-Ähnlichkeit der Schlüssel, ab der Rohvorschläge zusammengehören
DUPLICATE = 0.8  # ohne Modell: so ähnlich zu einer Bezeichnung der Registry heisst Duplikat
SIMILAR_TAGS = 5
TITLES = 8

UNGROUPED = """
SELECT r.id, r.affair_id, r.run_id, r.name_de, r.desc_de, r.reason, r.model_version,
       coalesce(a.title_de, a.title_fr, a.title_it, a.title_rm) AS title
FROM tag_proposal_raw r JOIN affairs a ON a.id = r.affair_id
WHERE r.proposal_id IS NULL
ORDER BY r.id
"""
EXISTING = """
SELECT id FROM tag_proposals
WHERE group_key = %(key)s OR similarity(group_key, %(key)s) >= %(threshold)s
ORDER BY group_key = %(key)s DESC, similarity(group_key, %(key)s) DESC, id
LIMIT 1
"""
# Ähnlichste Themen über alle Bezeichnungen (pref, alt, hidden); % nutzt den Trigramm-Index.
SIMILAR = """
SELECT l.tag_id, max(similarity(l.label, %(name)s)) AS score
FROM tag_labels l JOIN tags t ON t.tag_id = l.tag_id
WHERE t.status IN ('active', 'proposed') AND l.label %% %(name)s
GROUP BY l.tag_id
ORDER BY score DESC, l.tag_id
LIMIT %(limit)s
"""
INSERT = """
INSERT INTO tag_proposals (group_key, name_de, desc_de, reason, recommendation, related_tag_id,
                           model_version, run_id)
VALUES (%(key)s, %(name_de)s, %(desc_de)s, %(reason)s, %(recommendation)s, %(related_tag_id)s,
        %(model_version)s, %(run_id)s)
RETURNING id
"""
ATTACH = """
WITH raw AS (
    UPDATE tag_proposal_raw SET proposal_id = %(proposal_id)s
    WHERE id = ANY(%(raw_ids)s) RETURNING affair_id
)
INSERT INTO tag_proposal_affairs (proposal_id, affair_id)
SELECT DISTINCT %(proposal_id)s, affair_id FROM raw
ON CONFLICT DO NOTHING
"""


class Check(BaseModel):
    """Empfehlung zu einer Gruppe (proposal_check_v1)."""

    recommendation: Literal["new", "duplicate_of", "child_of"]
    related_tag: str | None = None
    name_de: str = Field(min_length=1, max_length=120)
    description_de: str = Field(min_length=1, max_length=1000)
    reason: str = Field(min_length=1, max_length=500)


@dataclass(frozen=True)
class Group:
    key: str
    rows: list[dict]

    @property
    def name_de(self) -> str:
        return Counter(row["name_de"] for row in self.rows).most_common(1)[0][0]


@dataclass(frozen=True)
class GroupResult:
    created: int  # neue Vorschläge
    attached: int  # Rohvorschläge, die einem bestehenden Vorschlag zugingen
    checked: int  # neue Vorschläge mit Empfehlung von 70B


def pending(conn: psycopg.Connection) -> list[Group]:
    """Ungruppierte Rohvorschläge nach Schlüssel, dem Namen umgeschrieben wie ein slug."""
    groups: dict[str, list[dict]] = {}
    for row in conn.cursor(row_factory=dict_row).execute(UNGROUPED):
        groups.setdefault(aps_slug(row["name_de"]), []).append(row)
    return [Group(key, rows) for key, rows in groups.items()]


def similar_tags(
    conn: psycopg.Connection, registry: Registry, name: str
) -> list[tuple[Tag, float]]:
    known = {tag.tag_id: tag for tag in registry.tags}
    rows = conn.execute(SIMILAR, {"name": name, "limit": SIMILAR_TAGS}).fetchall()
    return [(known[tag_id], score) for tag_id, score in rows if tag_id in known]


def by_labels(group: Group, similar: list[tuple[Tag, float]]) -> Check:
    """Empfehlung ohne Modell: eine fast gleiche Bezeichnung der Registry heisst Duplikat."""
    first = group.rows[0]
    top = similar[0] if similar and similar[0][1] >= DUPLICATE else None
    return Check(
        recommendation="duplicate_of" if top else "new",
        related_tag=top[0].tag_id if top else None,
        name_de=group.name_de,
        description_de=first["desc_de"] or group.name_de,
        reason=f"Bezeichnung fast gleich wie {top[0].tag_id}"
        if top
        else "keine ähnliche Bezeichnung in der Registry",
    )


async def by_model(
    client: LLMClient, prompt: Prompt, registry: Registry, group: Group, similar: list[Tag]
) -> Check | None:
    """Empfehlung von 70B; None, wenn die Antwort unbrauchbar ist oder ein Tag erfindet."""
    titles = list(dict.fromkeys(row["title"] for row in group.rows if row["title"]))[:TITLES]
    messages = prompt.messages(
        {"tags": registry.active()},
        {"proposals": group.rows[:10], "similar": similar, "titles": titles},
    )
    reply = await client.chat(messages, large=True, attempts=2)
    try:
        check = Check.model_validate(extract_json(reply.content))
    except (JSONExtractionError, ValidationError):
        return None
    if check.recommendation == "new":
        return check.model_copy(update={"related_tag": None})
    known = {tag.tag_id for tag in registry.tags}
    return check if check.related_tag in known else None


async def group(
    conn: psycopg.Connection,
    settings: Settings,
    *,
    use_model: bool = True,
    transport: httpx.AsyncBaseTransport | None = None,
) -> GroupResult:
    """Gruppiert alle ungruppierten Rohvorschläge, je Gruppe in einer Transaktion."""
    registry = load_registry(settings.registry_path)
    prompt = load_prompt(settings.prompts_dir, CHECK_PROMPT)
    client = LLMClient(settings, transport=transport) if use_model else None
    created = attached = checked = 0
    try:
        for found in pending(conn):
            raw_ids = [row["id"] for row in found.rows]
            existing = conn.execute(
                EXISTING, {"key": found.key, "threshold": SAME_PROPOSAL}
            ).fetchone()
            if existing is not None:
                with conn.transaction():
                    conn.execute(ATTACH, {"proposal_id": existing[0], "raw_ids": raw_ids})
                attached += len(raw_ids)
                continue
            similar = similar_tags(conn, registry, found.name_de)
            check = None
            if client is not None:
                try:
                    check = await by_model(client, prompt, registry, found, [t for t, _ in similar])
                except openai.APIError as error:
                    log.warning("Vorschlag %s ohne Modell geprüft: %s", found.key, error)
            checked += check is not None
            model_version = settings.llm_name_large if check else "pg_trgm"
            check = check or by_labels(found, similar)
            with conn.transaction():
                proposal_id = conn.execute(
                    INSERT,
                    {
                        "key": found.key,
                        "name_de": check.name_de,
                        "desc_de": check.description_de,
                        "reason": check.reason,
                        "recommendation": check.recommendation,
                        "related_tag_id": check.related_tag,
                        "model_version": model_version,
                        "run_id": max((row["run_id"] or 0) for row in found.rows) or None,
                    },
                ).fetchone()[0]
                conn.execute(ATTACH, {"proposal_id": proposal_id, "raw_ids": raw_ids})
            created += 1
    finally:
        if client is not None:
            await client.aclose()
    return GroupResult(created, attached, checked)


class ProposalNotFound(LookupError):
    pass


class ProposalDecided(ValueError):
    """Der Vorschlag ist schon entschieden."""


class ProposalOpen(ValueError):
    """Der Vorschlag ist nicht entschieden: Es gibt nichts zurückzunehmen."""


PROPOSAL = """
SELECT name_de, desc_de, recommendation, related_tag_id, status, decision, model_version, run_id
FROM tag_proposals WHERE id = %s
"""
DECIDE = """
UPDATE tag_proposals
SET status = 'done', decision = %(decision)s, decided_by = %(by)s, decided_at = now(),
    related_tag_id = coalesce(%(related)s, related_tag_id)
WHERE id = %(id)s AND status <> 'done'
"""
# Wieder offen; decided_by und decided_at nennen jetzt, wer den Entscheid zurückgenommen hat.
REOPEN = """
UPDATE tag_proposals SET status = 'open', decision = NULL, decided_by = %(by)s, decided_at = now()
WHERE id = %(id)s AND status = 'done'
"""
AFFAIRS = "SELECT affair_id FROM tag_proposal_affairs WHERE proposal_id = %s ORDER BY affair_id"
# Das Tag aus accepted: die Aufgabe des Laufs, den der Entscheid geöffnet hat (extra proposal_id),
# und ob es noch dieses ist. Wer es seither neu angelegt hat, öffnete einen neueren Lauf.
ACCEPTED_TASK = """
SELECT r.task, r.id = (SELECT max(id) FROM classification_runs WHERE task = r.task)
FROM classification_runs r WHERE r.params->>'proposal_id' = %s ORDER BY r.id DESC LIMIT 1
"""


@dataclass(frozen=True)
class Decision:
    tag_id: str | None
    run: OpenResult | None


def decide(
    conn: psycopg.Connection,
    settings: Settings,
    proposal_id: int,
    *,
    decision: Literal["accepted", "merged", "rejected", "undo"],
    by: str,
    name_de: str | None = None,
    definition_de: str | None = None,
    broader: list[str] | None = None,
    related_tag_id: str | None = None,
) -> Decision:
    """Hält den Entscheid fest; accepted legt das Tag an und öffnet die Jobs der Geschäfte.

    ValueError: merged ohne Tag; RegistryError: ungültiges Tag, etwa ein unbekanntes broader.
    """
    row = conn.cursor(row_factory=dict_row).execute(PROPOSAL, (proposal_id,)).fetchone()
    if row is None:
        raise ProposalNotFound(f"Vorschlag {proposal_id} gibt es nicht")
    if decision == "undo":
        return _undo(conn, settings, proposal_id, row, by)
    if row["status"] == "done":
        raise ProposalDecided(f"Vorschlag {proposal_id} ist schon entschieden")
    if decision == "merged" and not (related_tag_id or row["related_tag_id"]):
        raise ValueError("merged braucht related_tag_id: das Tag, in dem der Vorschlag aufgeht")
    tag_id, run = None, None
    if decision == "accepted":
        child_of = row["recommendation"] == "child_of" and row["related_tag_id"]
        tag_id, registry = add_adhoc_tag(
            settings.registry_path,
            name_de=name_de or row["name_de"],
            definition_de=definition_de or row["desc_de"] or row["name_de"],
            by=by,
            broader=broader
            if broader is not None
            else ([row["related_tag_id"]] if child_of else []),
            proposal={
                "by": row["model_version"] or "apertus",
                "run": str(row["run_id"]) if row["run_id"] else None,
                "recommendation": row["recommendation"] or "new",
                "related_tag": row["related_tag_id"],
            },
        )
        sync_registry(conn, registry, file_hash(settings.registry_path))
        run = open_jobs(
            conn,
            task=adhoc_task(tag_id),
            bodies=None,
            since=None,
            limit=None,
            kind="adhoc",
            registry_version=registry.registry_version,
            scheme_hash=tag_hash(registry.get(tag_id)),
            prompt_version=load_prompt(settings.prompts_dir, STAGE_PROMPTS[1]).version,
            affair_ids=[affair_id for (affair_id,) in conn.execute(AFFAIRS, (proposal_id,))],
            extra={"proposal_id": proposal_id, "by": by},
        )
    params = {"decision": decision, "by": by, "related": related_tag_id, "id": proposal_id}
    if conn.execute(DECIDE, params).rowcount == 0:
        raise ProposalDecided(f"Vorschlag {proposal_id} ist schon entschieden")
    return Decision(tag_id, run)


def _undo(
    conn: psycopg.Connection, settings: Settings, proposal_id: int, row: dict, by: str
) -> Decision:
    """Zurück auf offen; Decision.tag_id ist das zurückgezogene Tag aus accepted, falls es seither
    niemand neu angelegt hat."""
    if row["status"] != "done":
        raise ProposalOpen(f"Vorschlag {proposal_id} ist nicht entschieden")
    tag_id = None
    if row["decision"] == "accepted":
        found = conn.execute(ACCEPTED_TASK, (str(proposal_id),)).fetchone()
        if found and found[1]:
            tag_id = task_tag(found[0])
            with contextlib.suppress(WrongStatus):  # schon zurückgezogen
                retire(conn, settings, tag_id, by=by)
    if conn.execute(REOPEN, {"by": by, "id": proposal_id}).rowcount == 0:
        raise ProposalOpen(f"Vorschlag {proposal_id} ist nicht entschieden")
    return Decision(tag_id, None)
