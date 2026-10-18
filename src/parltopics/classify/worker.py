"""Worker der Massenklassifikation: zweistufig, ein Geschäft je Anfrage (PRD 7.3, 7.7).

Ablauf je Job nach ARCHITEKTUR 3.2: Stufe 1 wählt APS-Kapitel, Stufe 2 Themen mit Konfidenz, Beleg
und Kurzzusammenfassung. Eine ungültige Antwort wird einmal mit Fehlerhinweis wiederholt. Tiefe
Konfidenz, Tag-Vorschläge, Texte ohne erkannte Sprache und eine feste Stichprobe von 2 % gehen im
selben Job an 70B (ARCHITEKTUR 3.4). Registry und Prompts werden beim Start eingefroren.
"""

import asyncio
import logging
import os
import socket
import time
import uuid
from collections import Counter
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, TypeVar

import httpx
import openai
import psycopg
from psycopg_pool import ConnectionPool
from pydantic import ValidationError

from parltopics.classify.queue import (
    Job,
    Label,
    Pass,
    Result,
    claim,
    fail,
    finish,
    heartbeat,
    mark_stage,
    release_stale,
    verify_evidence,
)
from parltopics.classify.schemas import OutputError, Stage2Output, parse_stage1, parse_stage2
from parltopics.config import Settings
from parltopics.llm import (
    JSONExtractionError,
    LLMClient,
    Prompt,
    blocked_by_allowlist,
    extract_json,
    load_prompt,
)
from parltopics.registry import RegistryError, Tag, load_registry, scheme_hash
from parltopics.registry.sync import synced_version

log = logging.getLogger("parltopics.worker")

STAGE_PROMPTS = ("classify_chapters_v1", "classify_topics_v1")
SAMPLE_EVERY = 50  # Stichprobe von 2 % nach affair_id: reproduzierbar, ohne Zufall
IDLE_SECONDS = 5
INVALID = (JSONExtractionError, OutputError, ValidationError)
T = TypeVar("T")


class OutputFailure(Exception):
    """Auch nach der Wiederholung keine gültige Antwort des Modells."""


@dataclass(frozen=True)
class Classifier:
    """Was ein Worker beim Start einfriert: Registry-Ausschnitt und Prompts (PRD 7.7)."""

    chapters: list[Tag]
    topics: dict[str, list[Tag]]
    adhoc: list[Tag]
    registry_version: str
    scheme_hash: str
    stage1: Prompt
    stage2: Prompt

    @property
    def prompt_version(self) -> str:
        """Beide Prompts von classify:aps in einer Spalte, getrennt durch ein Leerzeichen."""
        return f"{self.stage1.version} {self.stage2.version}"


def load_classifier(settings: Settings) -> Classifier:
    registry = load_registry(settings.registry_path)
    chapters = [tag for tag in registry.active("aps") if tag.aps_level == "kapitel"]
    return Classifier(
        chapters=chapters,
        topics={
            chapter.tag_id: [t for t in registry.narrower(chapter.tag_id) if t.scheme == "aps"]
            for chapter in chapters
        },
        adhoc=registry.active("adhoc"),
        registry_version=registry.registry_version,
        scheme_hash=scheme_hash(registry, "aps"),
        stage1=load_prompt(settings.prompts_dir, STAGE_PROMPTS[0]),
        stage2=load_prompt(settings.prompts_dir, STAGE_PROMPTS[1]),
    )


def _brief(error: Exception) -> str:
    """Fehler in einer Zeile, für den Hinweis an das Modell und für das Protokoll."""
    if isinstance(error, ValidationError):
        parts = (f"{'.'.join(map(str, e['loc'])) or 'Antwort'}: {e['msg']}" for e in error.errors())
        return "; ".join(parts)[:500]
    return " ".join(str(error).split())[:500]


async def _ask(
    client: LLMClient, messages: list[dict[str, Any]], large: bool, parse: Callable[[dict], T]
) -> tuple[T, str]:
    """Eine Stufe: Anfrage, JSON lösen und prüfen; einmal mit Fehlerhinweis wiederholen."""
    reply = await client.chat(messages, large=large)
    try:
        return parse(extract_json(reply.content)), reply.model
    except INVALID as error:
        hint = (
            f"Die Antwort war ungültig ({_brief(error)})."
            " Antworte nur mit dem JSON-Objekt nach dem Schema."
        )
        messages = [
            *messages,
            {"role": "assistant", "content": reply.content},
            {"role": "user", "content": hint},
        ]
    reply = await client.chat(messages, large=large)
    try:
        return parse(extract_json(reply.content)), reply.model
    except INVALID as error:
        raise OutputFailure(_brief(error)) from error


