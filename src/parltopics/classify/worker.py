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
    TASK_APS,
    Job,
    Label,
    Pass,
    Result,
    adhoc_task,
    claim,
    fail,
    finish,
    heartbeat,
    mark_stage,
    release_stale,
    task_tag,
    verify_evidence,
)
from parltopics.classify.rules import CONFIDENCE, RULES_VERSION, match_rule
from parltopics.classify.schemas import (
    OutputError,
    Stage2Output,
    parse_single,
    parse_stage1,
    parse_stage2,
)
from parltopics.config import Settings
from parltopics.llm import (
    JSONExtractionError,
    LLMClient,
    Prompt,
    blocked_by_allowlist,
    extract_json,
    load_prompt,
)
from parltopics.registry import RegistryError, Tag, load_registry, scheme_hash, tag_hash
from parltopics.registry.sync import synced_version

log = logging.getLogger("parltopics.worker")

STAGE_PROMPTS = ("classify_chapters_v2", "classify_topics_v2")
SINGLE_PROMPT = "classify_single_v2"
INSTITUTIONS = "aps:1.2"  # Kapitel Institutionen: eigene Liste B in classify_single_v2
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
    known: dict[str, Tag]  # alle Tags der Registry, für Ad-hoc-Jobs auch vorgeschlagene
    single: Prompt | None = None  # gesetzt: APS-Jobs einstufig mit 70B (CLASSIFY_MODE)

    @property
    def prompt_version(self) -> str:
        """Prompt(s) von classify:aps; zweistufig beide, getrennt durch ein Leerzeichen."""
        if self.single is not None:
            return self.single.version
        return f"{self.stage1.version} {self.stage2.version}"

    @property
    def tasks(self) -> list[str]:
        """Aufgaben, die dieser Worker bearbeiten kann: APS und je vorgeschlagenes oder aktives
        Ad-hoc-Tag. Ein später angelegtes Tag übernimmt erst ein neu gestarteter Worker."""
        adhoc = (
            adhoc_task(tag.tag_id)
            for tag in self.known.values()
            if tag.scheme == "adhoc" and tag.status in ("proposed", "active")
        )
        return [TASK_APS, *adhoc]

    def versions(self, job: Job) -> tuple[str, str]:
        """prompt_version und scheme_hash eines Jobs; Ad-hoc nutzt nur Stufe 2 und ein Tag."""
        tag_id = task_tag(job.task)
        if tag_id is None:
            return self.prompt_version, self.scheme_hash
        return self.stage2.version, tag_hash(self.known[tag_id])


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
        known={tag.tag_id: tag for tag in registry.tags},
        single=(
            load_prompt(settings.prompts_dir, SINGLE_PROMPT)
            if settings.classify_mode == "single_70b"
            else None
        ),
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
    """Beide Stufen mit 8B oder 70B, danach die Belegprüfung. Ein Ad-hoc-Job braucht keine
    Kapitel: Stufe 2 bietet nur sein Tag an. Einstufig bietet ein Prompt alle Themen an."""
    user = {"affair_id": job.affair_id, "text": job.text}
    stage = "70b" if large else "8b"
    adhoc_id = task_tag(job.task)
    prompt = c.stage2
    if adhoc_id is not None:
        offered = {adhoc_id: c.known[adhoc_id]}
    elif c.single is not None:
        prompt = c.single
        institutions = {tag.tag_id: tag for tag in c.topics.get(INSTITUTIONS, [])}
        offered = {
            tag.tag_id: tag
            for chapter, tags in c.topics.items()
            if chapter != INSTITUTIONS
            for tag in tags
        }
        offered |= {tag.tag_id: tag for tag in c.adhoc}
    else:
        chapter_ids = {chapter.tag_id for chapter in c.chapters}
        stage1, _ = await _ask(
            client,
            c.stage1.messages({"chapters": c.chapters}, user),
            large,
            lambda data: parse_stage1(data, affair_id=job.affair_id, offered=chapter_ids),
        )
        offered = {
            tag.tag_id: tag for choice in stage1.chapters for tag in c.topics[choice.chapter_id]
        }
        offered |= {tag.tag_id: tag for tag in c.adhoc}
        if not offered:  # kein Kapitel und kein aktives Ad-hoc-Tag: nichts zur Auswahl
            empty = Stage2Output(affair_id=job.affair_id, language=stage1.language)
            settings = client.settings
            model = settings.llm_name_large if large else settings.llm_name
            return Pass(stage, model, []), empty
    dropped: list[str] = []
    single = c.single is not None and adhoc_id is None

    def parse2(data: dict) -> Stage2Output:
        if single:
            output, rejected = parse_single(
                data, affair_id=job.affair_id, topics=set(offered), institutions=set(institutions)
            )
        else:
            output, rejected = parse_stage2(data, affair_id=job.affair_id, offered=set(offered))
        dropped.extend(rejected)
        return output

    variables: dict[str, Any] = {"tags": list(offered.values())}
    if single:
        variables["institutions"] = list(institutions.values())
    messages = prompt.messages(variables, user)
    stage2, model = await _ask(client, messages, large, parse2)
    verified = await verify(job.text, [tag.evidence for tag in stage2.tags])
    if not all(verified):
        stage2, verified = await _requote(
            client, messages, large, parse2, stage2, verified, job.text, verify
        )
    if dropped:
        log.info("affair_id=%s verworfene Tags: %s", job.affair_id, ", ".join(dropped))
    labels = [
        # Unbelegt: Konfidenz halbiert (PRD 7.3); gerundet wie numeric(4,3) in affair_tags.
        Label(tag.tag_id, round(tag.confidence if ok else tag.confidence / 2, 3), tag.evidence, ok)
        for tag, ok in zip(stage2.tags, verified, strict=True)
    ]
    return Pass(stage, model, labels), stage2


