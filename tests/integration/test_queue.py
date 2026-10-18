"""Job-Queue gegen ein echtes PostgreSQL (PRD 7.7, F18, F19; ARCHITEKTUR 3.2)."""

import os
from datetime import date
from pathlib import Path

import psycopg
import pytest

from parltopics.classify.queue import (
    TASK_APS,
    Label,
    Pass,
    Result,
    acquire_run_lock,
    claim,
    fail,
    finish,
    heartbeat,
    open_jobs,
    release_stale,
    summary,
    verify_evidence,
)
from parltopics.classify.schemas import TagProposal
from parltopics.db import migrate
from parltopics.registry import file_hash, load_registry
from parltopics.registry.sync import sync_registry

pytestmark = pytest.mark.integration

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "tags_example.yaml"
TEXT = "Der Bundesrat soll die Digitalisierung der Verwaltung beschleunigen."
SUMMARY = "Der Bundesrat soll die Verwaltung digitalisieren."


@pytest.fixture
def db(conn, repo_root):
    migrate(conn, repo_root / "migrations")
    sync_registry(conn, load_registry(FIXTURE), file_hash(FIXTURE))
    affair = "INSERT INTO affairs (id, body_key, begin_date, raw) VALUES (%s, 'CHE', %s, '{}')"
    for affair_id in (1, 2, 3, 4):
        conn.execute(affair, (affair_id, date(2026, 1, affair_id)))
    for affair_id in (1, 2, 3):  # Geschäft 4 hat keinen Klassifikationstext
        conn.execute(
            "INSERT INTO affair_inputs (affair_id, text, language, source, input_hash)"
            " VALUES (%s, %s, 'de', 'texts', %s)",
            (affair_id, TEXT, f"h{affair_id}"),
        )
    return conn


def open_aps(conn, limit=None, prompt_version="p1"):
    return open_jobs(
        conn,
        task=TASK_APS,
        bodies=["CHE"],
        since=None,
        limit=limit,
        kind="full",
        registry_version="2026-10-18.3",
        scheme_hash="s1",
        prompt_version=prompt_version,
    )


def label(tag_id, confidence=0.9):
    return Label(tag_id, confidence, "Digitalisierung der Verwaltung", True)


def result(*passes, prompt_version="p1", proposals=()):
    return Result(
        passes=list(passes),
        summary_de=SUMMARY,
        proposals=list(proposals),
        prompt_version=prompt_version,
        registry_version="2026-10-18.3",
        scheme_hash="s1",
    )


def simple(tag_id="aps:6.1.9", prompt_version="p1"):
    return result(Pass("8b", "m8", [label(tag_id)]), prompt_version=prompt_version)


def other_connection(conn):
    schema = conn.execute("SELECT current_schema()").fetchone()[0]
    return psycopg.connect(
        os.environ["TEST_DATABASE_URL"], autocommit=True, options=f"-c search_path={schema},public"
    )


def test_open_jobs_needs_an_input_and_does_nothing_twice(db):
    first = open_aps(db)
    assert (first.total, first.new, first.reopened) == (3, 3, 0)
    jobs = claim(db, "w", 10)
    assert [job.affair_id for job in jobs] == [3, 2, 1]  # neueste zuerst
    for job in jobs:
        assert finish(db, job, "w", simple())
    again = open_aps(db)
    assert (again.total, again.new, again.reopened) == (0, 0, 0)
    finished = "SELECT count(*) FROM classification_runs WHERE finished_at IS NOT NULL"
    assert db.execute(finished).fetchone() == (2,)


def test_changed_text_or_prompt_reopens_done_jobs_and_failed_only_with_a_new_prompt(db):
    open_aps(db)
    for job in claim(db, "w", 10):
        if job.affair_id == 1:
            assert fail(db, job, "w", "leerer Text", permanent=True) == "failed"
        else:
            assert finish(db, job, "w", simple())
    db.execute("UPDATE affair_inputs SET input_hash = 'neu' WHERE affair_id = 2")
    changed = open_aps(db)
    assert (changed.total, changed.new, changed.reopened) == (1, 0, 1)

    (pending,) = claim(db, "w", 10)
    assert pending.affair_id == 2
    newer = open_aps(db, prompt_version="p2")
    assert (newer.total, newer.reopened) == (2, 2)  # der pending-Job bleibt beim Worker
    events = db.execute(
        "SELECT affair_id, from_status FROM job_events WHERE reason = 'reopen'"
    ).fetchall()
    assert set(events) == {(2, "done"), (3, "done"), (1, "failed")}


def test_two_workers_never_claim_the_same_job(db):
    open_aps(db)
    with other_connection(db) as other, db.transaction():
        mine = claim(db, "w1", 2)
        theirs = claim(other, "w2", 10)
    assert [job.affair_id for job in mine] == [3, 2]
    assert [job.affair_id for job in theirs] == [1]


def test_a_second_run_of_the_same_task_is_refused(db):
    with other_connection(db) as other:
        assert acquire_run_lock(db, TASK_APS)
        assert not acquire_run_lock(other, TASK_APS)
        assert acquire_run_lock(other, "classify:adhoc:x")


