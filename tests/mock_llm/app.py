"""OpenAI-kompatibler Mock für Tests und den Offline-Test (AIRGAP.md 4).

Kein Modell, immer dieselbe Antwort.
"""

import time

from fastapi import FastAPI, Request

app = FastAPI(title="Mock-LLM")


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
    return {
        "id": "mock-1",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": body.get("model", "mock"),
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": "OK"}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 1, "total_tokens": 1},
    }
