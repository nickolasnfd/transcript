"""Verificação das dependências externas: ffmpeg, Ollama e GPU."""

import shutil
import subprocess
from typing import Any

import httpx

from .config import settings


def check_ffmpeg() -> dict[str, Any]:
    path = shutil.which("ffmpeg")
    if not path:
        return {"ok": False, "detail": "ffmpeg não encontrado no PATH"}
    try:
        out = subprocess.run(
            ["ffmpeg", "-version"], capture_output=True, text=True, timeout=10
        )
        version = out.stdout.splitlines()[0] if out.stdout else ""
        return {"ok": out.returncode == 0, "detail": version}
    except Exception as exc:  # pragma: no cover - falha rara
        return {"ok": False, "detail": str(exc)}


async def check_ollama() -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.get(f"{settings.ollama_url}/api/tags")
            resp.raise_for_status()
            models = [m.get("name") for m in resp.json().get("models", [])]
            return {"ok": True, "models": models}
    except Exception as exc:
        return {
            "ok": False,
            "models": [],
            "detail": f"Ollama indisponível em {settings.ollama_url}: {exc}",
        }


def check_gpu() -> dict[str, Any]:
    try:
        import torch

        available = torch.cuda.is_available()
        name = torch.cuda.get_device_name(0) if available else None
        return {
            "ok": True,
            "cuda": available,
            "device": settings.resolved_device,
            "name": name,
        }
    except Exception as exc:
        return {"ok": False, "cuda": False, "device": "cpu", "detail": str(exc)}
