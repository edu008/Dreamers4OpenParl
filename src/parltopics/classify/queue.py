"""Job-Queue in PostgreSQL: Jobs öffnen, übernehmen, Heartbeat, Aufräumen, Ergebnis schreiben.

PRD 7.7, ARCHITEKTUR 3.2, ADR 0002. Jeder Statuswechsel steht in job_events. Ein Worker schreibt
nur, solange sein Job noch pending ist und seine worker_id trägt (Besitzprüfung). Labels werden nie
gelöscht, nur auf superseded oder rejected gesetzt. Alle Funktionen erwarten eine Verbindung im
Autocommit; was zusammengehört, läuft in einer eigenen Transaktion.
"""

from dataclasses import dataclass
from datetime import date

import psycopg
from psycopg.types.json import Jsonb

from parltopics.classify.schemas import TagProposal

TASK_APS = "classify:aps"
MAX_ATTEMPTS = 3
EVIDENCE_SIMILARITY = 0.9


@dataclass(frozen=True)
class Job:
    affair_id: int
    task: str
    attempts: int
    run_id: int | None
    text: str | None
    input_hash: str | None
    language: str | None


@dataclass(frozen=True)
class Label:
    tag_id: str
    confidence: float
    evidence: str
    evidence_verified: bool


@dataclass(frozen=True)
class Pass:
    """Antwort eines Modells für ein Geschäft: 8B oder, nach Eskalation, 70B."""

    stage: str
    model_version: str
    labels: list[Label]


@dataclass(frozen=True)
class Result:
    passes: list[Pass]  # der letzte Durchlauf gilt, frühere werden als superseded gespeichert
    summary_de: str | None
    proposals: list[TagProposal]
    prompt_version: str
    registry_version: str
    scheme_hash: str


@dataclass(frozen=True)
class OpenResult:
    run_id: int
    total: int  # Jobs, die dieser Lauf bearbeitet
    new: int
    reopened: int  # done oder failed wieder auf open


