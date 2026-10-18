"""Ablauf eines Jobs im Worker mit Mock-LLM (PRD 7.3, ARCHITEKTUR 3.2 bis 3.4)."""

import asyncio
import json
from pathlib import Path

import httpx
import pytest

from parltopics.classify.queue import Job
from parltopics.classify.worker import OutputFailure, classify_affair, fill_slots, load_classifier
from parltopics.llm import LLMClient
from tests.mock_llm.app import completion, fake_completion

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "tags_example.yaml"
TEXT = "Der Bundesrat soll den Arbeitsmarkt für ältere Arbeitnehmende stärken."


@pytest.fixture
def classifier(settings):
    return load_classifier(settings.model_copy(update={"registry_path": FIXTURE}))


def mock_llm(settings, answer=lambda body: fake_completion(body["messages"])):
    """LLMClient gegen einen Mock-Transport; answer(body) liefert den Inhalt der Antwort."""
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        requests.append(body)
        return httpx.Response(200, json=completion(answer(body), body["model"]))

    return LLMClient(settings, transport=httpx.MockTransport(handler)), requests


def job(affair_id=7, language="de"):
    return Job(affair_id, "classify:aps", 1, 1, TEXT, "h", language)


async def verified(text, evidences):
    return [True] * len(evidences)


async def unverified(text, evidences):
    return [False] * len(evidences)


async def nothing():
    return None


async def test_two_stages_offer_only_the_topics_of_the_chosen_chapter(settings, classifier):
    client, requests = mock_llm(settings)
    async with client:
        result, reasons = await classify_affair(
            classifier, client, job(), threshold=0.6, verify=verified, escalate=nothing
        )
    assert reasons == []
    (only,) = result.passes
    assert (only.stage, only.model_version) == ("8b", "test-8b")
    assert [(label.tag_id, label.confidence) for label in only.labels] == [("aps:2.4.1", 0.9)]
    assert result.summary_de == "Geschäft 7 (Mock)."
    assert result.prompt_version.startswith("classify_chapters_v1+")
    assert len(requests) == 2
    stage2 = requests[1]["messages"][0]["content"]
    assert "aps:2.4.1 |" in stage2
    assert "adhoc:digitalisierung-breit |" in stage2
    assert "aps:6.1.9 |" not in stage2


async def test_invalid_json_is_retried_once_with_a_hint(settings, classifier):
    answers = iter(["kein JSON"])
    client, requests = mock_llm(
        settings, lambda body: next(answers, None) or fake_completion(body["messages"])
    )
    async with client:
        result, reasons = await classify_affair(
            classifier, client, job(), threshold=0.6, verify=verified, escalate=nothing
        )
    assert reasons == []
    assert [label.tag_id for label in result.passes[-1].labels] == ["aps:2.4.1"]
    assert len(requests) == 3
    assert requests[1]["messages"][-2] == {"role": "assistant", "content": "kein JSON"}
    assert "ungültig" in requests[1]["messages"][-1]["content"]


async def test_invalid_output_goes_to_70b_and_then_fails(settings, classifier):
    client, requests = mock_llm(settings, lambda body: "kein JSON")
    escalations = []

    async def escalate():
        escalations.append(True)

    async with client:
        with pytest.raises(OutputFailure):
            await classify_affair(
                classifier, client, job(), threshold=0.6, verify=verified, escalate=escalate
            )
    assert escalations == [True]
    assert [body["model"] for body in requests] == ["test-8b", "test-8b", "test-70b", "test-70b"]


async def test_invalid_70b_keeps_the_valid_8b_result(settings, classifier):
    def answer(body):
        return "kein JSON" if body["model"] == "test-70b" else fake_completion(body["messages"])

    client, requests = mock_llm(settings, answer)
    async with client:
        result, reasons = await classify_affair(
            classifier, client, job(affair_id=100), threshold=0.6, verify=verified, escalate=nothing
        )
    assert reasons == ["stichprobe", "70b_ungueltig"]
    (only,) = result.passes
    assert only.stage == "8b"
    assert [label.tag_id for label in only.labels] == ["aps:2.4.1"]
    assert [body["model"] for body in requests][-2:] == ["test-70b", "test-70b"]


async def test_a_slow_job_does_not_block_free_slots():
    """Job 1 wartet, bis Job 4 fertig ist; mit Stapeln zu 2 Jobs bliebe das hängen."""
    open_jobs = [job(affair_id=i) for i in range(1, 6)]
    fourth_done = asyncio.Event()
    finished: list[int] = []

    async def claim_jobs(n):
        taken, open_jobs[:] = open_jobs[:n], open_jobs[n:]
        return taken

    async def process(j):
        if j.affair_id == 1:
            await fourth_done.wait()
        finished.append(j.affair_id)
        if j.affair_id == 4:
            fourth_done.set()

    await asyncio.wait_for(fill_slots(claim_jobs, process, 2, once=True), timeout=2)
    assert finished == [2, 3, 4, 1, 5]


def changing_8b(change):
    """Mock, dessen 8B-Antwort in Stufe 2 von change verändert wird."""

    def answer(body):
        data = json.loads(fake_completion(body["messages"]))
        if change and "tags" in data and body["model"] == "test-8b":
            change(data)
        return json.dumps(data)

    return answer


def low_confidence(data):
    data["tags"][0]["confidence"] = 0.3


def with_proposal(data):
    data["proposed_tags"] = [{"name_de": "Neu", "description_de": "d", "reason": "fehlt"}]


@pytest.mark.parametrize(
    ("change", "job_args", "verify", "reason"),
    [
        (low_confidence, {}, verified, "konfidenz"),
        (with_proposal, {}, verified, "vorschlag"),
        (None, {"language": "other"}, verified, "sprache"),
        (None, {"affair_id": 100}, verified, "stichprobe"),
        (None, {}, unverified, "konfidenz"),
    ],
)
async def test_escalation_rules(settings, classifier, change, job_args, verify, reason):
    client, _ = mock_llm(settings, changing_8b(change))
    async with client:
        result, reasons = await classify_affair(
            classifier, client, job(**job_args), threshold=0.6, verify=verify, escalate=nothing
        )
    assert reasons == [reason]
    first, final = result.passes
    assert (first.stage, final.stage, final.model_version) == ("8b", "70b", "test-70b")
    if verify is unverified:
        assert (first.labels[0].confidence, first.labels[0].evidence_verified) == (0.45, False)