async def _requote(
    client: LLMClient,
    messages: list[dict[str, Any]],
    large: bool,
    parse: Callable[[dict], Stage2Output],
    stage2: Stage2Output,
    verified: list[bool],
    text: str,
    verify: Callable[[str, list[str]], Awaitable[list[bool]]],
) -> tuple[Stage2Output, list[bool]]:
    """Einmal nachfragen, wenn Belege nicht wörtlich im Text stehen (Modelle umschreiben gern).

    Die neue Antwort gilt nur, wenn sie gültig ist und mehr Belege im Text gefunden werden.
    """
    missing = [tag.tag_id for tag, ok in zip(stage2.tags, verified, strict=True) if not ok]
    hint = (
        f"Diese Belege stehen nicht wörtlich im Geschäftstext: {', '.join(missing)}."
        " Ersetze sie durch exakt kopierte Abschnitte zwischen <<< und >>>, ohne eigene"
        " Formulierung. Antworte nur mit dem vollständigen JSON-Objekt nach dem Schema."
    )
    retry = [
        *messages,
        {"role": "assistant", "content": stage2.model_dump_json()},
        {"role": "user", "content": hint},
    ]
    reply = await client.chat(retry, large=large)
    try:
        again = parse(extract_json(reply.content))
    except INVALID:
        return stage2, verified
    checked = await verify(text, [tag.evidence for tag in again.tags])
    return (again, checked) if sum(checked) > sum(verified) else (stage2, verified)


def escalation_reasons(
    job: Job, labels: list[Label], output: Stage2Output, threshold: float
) -> list[str]:
    """Wann 70B übernimmt (ARCHITEKTUR 3.4). Ad-hoc-Jobs nur bei tiefer Konfidenz: ihre
    Stichprobe hat meist kein Thema, und ohne Kapitelwahl gibt es keine Vorschläge zu prüfen."""
    if task_tag(job.task) is not None:
        low = any(label.confidence < threshold for label in labels)
        return ["konfidenz"] if low else []
    checks = {
        "konfidenz": any(label.confidence < threshold for label in labels),
        "keine_themen": not labels,  # auch wenn 8B kein passendes Kapitel fand
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
    rule = match_rule(job.text) if task_tag(job.task) is None else None
    if rule is not None:
        # Routinegeschäft (Vorschlag B): Thema aus dem Titel, kein Modellaufruf.
        label = Label(rule.tag_id, CONFIDENCE, rule.evidence, True)
        language = job.language if job.language in ("de", "fr", "it", "rm") else "other"
        empty = Stage2Output(affair_id=job.affair_id, language=language)
        return _result(c, job, [Pass("rule", RULES_VERSION, [label])], empty), [
            f"regel:{rule.rule}"
        ]
    if c.single is not None and task_tag(job.task) is None:
        # Einstufig: ein 70B-Durchlauf, keine Eskalation. Ungültig auch nach der Wiederholung:
        # OutputFailure, der Job ist dauerhaft failed.
        final, output = await _pass(c, client, job, large=True, verify=verify)
        return _result(c, job, [final], output), []
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
    return _result(c, job, passes, output), reasons


def _result(c: Classifier, job: Job, passes: list[Pass], output: Stage2Output) -> Result:
    prompt_version, scheme = c.versions(job)
    return Result(
        passes=passes,
        summary_de=output.summary_de,
        proposals=[] if task_tag(job.task) else output.proposed_tags,
        prompt_version=prompt_version,
        registry_version=c.registry_version,
        scheme_hash=scheme,
    )


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
    if task and task_tag(task) is not None and task_tag(task) not in c.known:
        raise RegistryError(f"{task}: Tag {task_tag(task)} steht nicht in der Registry")
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
        # Einstufig arbeitet jeder Job mit 70B: so viele Plätze wie 70B-Anfragen erlaubt sind.
        slots = settings.parallel_70b if c.single is not None else settings.parallel_8b
        log.info(
            "worker %s: registry %s, prompts %s, %d parallel",
            worker_id,
            c.registry_version,
            c.prompt_version,
            slots,
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
                tasks = [task] if task else c.tasks
                return await db(claim, worker_id, n, tasks=tasks, run_id=run_id)

            beating = asyncio.create_task(beat())
            try:
                await fill_slots(claim_jobs, process, slots, once=once)
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