# Geschäfte eines Laufs: mit Klassifikationstext, neueste zuerst.
SCOPE = """
SELECT a.id FROM affairs a JOIN affair_inputs i ON i.affair_id = a.id
WHERE (%(bodies)s::text[] IS NULL OR a.body_key = ANY(%(bodies)s::text[]))
  AND (%(since)s::date IS NULL OR a.begin_date >= %(since)s::date)
ORDER BY a.begin_date DESC NULLS LAST, a.id DESC
LIMIT %(limit)s
"""
NEW_RUN = """
INSERT INTO classification_runs (kind, task, params, registry_version, scheme_hash, prompt_version)
VALUES (%s, %s, %s, %s, %s, %s)
RETURNING id
"""
OPEN_NEW = f"""
WITH scope AS ({SCOPE}),
inserted AS (
    INSERT INTO classification_jobs (affair_id, task, run_id)
    SELECT id, %(task)s, %(run_id)s FROM scope
    ON CONFLICT (affair_id, task) DO NOTHING
    RETURNING affair_id
)
INSERT INTO job_events (affair_id, task, to_status, reason, run_id)
SELECT affair_id, %(task)s, 'open', 'new', %(run_id)s FROM inserted
"""
# Wieder öffnen (PRD 7.7): done mit anderem Text, Prompt oder scheme_hash; failed nur mit neuem
# Prompt; offene Jobs früherer Läufe übernimmt der neue Lauf. pending gehört einem Worker.
OPEN_STALE = f"""
WITH scope AS ({SCOPE}),
stale AS (
    SELECT j.affair_id, j.status, j.run_id FROM classification_jobs j
    JOIN scope ON scope.id = j.affair_id
    JOIN affair_inputs i ON i.affair_id = j.affair_id
    LEFT JOIN classification_runs r ON r.id = j.run_id
    WHERE j.task = %(task)s AND j.run_id IS DISTINCT FROM %(run_id)s
      AND (j.status = 'open'
           OR (j.status = 'done' AND (j.input_hash IS DISTINCT FROM i.input_hash
                                      OR j.prompt_version IS DISTINCT FROM %(prompt_version)s
                                      OR j.scheme_hash IS DISTINCT FROM %(scheme_hash)s))
           OR (j.status = 'failed' AND r.prompt_version IS DISTINCT FROM %(prompt_version)s))
    FOR UPDATE OF j
),
reopened AS (
    UPDATE classification_jobs j
    SET status = 'open', run_id = %(run_id)s, attempts = 0, last_error = NULL, updated_at = now()
    FROM stale
    WHERE j.affair_id = stale.affair_id AND j.task = %(task)s
    RETURNING j.affair_id, stale.status AS old_status, stale.run_id AS old_run
),
logged AS (
    INSERT INTO job_events (affair_id, task, from_status, to_status, reason, run_id)
    SELECT affair_id, %(task)s, old_status, 'open', 'reopen', %(run_id)s FROM reopened
    WHERE old_status <> 'open'
)
SELECT old_status, old_run FROM reopened
"""
COUNT_RUN = """
UPDATE classification_runs r
SET n_total = c.n, finished_at = CASE WHEN c.n = 0 THEN now() END
FROM (SELECT count(*) AS n FROM classification_jobs WHERE run_id = %(run_id)s) c
WHERE r.id = %(run_id)s
RETURNING n_total
"""
# Ein Lauf ist fertig, wenn keiner seiner Jobs mehr open oder pending ist (PRD 7.7).
CLOSE_RUNS = """
UPDATE classification_runs r SET finished_at = now()
WHERE r.id = ANY(%s) AND r.finished_at IS NULL
  AND NOT EXISTS (
      SELECT 1 FROM classification_jobs j WHERE j.run_id = r.id AND j.status IN ('open', 'pending')
  )
"""
CLAIM = """
WITH next AS (
    SELECT j.affair_id, j.task FROM classification_jobs j JOIN affairs a ON a.id = j.affair_id
    WHERE j.status = 'open'
      AND (%(task)s::text IS NULL OR j.task = %(task)s::text)
      AND (%(run_id)s::integer IS NULL OR j.run_id = %(run_id)s::integer)
    ORDER BY j.priority, a.begin_date DESC NULLS LAST
    LIMIT %(batch)s
    FOR UPDATE OF j SKIP LOCKED
),
claimed AS (
    UPDATE classification_jobs j
    SET status = 'pending', stage = '8b', worker_id = %(worker_id)s, locked_at = now(),
        attempts = j.attempts + 1, updated_at = now()
    FROM next LEFT JOIN affair_inputs i ON i.affair_id = next.affair_id
    WHERE j.affair_id = next.affair_id AND j.task = next.task
    RETURNING j.affair_id, j.task, j.attempts, j.run_id, i.text, i.input_hash, i.language
),
logged AS (
    INSERT INTO job_events (affair_id, task, from_status, to_status, reason, run_id, worker_id)
    SELECT affair_id, task, 'open', 'pending', 'claim', run_id, %(worker_id)s FROM claimed
)
SELECT affair_id, task, attempts, run_id, text, input_hash, language FROM claimed
"""
RELEASE_STALE = """
WITH stale AS (
    UPDATE classification_jobs
    SET status = CASE WHEN attempts >= %(max_attempts)s THEN 'failed' ELSE 'open' END,
        worker_id = NULL, locked_at = NULL, last_error = 'timeout', updated_at = now()
    WHERE status = 'pending' AND locked_at < now() - make_interval(secs => %(timeout)s)
    RETURNING affair_id, task, status, run_id
),
logged AS (
    INSERT INTO job_events (affair_id, task, from_status, to_status, reason, run_id)
    SELECT affair_id, task, 'pending', status, 'timeout', run_id FROM stale
),
counted AS (
    UPDATE classification_runs r SET n_failed = r.n_failed + s.n
    FROM (SELECT run_id, count(*) AS n FROM stale WHERE status = 'failed' GROUP BY run_id) s
    WHERE r.id = s.run_id
)
SELECT affair_id, task, status, run_id FROM stale
"""
OWN = """
UPDATE classification_jobs
SET status = 'done', stage = %(stage)s, input_hash = %(input_hash)s,
    prompt_version = %(prompt_version)s, scheme_hash = %(scheme_hash)s, locked_at = NULL,
    last_error = NULL, updated_at = now()
WHERE affair_id = %(affair_id)s AND task = %(task)s AND worker_id = %(worker_id)s
  AND status = 'pending'
RETURNING affair_id
"""
LOST_LOCK = """
INSERT INTO job_events (affair_id, task, from_status, to_status, reason, run_id, worker_id)
SELECT affair_id, task, status, status, 'lost_lock', run_id, %(worker_id)s
FROM classification_jobs WHERE affair_id = %(affair_id)s AND task = %(task)s
"""
# Menschliche Entscheide haben Vorrang (PRD 7.3): bestätigte und von Hand ergänzte Labels bleiben
# aktiv; verworfene oder ersetzte Tags kehren für denselben Text nur als rejected zurück.
HUMAN = """
SELECT tag_id, status = 'active' AND (stage = 'human' OR review_status = 'confirmed') AS kept
FROM affair_tags
WHERE affair_id = %(affair_id)s
  AND ((status = 'active' AND (stage = 'human' OR review_status = 'confirmed'))
       OR (review_status IN ('rejected', 'changed') AND input_hash = %(input_hash)s))
"""
SUPERSEDE = """
UPDATE affair_tags SET status = 'superseded'
WHERE affair_id = %(affair_id)s AND status = 'active'
  AND (task = %(task)s OR tag_id = ANY(%(tag_ids)s))
  AND stage <> 'human' AND review_status IS DISTINCT FROM 'confirmed'
"""
INSERT_LABEL = """
INSERT INTO affair_tags (affair_id, tag_id, scheme, confidence, evidence, evidence_verified, task,
                         stage, model_version, prompt_version, registry_version, input_hash,
                         run_id, status)
VALUES (%(affair_id)s, %(tag_id)s, %(scheme)s, %(confidence)s, %(evidence)s,
        %(evidence_verified)s, %(task)s, %(stage)s, %(model_version)s, %(prompt_version)s,
        %(registry_version)s, %(input_hash)s, %(run_id)s, %(status)s)
"""
SUPERSEDE_SUMMARY = """
UPDATE affair_summaries SET status = 'superseded'
WHERE affair_id = %(affair_id)s AND language = 'de' AND status = 'active'
"""
INSERT_SUMMARY = """
INSERT INTO affair_summaries (affair_id, language, summary, task, stage, model_version,
                              prompt_version, input_hash, run_id)
VALUES (%(affair_id)s, 'de', %(summary)s, %(task)s, %(stage)s, %(model_version)s,
        %(prompt_version)s, %(input_hash)s, %(run_id)s)
"""
INSERT_PROPOSAL = """
INSERT INTO tag_proposal_raw (affair_id, run_id, name_de, desc_de, reason, model_version)
VALUES (%(affair_id)s, %(run_id)s, %(name_de)s, %(desc_de)s, %(reason)s, %(model_version)s)
"""
DONE_EVENT = """
INSERT INTO job_events (affair_id, task, from_status, to_status, reason, run_id, worker_id)
VALUES (%(affair_id)s, %(task)s, 'pending', 'done', %(stage)s, %(run_id)s, %(worker_id)s)
"""
COUNT_DONE = """
UPDATE classification_runs SET n_done = n_done + 1, n_escalated = n_escalated + %(escalated)s
WHERE id = %(run_id)s
"""
FAIL = """
WITH failed AS (
    UPDATE classification_jobs
    SET status = CASE WHEN %(permanent)s OR attempts >= %(max_attempts)s THEN 'failed'
                      ELSE 'open' END,
        worker_id = NULL, locked_at = NULL, last_error = left(%(error)s, 500), updated_at = now()
    WHERE affair_id = %(affair_id)s AND task = %(task)s AND worker_id = %(worker_id)s
      AND status = 'pending'
    RETURNING affair_id, task, status, run_id
),
logged AS (
    INSERT INTO job_events (affair_id, task, from_status, to_status, reason, run_id, worker_id)
    SELECT affair_id, task, 'pending', status, left(%(error)s, 200), run_id, %(worker_id)s
    FROM failed
),
counted AS (
    UPDATE classification_runs r SET n_failed = r.n_failed + 1
    FROM failed f WHERE r.id = f.run_id AND f.status = 'failed'
)
SELECT status FROM failed
"""


