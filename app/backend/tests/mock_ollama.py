"""Servidor fake do Ollama para testes: /api/tags e /api/chat com streaming NDJSON.

Uso: python -m app.backend.tests.mock_ollama [porta]
"""

import asyncio
import json
import sys

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

app = FastAPI()

FAKE_MODELS = ["llama3.1:8b", "qwen2.5:7b"]


@app.get("/api/tags")
async def tags():
    return {"models": [{"name": m} for m in FAKE_MODELS]}


@app.post("/api/chat")
async def chat(request: Request):
    body = await request.json()
    last_user = next(
        (
            m["content"]
            for m in reversed(body.get("messages", []))
            if m["role"] == "user"
        ),
        "",
    )
    # Resposta determinística que ecoa um trecho do prompt (útil para asserts)
    reply = f"[mock:{body.get('model')}] Resposta simulada para: {last_user[:80]}"

    async def stream():
        for word in reply.split(" "):
            yield json.dumps(
                {"message": {"role": "assistant", "content": word + " "}}
            ) + "\n"
            await asyncio.sleep(0.02)
        yield json.dumps(
            {"message": {"role": "assistant", "content": ""}, "done": True}
        ) + "\n"

    return StreamingResponse(stream(), media_type="application/x-ndjson")


if __name__ == "__main__":
    import uvicorn

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 11434
    uvicorn.run(app, port=port, log_level="warning")