def test_a_worker_whose_job_was_handed_over_writes_nothing(db):
    open_aps(db, limit=1)
    (job,) = claim(db, "w1", 1)
    db.execute("UPDATE classification_jobs SET locked_at = now() - interval '1 hour'")
    assert release_stale(db, 600) == [(3, TASK_APS, "open")]
    (again,) = claim(db, "w2", 1)
    assert not finish(db, job, "w1", simple())
    assert db.execute("SELECT count(*) FROM affair_tags").fetchone() == (0,)
    assert finish(db, again, "w2", simple())
    reasons = [reason for (reason,) in db.execute("SELECT reason FROM job_events ORDER BY id")]
    assert reasons == ["new", "claim", "timeout", "claim", "lost_lock", "8b"]


def test_heartbeat_keeps_the_job_and_the_third_timeout_fails_it(db):
    open_aps(db, limit=1)
    claim(db, "w", 1)
    db.execute("UPDATE classification_jobs SET locked_at = now() - interval '1 hour'")
    assert heartbeat(db, "w") == 1
    assert release_stale(db, 600) == []
    for expected in ("open", "open", "failed"):
        db.execute("UPDATE classification_jobs SET locked_at = now() - interval '1 hour'")
        assert release_stale(db, 600)[0][2] == expected
        claim(db, "w", 1)
    run = "SELECT n_failed, finished_at IS NOT NULL FROM classification_runs"
    assert db.execute(run).fetchone() == (1, True)


def test_finish_replaces_labels_and_respects_human_decisions(db):
    open_aps(db, limit=1)
    (job,) = claim(db, "w", 1)
    old = (
        "INSERT INTO affair_tags (affair_id, tag_id, scheme, confidence, task, stage,"
        " model_version, prompt_version, registry_version, input_hash, status, review_status)"
        " VALUES (3, %s, %s, 0.8, %s, %s, 'm', 'p0', 'v', 'h3', %s, %s)"
    )
    db.execute(old, ("aps:2.4.1", "aps", TASK_APS, "8b", "active", None))
    db.execute(old, ("adhoc:digitalisierung-breit", "adhoc", "adhoc:x", "8b", "active", None))
    db.execute(old, ("aps:6.1", "aps", TASK_APS, "human", "active", None))
    db.execute(old, ("aps:6.1.9", "aps", TASK_APS, "8b", "superseded", "rejected"))
    escalated = result(
        Pass("8b", "m8", [label("aps:2.4.1", 0.4)]),
        Pass("70b", "m70", [label(tag) for tag in ("aps:6.1.9", "adhoc:digitalisierung-breit")]),
        proposals=[TagProposal(name_de="E-Government", description_de="Verwaltung", reason="neu")],
    )
    escalated.passes[-1].labels.append(label("aps:6.1"))
    assert finish(db, job, "w", escalated)

    new = db.execute(
        "SELECT tag_id, stage, status, model_version FROM affair_tags"
        " WHERE prompt_version = 'p1' ORDER BY id"
    ).fetchall()
    assert new == [
        ("aps:2.4.1", "8b", "superseded", "m8"),
        ("aps:6.1.9", "70b", "rejected", "m70"),
        ("adhoc:digitalisierung-breit", "70b", "active", "m70"),
    ]
    previous = "SELECT tag_id, status FROM affair_tags WHERE prompt_version = 'p0'"
    assert dict(db.execute(previous).fetchall()) == {
        "aps:2.4.1": "superseded",
        "adhoc:digitalisierung-breit": "superseded",
        "aps:6.1": "active",
        "aps:6.1.9": "superseded",
    }
    active_summary = "SELECT summary, stage FROM affair_summaries WHERE status = 'active'"
    assert db.execute(active_summary).fetchone() == (SUMMARY, "70b")
    proposal = "SELECT name_de, model_version FROM tag_proposal_raw"
    assert db.execute(proposal).fetchone() == ("E-Government", "m70")
    run = "SELECT n_done, n_escalated, finished_at IS NOT NULL FROM classification_runs"
    assert db.execute(run).fetchone() == (1, 1, True)


def test_reclassifying_never_hits_the_unique_index(db):
    for prompt_version in ("p1", "p2"):
        open_aps(db, limit=1, prompt_version=prompt_version)
        (job,) = claim(db, "w", 1)
        assert finish(db, job, "w", simple(prompt_version=prompt_version))
    labels = db.execute("SELECT prompt_version, status FROM affair_tags ORDER BY id").fetchall()
    assert labels == [("p1", "superseded"), ("p2", "active")]
    summaries = db.execute("SELECT status FROM affair_summaries ORDER BY id").fetchall()
    assert summaries == [("superseded",), ("active",)]


def test_fail_retries_transient_errors_three_times(db):
    open_aps(db, limit=1)
    for expected in ("open", "open", "failed"):
        (job,) = claim(db, "w", 1)
        assert fail(db, job, "w", "Zeitüberschreitung", permanent=False) == expected
    assert fail(db, job, "w", "zu spät", permanent=True) is None  # gehört niemandem mehr
    assert summary(db) == [(TASK_APS, "failed", 1)]
    error = "SELECT last_error FROM classification_jobs"
    assert db.execute(error).fetchone() == ("Zeitüberschreitung",)


def test_verify_evidence_tolerates_small_differences(db):
    evidences = [
        "Digitalisierung der Verwaltung",
        "digitalisierung der  verwaltung!",
        "Landwirtschaft und Tierschutz",
    ]
    assert verify_evidence(db, TEXT, evidences) == [True, True, False]
    assert verify_evidence(db, TEXT, []) == []