def acquire_run_lock(conn: psycopg.Connection, task: str) -> bool:
    """Höchstens ein Lauf je Aufgabe (PRD 7.7). Die Sperre hält, bis die Verbindung schliesst."""
    return conn.execute("SELECT pg_try_advisory_lock(hashtext(%s))", (f"run:{task}",)).fetchone()[0]


def open_jobs(
    conn: psycopg.Connection,
    *,
    task: str,
    bodies: list[str] | None,
    since: date | None,
    limit: int | None,
    kind: str,
    registry_version: str,
    scheme_hash: str,
    prompt_version: str,
) -> OpenResult:
    """Legt einen Lauf an und öffnet seine Jobs: neue Geschäfte und veraltete Ergebnisse."""
    params = {
        "task": task,
        "bodies": bodies,
        "since": since,
        "limit": limit,
        "scheme_hash": scheme_hash,
        "prompt_version": prompt_version,
    }
    logged = {"bodies": bodies, "since": since.isoformat() if since else None, "limit": limit}
    with conn.transaction():
        run_id = conn.execute(
            NEW_RUN, (kind, task, Jsonb(logged), registry_version, scheme_hash, prompt_version)
        ).fetchone()[0]
        params["run_id"] = run_id
        new = conn.execute(OPEN_NEW, params).rowcount
        moved = conn.execute(OPEN_STALE, params).fetchall()
        old_runs = sorted({old_run for _, old_run in moved if old_run is not None})
        if old_runs:
            conn.execute(CLOSE_RUNS, (old_runs,))
        total = conn.execute(COUNT_RUN, {"run_id": run_id}).fetchone()[0]
    reopened = sum(old_status != "open" for old_status, _ in moved)
    return OpenResult(run_id=run_id, total=total, new=new, reopened=reopened)