async def _pass(
    c: Classifier,
    client: LLMClient,
    job: Job,
    *,
    large: bool,
    verify: Callable[[str, list[str]], Awaitable[list[bool]]],
) -> tuple[Pass, Stage2Output]:
    """Beide Stufen mit 8B oder 70B, danach die Belegprüfung."""
    user = {"affair_id": job.affair_id, "text": job.text}
    chapter_ids = {chapter.tag_id for chapter in c.chapters}
    stage1, _ = await _ask(
        client,
        c.stage1.messages({"chapters": c.chapters}, user),
        large,
        lambda data: parse_stage1(data, affair_id=job.affair_id, offered=chapter_ids),
    )
    offered = {tag.tag_id: tag for choice in stage1.chapters for tag in c.topics[choice.chapter_id]}
    offered |= {tag.tag_id: tag for tag in c.adhoc}
    dropped: list[str] = []

    def parse2(data: dict) -> Stage2Output:
        output, rejected = parse_stage2(data, affair_id=job.affair_id, offered=set(offered))
        dropped.extend(rejected)
        return output

    stage2, model = await _ask(
        client, c.stage2.messages({"tags": list(offered.values())}, user), large, parse2
    )
    if dropped:
        log.info("affair_id=%s verworfene Tags: %s", job.affair_id, ", ".join(dropped))
    verified = await verify(job.text, [tag.evidence for tag in stage2.tags])
    labels = [
        # Unbelegt: Konfidenz halbiert (PRD 7.3); gerundet wie numeric(4,3) in affair_tags.
        Label(tag.tag_id, round(tag.confidence if ok else tag.confidence / 2, 3), tag.evidence, ok)
        for tag, ok in zip(stage2.tags, verified, strict=True)
    ]
    return Pass("70b" if large else "8b", model, labels), stage2


def escalation_reasons(
    job: Job, labels: list[Label], output: Stage2Output, threshold: float
) -> list[str]:
    """Wann 70B übernimmt (ARCHITEKTUR 3.4)."""
    checks = {
        "konfidenz": any(label.confidence < threshold for label in labels),
        "vorschlag": bool(output.proposed_tags),
        "sprache": job.language in (None, "other"),
        "stichprobe": job.affair_id % SAMPLE_EVERY == 0,
    }
    return [reason for reason, hit in checks.items() if hit]


async def classify_affair(
    c: Classifier,
    client: LLMClient,
    job: Job,
    *,
    threshold: float,
    verify: Callable[[str, list[str]], Awaitable[list[bool]]],
    escalate: Callable[[], Awaitable[None]],
) -> tuple[Result, list[str]]:
    """Klassifiziert ein Geschäft. Gibt das Ergebnis und die Gründe einer Eskalation zurück.

    OutputFailure: weder 8B noch 70B lieferten eine gültige Antwort, der Job ist dauerhaft failed.
    Ist nur die 70B-Antwort ungültig, gilt das 8B-Ergebnis (Grund `70b_ungueltig`).
    """
    passes: list[Pass] = []
    try:
        first, output = await _pass(c, client, job, large=False, verify=verify)
        passes.append(first)
        reasons = escalation_reasons(job, first.labels, output, threshold)
    except OutputFailure:
        reasons = ["json"]
    if reasons:
        await escalate()
        try:
            final, output = await _pass(c, client, job, large=True, verify=verify)
            passes.append(final)
        except OutputFailure:
            if not passes:
                raise
            # 70B unbrauchbar, 8B gültig: das 8B-Ergebnis gilt, statt den Job zu verwerfen.
            reasons.append("70b_ungueltig")
    result = Result(
        passes=passes,
        summary_de=output.summary_de,
        proposals=output.proposed_tags,
        prompt_version=c.prompt_version,
        registry_version=c.registry_version,
        scheme_hash=c.scheme_hash,
    )
    return result, reasons


