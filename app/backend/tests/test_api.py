"""Testes do backend: health, upload+transcrição (backend fake), busca, export e LLM mockado."""

import json

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """App com DATA_DIR isolado e Transcriber fake (sem baixar modelos)."""
    from app.backend import config

    monkeypatch.setattr(config.settings, "data_dir", tmp_path)
    config.settings.ensure_dirs()

    from app.backend import main
    from app.backend.db import init_db
    from app.backend.transcription import jobs
    from app.backend.transcription.base import (
        Transcriber,
        TranscriptResult,
        TranscriptSegment,
    )

    init_db()

    class FakeTranscriber(Transcriber):
        def transcribe(self, audio_path, model_name, language=None, on_progress=None):
            if on_progress:
                on_progress(0.5)
                on_progress(1.0)
            return TranscriptResult(
                text="olá mundo isto é um teste",
                language=language or "pt",
                duration=1.5,
                segments=[
                    TranscriptSegment(
                        id=0, start=0.0, end=1.5, text="olá mundo isto é um teste"
                    )
                ],
            )

    monkeypatch.setattr(jobs, "transcriber", FakeTranscriber())

    with TestClient(main.app) as c:
        yield c


def _upload_and_wait(client, filename="exemplo.wav") -> int:
    """Sobe um wav mínimo e espera o job concluir via WebSocket."""
    wav_header = (
        b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"
        b"\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
    )
    resp = client.post(
        "/api/transcriptions",
        files={"file": (filename, wav_header, "audio/wav")},
        data={"model": "tiny", "language": "pt"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    with client.websocket_connect(f"/ws/jobs/{body['job_id']}") as ws:
        for _ in range(50):
            snap = ws.receive_json()
            if snap["status"] in ("done", "error"):
                assert snap["status"] == "done", snap
                break
    return body["transcription_id"]


def test_health(client):
    data = client.get("/api/health").json()
    assert {"ok", "ffmpeg", "ollama", "gpu"} <= data.keys()


def test_upload_transcribe_and_detail(client):
    tid = _upload_and_wait(client)
    detail = client.get(f"/api/transcriptions/{tid}").json()
    assert detail["status"] == "done"
    assert detail["text"] == "olá mundo isto é um teste"
    assert detail["language"] == "pt"
    assert len(detail["segments"]) == 1


def test_invalid_format_rejected(client):
    resp = client.post(
        "/api/transcriptions",
        files={"file": ("nota.xyz", b"abc", "application/octet-stream")},
    )
    assert resp.status_code == 422


def test_search_fulltext(client):
    tid = _upload_and_wait(client)
    hits = client.get("/api/transcriptions", params={"q": "mundo"}).json()
    assert any(t["id"] == tid for t in hits)
    assert client.get("/api/transcriptions", params={"q": "inexistente"}).json() == []


def test_export_formats(client):
    tid = _upload_and_wait(client)
    for fmt in ("txt", "srt", "vtt", "json"):
        resp = client.get(f"/api/transcriptions/{tid}/export", params={"format": fmt})
        assert resp.status_code == 200, fmt
        # o writer JSON do whisper escapa unicode (ensure_ascii)
        content = json.loads(resp.text)["text"] if fmt == "json" else resp.text
        assert "olá mundo" in content
    srt = client.get(f"/api/transcriptions/{tid}/export", params={"format": "srt"}).text
    assert "00:00:00,000 --> 00:00:01,500" in srt


def test_delete_removes_files(client):
    from app.backend.config import settings

    tid = _upload_and_wait(client)
    audio_files = list(settings.audio_dir.iterdir())
    assert audio_files
    assert client.delete(f"/api/transcriptions/{tid}").status_code == 204
    assert client.get(f"/api/transcriptions/{tid}").status_code == 404
    assert not list(settings.audio_dir.iterdir())


def test_llm_summary_with_mocked_ollama(client, monkeypatch):
    """Ação de LLM com o cliente do Ollama substituído por um fake."""
    from app.backend.llm import actions

    async def fake_chat_stream(messages, model=None):
        for token in ["Resumo: ", "conteúdo ", "de ", "teste."]:
            yield token

    monkeypatch.setattr(actions, "chat_stream", fake_chat_stream)

    tid = _upload_and_wait(client)
    resp = client.post(f"/api/transcriptions/{tid}/summary", json={})
    assert resp.status_code == 200
    assert resp.text == "Resumo: conteúdo de teste."

    # resultado persistido
    saved = client.get(f"/api/transcriptions/{tid}/llm-results").json()["results"]
    assert saved["summary"]["output"] == "Resumo: conteúdo de teste."


def test_llm_offline_returns_clear_error(client, monkeypatch):
    from app.backend.llm import actions
    from app.backend.llm.ollama_client import OllamaOfflineError

    async def offline_stream(messages, model=None):
        raise OllamaOfflineError("connection refused")
        yield  # pragma: no cover

    monkeypatch.setattr(actions, "chat_stream", offline_stream)

    tid = _upload_and_wait(client)
    resp = client.post(f"/api/transcriptions/{tid}/summary", json={})
    assert resp.status_code == 200
    assert "[ERRO]" in resp.text


def test_chat_persists_history(client, monkeypatch):
    from app.backend.llm import actions

    async def fake_chat_stream(messages, model=None):
        yield f"eco:{len(messages)}"

    monkeypatch.setattr(actions, "chat_stream", fake_chat_stream)

    tid = _upload_and_wait(client)
    r1 = client.post(f"/api/transcriptions/{tid}/chat", json={"message": "primeira?"})
    # system + pergunta = 2 mensagens
    assert r1.text == "eco:2"
    r2 = client.post(f"/api/transcriptions/{tid}/chat", json={"message": "segunda?"})
    # system + histórico (2) + pergunta = 4
    assert r2.text == "eco:4"
    history = client.get(f"/api/transcriptions/{tid}/chat").json()["messages"]
    assert [m["role"] for m in history] == ["user", "assistant", "user", "assistant"]