def claim(
    conn: psycopg.Connection,
    worker_id: str,
    batch: int,
    *,
    task: str | None = None,
    run_id: int | None = None,
) -> list[Job]:
    """Übernimmt offene Jobs mit SKIP LOCKED: Priorität, dann neueste Geschäfte zuerst."""
    params = {"worker_id": worker_id, "batch": batch, "task": task, "run_id": run_id}
    return [Job(*row) for row in conn.execute(CLAIM, params).fetchall()]


def mark_stage(conn: psycopg.Connection, job: Job, worker_id: str, stage: str) -> None:
    """Eskalation bleibt im selben Job: pending, stage wechselt (PRD 7.7)."""
    conn.execute(
        "UPDATE classification_jobs SET stage = %s, updated_at = now()"
        " WHERE affair_id = %s AND task = %s AND worker_id = %s AND status = 'pending'",
        (stage, job.affair_id, job.task, worker_id),
    )


def heartbeat(conn: psycopg.Connection, worker_id: str) -> int:
    return conn.execute(
        "UPDATE classification_jobs SET locked_at = now()"
        " WHERE worker_id = %s AND status = 'pending'",
        (worker_id,),
    ).rowcount


def release_stale(conn: psycopg.Connection, timeout_seconds: int) -> list[tuple[int, str, str]]:
    """Gibt Jobs ohne Heartbeat frei: zurück auf open, ab dem dritten Versuch failed.

    Idempotent und zeilengesperrt, darum darf jeder Worker es aufrufen.
    """
    params = {"timeout": timeout_seconds, "max_attempts": MAX_ATTEMPTS}
    with conn.transaction():
        released = conn.execute(RELEASE_STALE, params).fetchall()
        runs = sorted({run_id for *_, run_id in released if run_id is not None})
        if runs:
            conn.execute(CLOSE_RUNS, (runs,))
    return [(affair_id, task, status) for affair_id, task, status, _ in released]


def verify_evidence(conn: psycopg.Connection, text: str, evidences: list[str]) -> list[bool]:
    """Belegprüfung mit pg_trgm (PRD 7.3): steht der Beleg unscharf wörtlich im Text?"""
    if not evidences:
        return []
    rows = conn.execute(
        "SELECT word_similarity(e, %s) >= %s"
        " FROM unnest(%s::text[]) WITH ORDINALITY AS u(e, n) ORDER BY n",
        (text, EVIDENCE_SIMILARITY, evidences),
    ).fetchall()
    return [verified for (verified,) in rows]