async def run_worker(
    settings: Settings,
    *,
    task: str | None = None,
    run_id: int | None = None,
    once: bool = False,
    transport: httpx.AsyncBaseTransport | None = None,
) -> Counter[str]:
    """Übernimmt offene Jobs; mit once bis keine mehr offen sind, sonst ohne Ende.

    Gibt die Zahl der Jobs je Ausgang zurück (done, open, failed, lost_lock).
    """
    c = load_classifier(settings)
    worker_id = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:6]}"
    counts: Counter[str] = Counter()
    pool = ConnectionPool(
        settings.database_url, min_size=1, max_size=4, kwargs={"autocommit": True}, open=False
    )
    with pool:
        pool.wait(timeout=10)

        async def db(fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
            def call() -> T:
                with pool.connection() as conn:
                    return fn(conn, *args, **kwargs)

            return await asyncio.to_thread(call)

        synced = await db(synced_version)
        if synced != c.registry_version:
            raise RegistryError(
                f"Registry {c.registry_version} ist nicht synchronisiert (Datenbank: {synced});"
                " zuerst `parltopics registry sync`"
            )
        log.info(
            "worker %s: registry %s, prompts %s, %d parallel",
            worker_id,
            c.registry_version,
            c.prompt_version,
            settings.parallel_8b,
        )

        async def beat() -> None:
            while True:
                await asyncio.sleep(settings.heartbeat_seconds)
                try:
                    await db(heartbeat, worker_id)
                except psycopg.Error as error:
                    log.warning("Heartbeat fehlgeschlagen: %s", error)

        async with LLMClient(settings, transport=transport) as client:

            async def process(job: Job) -> None:
                start = time.monotonic()
                detail = ""
                if not job.text:
                    status = await db(fail, job, worker_id, "leerer Text", permanent=True)
                else:
                    try:
                        result, reasons = await classify_affair(
                            c,
                            client,
                            job,
                            threshold=settings.confidence_threshold,
                            verify=lambda text, evidences: db(verify_evidence, text, evidences),
                            escalate=lambda: db(mark_stage, job, worker_id, "70b"),
                        )
                    except OutputFailure as error:
                        detail = f"ungültige Antwort: {error}"
                        status = await db(fail, job, worker_id, detail, permanent=True)
                    except openai.APIError as error:
                        if blocked_by_allowlist(error):
                            raise
                        detail = f"{type(error).__name__}: {error}"
                        status = await db(fail, job, worker_id, detail, permanent=False)
                    except Exception as error:  # Absturz bei einem Geschäft zählt als Versuch
                        log.exception("affair_id=%s: unerwarteter Fehler", job.affair_id)
                        detail = f"{type(error).__name__}: {error}"
                        status = await db(fail, job, worker_id, detail, permanent=False)
                    else:
                        final = result.passes[-1]
                        done = await db(finish, job, worker_id, result)
                        status = "done" if done else None
                        detail = (
                            f"stage={final.stage} labels={len(final.labels)}"
                            f" reasons={','.join(reasons) or '-'}"
                        )
                status = status or "lost_lock"
                counts[status] += 1
                log.info(
                    "affair_id=%s status=%s %s ms=%d limit8b=%d",
                    job.affair_id,
                    status,
                    detail,
                    (time.monotonic() - start) * 1000,
                    client.limiter(settings.llm_name).limit,
                )

            async def claim_jobs(n: int) -> list[Job]:
                await db(release_stale, settings.job_timeout_seconds)
                return await db(claim, worker_id, n, task=task, run_id=run_id)

            beating = asyncio.create_task(beat())
            try:
                await fill_slots(claim_jobs, process, settings.parallel_8b, once=once)
            finally:
                beating.cancel()
    return counts


async def fill_slots(
    claim_jobs: Callable[[int], Awaitable[list[Job]]],
    process: Callable[[Job], Awaitable[None]],
    slots: int,
    *,
    once: bool,
    idle_seconds: float = IDLE_SECONDS,
) -> None:
    """Hält bis zu `slots` Jobs in Arbeit; ein frei gewordener Platz startet sofort den nächsten.

    So wartet nicht der ganze Stapel auf den langsamsten Job (etwa nach Eskalation an 70B).
    Übernommen wird weiter stapelweise, damit die Queue nicht öfter abgefragt wird; Jobs im Vorrat
    sind pending und vom Heartbeat gedeckt. Mit once endet die Schleife, wenn nichts mehr offen ist.
    """
    waiting: list[Job] = []
    running: set[asyncio.Task[None]] = set()
    try:
        while True:
            if not waiting and len(running) < slots:
                waiting = await claim_jobs(slots)
            while waiting and len(running) < slots:
                running.add(asyncio.create_task(process(waiting.pop(0))))
            if not running:
                if once:
                    return
                await asyncio.sleep(idle_seconds)
                continue
            done, running = await asyncio.wait(running, return_when=asyncio.FIRST_COMPLETED)
            for finished in done:
                finished.result()  # ein Fehler wie ein Allowlist-Verstoss beendet den Worker
    finally:
        for task in running:
            task.cancel()
