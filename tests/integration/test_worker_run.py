"""Ein ganzer Lauf: Worker gegen PostgreSQL und Mock-LLM (PRD F5, F6, F18; M1 Mock-LLM-Tests)."""

import json
import os
from pathlib import Path

import httpx
import pytest
from psycopg.conninfo import make_conninfo

from parltopics.classify.queue import TASK_APS, open_jobs
from parltopics.classify.worker import load_classifier, run_worker
from parltopics.config import Settings
from parltopics.db import migrate
from parltopics.registry import file_hash, load_registry
from parltopics.registry.sync import sync_registry
from tests.mock_llm.app import completion, fake_completion

pytestmark = pytest.mark.integration

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "tags_example.yaml"


def mock_transport() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        content = fake_completion(body["messages"])
        return httpx.Response(200, json=completion(content, body["model"]))

    return httpx.MockTransport(handler)


async def test_a_run_classifies_every_job_once(conn, repo_root):
    migrate(conn, repo_root / "migrations")
    sync_registry(conn, load_registry(FIXTURE), file_hash(FIXTURE))
    for affair_id in (50, 51, 52):  # 50 fällt in die Stichprobe für 70B
        conn.execute(
            "INSERT INTO affairs (id, body_key, begin_date, raw)"
            " VALUES (%s, 'CHE', '2026-01-01', '{}')",
            (affair_id,),
        )
        conn.execute(
            "INSERT INTO affair_inputs (affair_id, text, language, source, input_hash)"
            " VALUES (%s, 'Der Bundesrat soll den Arbeitsmarkt stärken.', 'de', 'texts', %s)",
            (affair_id, f"h{affair_id}"),
        )
    schema = conn.execute("SELECT current_schema()").fetchone()[0]
    settings = Settings(
        _env_file=None,
        database_url=make_conninfo(
            os.environ["TEST_DATABASE_URL"], options=f"-c search_path={schema},public"
        ),
        llm_base_url="http://llm.test/v1",
        llm_name="test-8b",
        llm_name_large="test-70b",
        registry_path=FIXTURE,
        prompts_dir=repo_root / "prompts",
        parallel_8b=2,
        classify_mode="two_stage",  # prüft Eskalation 8B → 70B
    )
    classifier = load_classifier(settings)
    versions = {
        "registry_version": classifier.registry_version,
        "scheme_hash": classifier.scheme_hash,
        "prompt_version": classifier.prompt_version,
    }

    def open_run():
        return open_jobs(
            conn, task=TASK_APS, bodies=None, since=None, limit=None, kind="full", **versions
        )

    run = open_run()
    counts = await run_worker(
        settings, task=TASK_APS, run_id=run.run_id, once=True, transport=mock_transport()
    )
    assert counts == {"done": 3}

    labels = conn.execute(
        "SELECT affair_id, tag_id, stage, status, model_version FROM affair_tags"
        " ORDER BY affair_id, id"
    ).fetchall()
    assert labels == [
        (50, "aps:2.4.1", "8b", "superseded", "test-8b"),
        (50, "aps:2.4.1", "70b", "active", "test-70b"),
        (51, "aps:2.4.1", "8b", "active", "test-8b"),
        (52, "aps:2.4.1", "8b", "active", "test-8b"),
    ]
    jobs = conn.execute("SELECT DISTINCT status, prompt_version FROM classification_jobs")
    assert jobs.fetchall() == [("done", classifier.prompt_version)]
    stats = "SELECT n_total, n_done, n_escalated, finished_at IS NOT NULL FROM classification_runs"
    assert conn.execute(stats).fetchone() == (3, 3, 1, True)
    assert open_run().total == 0  # nichts geändert, nichts offen (F18)