def finish(conn: psycopg.Connection, job: Job, worker_id: str, result: Result) -> bool:
    """Schreibt das Ergebnis, wenn der Job noch diesem Worker gehört. False: Besitz verloren."""
    final = result.passes[-1]
    key = {
        "affair_id": job.affair_id,
        "task": job.task,
        "worker_id": worker_id,
        "run_id": job.run_id,
        "input_hash": job.input_hash,
        "prompt_version": result.prompt_version,
    }
    with conn.transaction():
        owned = conn.execute(
            OWN, {**key, "stage": final.stage, "scheme_hash": result.scheme_hash}
        ).fetchone()
        if owned is not None:
            _write_result(conn, job, key, result)
    if owned is None:
        conn.execute(LOST_LOCK, key)
        return False
    return True


def _write_result(conn: psycopg.Connection, job: Job, key: dict, result: Result) -> None:
    final = result.passes[-1]
    human = conn.execute(HUMAN, key).fetchall()
    kept = {tag_id for tag_id, keep in human if keep}
    rejected = {tag_id for tag_id, keep in human if not keep} - kept

    def row(stage_pass: Pass, label: Label, status: str) -> dict:
        return {
            **key,
            "tag_id": label.tag_id,
            "scheme": label.tag_id.split(":", 1)[0],
            "confidence": label.confidence,
            "evidence": label.evidence,
            "evidence_verified": label.evidence_verified,
            "stage": stage_pass.stage,
            "model_version": stage_pass.model_version,
            "registry_version": result.registry_version,
            "status": status,
        }

    rows = [row(p, label, "superseded") for p in result.passes[:-1] for label in p.labels]
    final_labels = [label for label in final.labels if label.tag_id not in kept]
    active = [label.tag_id for label in final_labels if label.tag_id not in rejected]
    rows += [
        row(final, label, "rejected" if label.tag_id in rejected else "active")
        for label in final_labels
    ]
    conn.execute(SUPERSEDE, {**key, "tag_ids": active})
    conn.cursor().executemany(INSERT_LABEL, rows)
    model = {"stage": final.stage, "model_version": final.model_version}
    if result.summary_de:
        conn.execute(SUPERSEDE_SUMMARY, key)
        conn.execute(INSERT_SUMMARY, {**key, **model, "summary": result.summary_de})
    if result.proposals:
        conn.cursor().executemany(
            INSERT_PROPOSAL,
            [
                {
                    **key,
                    "name_de": proposal.name_de,
                    "desc_de": proposal.description_de,
                    "reason": proposal.reason,
                    "model_version": final.model_version,
                }
                for proposal in result.proposals
            ],
        )
    conn.execute(DONE_EVENT, {**key, **model})
    conn.execute(COUNT_DONE, {**key, "escalated": int(final.stage == "70b")})
    conn.execute(CLOSE_RUNS, ([job.run_id],))


def fail(
    conn: psycopg.Connection, job: Job, worker_id: str, error: str, *, permanent: bool
) -> str | None:
    """Fehler eines Jobs: dauerhaft oder ab dem dritten Versuch failed, sonst wieder open.

    Gibt den neuen Status zurück, None bei verlorenem Besitz.
    """
    params = {
        "affair_id": job.affair_id,
        "task": job.task,
        "worker_id": worker_id,
        "error": error,
        "permanent": permanent,
        "max_attempts": MAX_ATTEMPTS,
    }
    with conn.transaction():
        row = conn.execute(FAIL, params).fetchone()
        if row is not None:
            conn.execute(CLOSE_RUNS, ([job.run_id],))
    return row[0] if row else None


def summary(conn: psycopg.Connection) -> list[tuple[str, str, int]]:
    """Zählung je Aufgabe und Status (F18, GET /v1/jobs/summary)."""
    return conn.execute(
        "SELECT task, status, count(*) FROM classification_jobs GROUP BY task, status"
        " ORDER BY task, status"
    ).fetchall()
