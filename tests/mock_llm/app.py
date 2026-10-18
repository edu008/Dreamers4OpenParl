"""OpenAI-kompatibler Mock für Tests und den Offline-Test (AIRGAP.md 4).

Kein Modell. Die Klassifikations-Prompts (Stufe 1 und 2) bekommen gültiges JSON mit der ersten
angebotenen ID, der Agent ruft einmal search_affairs auf und zitiert dann den ersten Treffer, alle
anderen Anfragen bekommen die Antwort "OK" (für `parltopics llm check`).
"""

import json
import re
import time

from fastapi import FastAPI, Request

AFFAIR = re.compile(r"Geschäft (\d+):")
CHAPTER = re.compile(r"^(aps:\d+\.\d+) \|", re.MULTILINE)
TOPIC = re.compile(r"^(aps:\d+\.\d+\.\d+|adhoc:[a-z0-9.\-]+) \|", re.MULTILINE)
TEXT = re.compile(r"<<<\n(.*?)\n>>>", re.DOTALL)
SIMILAR = re.compile(r"Ähnlichste bestehende Themen.*?<<<\n(.*?)>>>", re.DOTALL)
ANY_TAG = re.compile(r"^(aps:[\d.]+|adhoc:[a-z0-9.\-]+) \|", re.MULTILINE)
CHILDREN = re.compile(r"Unterseiten.*?<<<\n(.*?)>>>", re.DOTALL)
AFFAIRS = re.compile(r"Geschäfte \(ID.*?<<<\n(.*?)>>>", re.DOTALL)
FIRST_ID = re.compile(r"^(\d+) \|", re.MULTILINE)
FOUND_ID = re.compile(r'"affair_id": (\d+)')
RELEVANCE = (0.9, 0.5)  # Navigationssuche: erste Unterseite, dann die zweite, sonst nichts
TOOL_RESULT = "Ergebnis von"

app = FastAPI(title="Mock-LLM")


def completion(content: str, model: str) -> dict:
    return {
        "id": "mock-1",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 1, "total_tokens": 1},
    }


def agent_step(messages: list[dict]) -> str:
    """Agent: zuerst search_affairs mit der Frage, danach die erste gelieferte ID zitieren."""
    if len(messages) == 2:  # System und Frage: der erste Schritt
        return json.dumps({"action": "search_affairs", "args": {"query": messages[1]["content"]}})
    results = "\n".join(m["content"] for m in messages if m["content"].startswith(TOOL_RESULT))
    found = FOUND_ID.search(results)
    if found is None:
        return json.dumps({"answer": "Keine passenden Geschäfte gefunden.", "cited_ids": []})
    chosen = int(found.group(1))
    answer = f"Geschäft [{chosen}] passt zur Frage (Mock)."
    return json.dumps({"answer": answer, "cited_ids": [chosen]}, ensure_ascii=False)


def fake_completion(messages: list[dict]) -> str:
    """Antwort auf eine Anfrage: JSON nach PRD Anhang B oder "OK"."""
    system = next((m["content"] for m in messages if m["role"] == "system"), "")
    user = next((m["content"] for m in messages if m["role"] == "user"), "")
    if "nur lesende Werkzeuge" in system:  # agent_system_v1, vor «Suchbegriffe» unten
        return agent_step(messages)
    if "Vorschläge für neue Themen" in system:  # proposal_check_v1: erstes ähnliches Tag
        block = SIMILAR.search(user)
        first = ANY_TAG.search(block.group(1)) if block else None
        related = first.group(1) if first else None
        check = {
            "recommendation": "child_of" if related else "new",
            "related_tag": related,
            "name_de": "Mock-Vorschlag",
            "description_de": "Beschreibung (Mock).",
            "reason": "Mock",
        }
        return json.dumps(check)
    if "Themenbaum" in system:  # navigate_v1
        block = CHILDREN.search(user)
        kids = ANY_TAG.findall(block.group(1)) if block else []
        scores = [
            {"page_id": kid, "relevance": RELEVANCE[i] if i < len(RELEVANCE) else 0.0}
            for i, kid in enumerate(kids)
        ]
        step: dict = {"scores": scores}
        if '"filters"' in system:
            step["filters"] = {"year_from": None, "year_to": None, "body_keys": [], "levels": []}
        return json.dumps(step)
    if "Grundlage sind nur die Geschäfte" in system:  # navigate_answer_v1
        block = AFFAIRS.search(user)
        first = FIRST_ID.search(block.group(1)) if block else None
        if first is None:
            return json.dumps({"selected_ids": [], "statements": []})
        chosen = int(first.group(1))
        text = f"Geschäft {chosen} passt zur Frage (Mock)."
        statement = {"text": text, "affair_ids": [chosen], "page_ids": []}
        return json.dumps({"selected_ids": [chosen], "statements": [statement]})
    if "Suchbegriffe" in system:  # adhoc_keywords_v1
        return json.dumps({"de": ["Velo", "Veloweg"], "fr": ["vélo"], "it": ["bicicletta"]})
    affair = AFFAIR.search(user)
    if affair is None:
        return "OK"
    affair_id = int(affair.group(1))
    if '"chapter_id"' in system:
        chapters = [{"chapter_id": c, "confidence": 0.9} for c in CHAPTER.findall(system)[:1]]
        return json.dumps({"affair_id": affair_id, "language": "de", "chapters": chapters})
    text = TEXT.search(user)
    body = text.group(1) if text else ""
    evidence = (body if len(body) <= 120 else body[:120].rsplit(" ", 1)[0]) or "Mock"
    tags = [
        {"tag_id": tag_id, "confidence": 0.9, "evidence": evidence}
        for tag_id in TOPIC.findall(system)[:1]
    ]
    output = {
        "affair_id": affair_id,
        "language": "de",
        "summary_de": f"Geschäft {affair_id} (Mock).",
        "tags": tags,
        "proposed_tags": [],
    }
    return json.dumps(output, ensure_ascii=False)


@app.get("/v1/models")
def models() -> dict:
    return {
        "object": "list",
        "data": [
            {"id": name, "object": "model", "owned_by": "parltopics"}
            for name in ("mock-8b", "mock-70b")
        ],
    }


@app.post("/v1/chat/completions")
async def chat(request: Request) -> dict:
    body = await request.json()
    return completion(fake_completion(body.get("messages", [])), body.get("model", "mock"))
