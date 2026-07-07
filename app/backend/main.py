"""FastAPI app + rotas do app de transcrição local."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import health
from .config import settings
from .db import init_db
from .models import HealthStatus


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.ensure_dirs()
    init_db()
    yield


app = FastAPI(title="Transcritor Local (Whisper + Ollama)", lifespan=lifespan)

# Frontend dev server (Vite) roda em outra porta em localhost
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthStatus)
async def get_health():
    ffmpeg = health.check_ffmpeg()
    ollama = await health.check_ollama()
    gpu = health.check_gpu()
    return HealthStatus(
        ok=ffmpeg["ok"],  # transcrição exige ffmpeg; Ollama é opcional
        ffmpeg=ffmpeg,
        ollama=ollama,
        gpu=gpu,
        whisper_model=settings.whisper_model,
        ollama_model=settings.ollama_model,
    )
