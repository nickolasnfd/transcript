"""Schemas Pydantic da API."""

from typing import Any, Optional

from pydantic import BaseModel


class HealthStatus(BaseModel):
    ok: bool
    ffmpeg: dict[str, Any]
    ollama: dict[str, Any]
    gpu: dict[str, Any]
    whisper_model: str
    ollama_model: str


class TranscriptionSummary(BaseModel):
    id: int
    filename: str
    created_at: str
    duration: Optional[float] = None
    language: Optional[str] = None
    model: Optional[str] = None
    status: str


class Segment(BaseModel):
    id: int
    start: float
    end: float
    text: str


class TranscriptionDetail(TranscriptionSummary):
    text: Optional[str] = None
    segments: list[Segment] = []
    error: Optional[str] = None


class JobCreated(BaseModel):
    job_id: str
    transcription_id: int


class ChatRequest(BaseModel):
    message: str
    model: Optional[str] = None


class LLMRequest(BaseModel):
    model: Optional[str] = None
