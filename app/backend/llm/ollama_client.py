"""Cliente HTTP do Ollama com respostas em streaming."""

import json
from typing import AsyncIterator

import httpx

from ..config import settings


class OllamaOfflineError(Exception):
    """Ollama não está acessível — recursos de LLM ficam indisponíveis."""


async def list_models() -> list[str]:
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{settings.ollama_url}/api/tags")
            resp.raise_for_status()
            return [m["name"] for m in resp.json().get("models", [])]
    except (httpx.HTTPError, OSError) as exc:
        raise OllamaOfflineError(str(exc)) from exc


async def chat_stream(
    messages: list[dict], model: str | None = None
) -> AsyncIterator[str]:
    """Envia mensagens ao /api/chat do Ollama e emite os tokens da resposta."""
    payload = {
        "model": model or settings.ollama_model,
        "messages": messages,
        "stream": True,
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(300, connect=5)) as client:
            async with client.stream(
                "POST", f"{settings.ollama_url}/api/chat", json=payload
            ) as resp:
                if resp.status_code != 200:
                    body = (await resp.aread()).decode(errors="replace")
                    raise OllamaOfflineError(
                        f"Ollama respondeu {resp.status_code}: {body[:300]}"
                    )
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    if data.get("error"):
                        raise OllamaOfflineError(data["error"])
                    token = data.get("message", {}).get("content", "")
                    if token:
                        yield token
                    if data.get("done"):
                        return
    except (httpx.HTTPError, OSError) as exc:
        raise OllamaOfflineError(
            f"Ollama indisponível em {settings.ollama_url}: {exc}"
        ) from exc
