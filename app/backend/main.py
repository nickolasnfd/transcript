"""FastAPI app + rotas do app de transcrição local."""

import json
import re
import unicodedata
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from . import health
from .config import settings
from .db import get_conn, init_db
from .export.writers import SUPPORTED_FORMATS, export_transcript
from .llm import actions as llm_actions
from .llm.ollama_client import OllamaOfflineError, list_models
from .models import (
    ChatRequest,
    HealthStatus,
    JobCreated,
    LLMRequest,
    Segment,
    TranscriptionDetail,
    TranscriptionSummary,
)
from .transcription.jobs import job_manager

ALLOWED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".mp4", ".webm"}
VALID_MODELS = {"tiny", "base", "small", "medium", "large", "turbo"}


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


def _safe_filename(name: str) -> str:
    base = unicodedata.normalize("NFKD", Path(name).name)
    base = re.sub(r"[^\w.\-]+", "_", base)
    return base or "audio"


def _row_to_detail(row) -> TranscriptionDetail:
    segments = [Segment(**s) for s in json.loads(row["segments_json"] or "[]")]
    return TranscriptionDetail(
        id=row["id"],
        filename=row["filename"],
        created_at=row["created_at"],
        duration=row["duration"],
        language=row["language"],
        model=row["model"],
        status=row["status"],
        text=row["text"],
        error=row["error"],
        segments=segments,
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


@app.post("/api/transcriptions", response_model=JobCreated)
async def create_transcription(
    file: UploadFile = File(...),
    model: str = Form(default=None),
    language: str = Form(default=None),
):
    model = model or settings.whisper_model
    # Aceita nomes conhecidos ou um caminho para checkpoint .pt (modelos fine-tunados)
    is_checkpoint = model.endswith(".pt") and Path(model).is_file()
    if model not in VALID_MODELS and not is_checkpoint:
        raise HTTPException(422, f"Modelo inválido: {model}. Use um de {sorted(VALID_MODELS)}")

    filename = _safe_filename(file.filename or "audio")
    if Path(filename).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            422,
            f"Formato não suportado: {Path(filename).suffix or '(sem extensão)'}. "
            f"Aceitos: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    dest = settings.audio_dir / f"{uuid.uuid4().hex[:8]}_{filename}"
    with dest.open("wb") as out:
        while chunk := await file.read(1024 * 1024):
            out.write(chunk)

    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO transcriptions (filename, filepath, model, language, status)"
            " VALUES (?, ?, ?, ?, 'queued')",
            (filename, str(dest), model, language),
        )
        transcription_id = cur.lastrowid

    job = job_manager.enqueue(transcription_id, str(dest), model, language)
    return JobCreated(job_id=job.job_id, transcription_id=transcription_id)


@app.get("/api/transcriptions", response_model=list[TranscriptionSummary])
async def list_transcriptions(q: str | None = Query(default=None)):
    with get_conn() as conn:
        if q:
            rows = conn.execute(
                """
                SELECT t.id, t.filename, t.created_at, t.duration, t.language,
                       t.model, t.status
                FROM transcriptions_fts f
                JOIN transcriptions t ON t.id = f.rowid
                WHERE transcriptions_fts MATCH ?
                ORDER BY rank
                """,
                (q,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, filename, created_at, duration, language, model, status"
                " FROM transcriptions ORDER BY id DESC"
            ).fetchall()
    return [TranscriptionSummary(**dict(row)) for row in rows]


@app.get("/api/transcriptions/{transcription_id}", response_model=TranscriptionDetail)
async def get_transcription(transcription_id: int):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM transcriptions WHERE id = ?", (transcription_id,)
        ).fetchone()
    if row is None:
        raise HTTPException(404, "Transcrição não encontrada")
    return _row_to_detail(row)


@app.delete("/api/transcriptions/{transcription_id}", status_code=204)
async def delete_transcription(transcription_id: int):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT filepath, filename FROM transcriptions WHERE id = ?",
            (transcription_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(404, "Transcrição não encontrada")
        conn.execute("DELETE FROM transcriptions WHERE id = ?", (transcription_id,))

    # Remove o áudio e quaisquer exports gerados
    Path(row["filepath"]).unlink(missing_ok=True)
    stem = Path(row["filepath"]).stem
    for export in settings.exports_dir.glob(f"{stem}.*"):
        export.unlink(missing_ok=True)
    return Response(status_code=204)


@app.get("/api/transcriptions/{transcription_id}/export")
async def export_transcription(transcription_id: int, format: str = Query(...)):
    if format not in SUPPORTED_FORMATS:
        raise HTTPException(422, f"Formato inválido. Use: {', '.join(SUPPORTED_FORMATS)}")
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM transcriptions WHERE id = ?", (transcription_id,)
        ).fetchone()
    if row is None:
        raise HTTPException(404, "Transcrição não encontrada")
    if row["status"] != "done":
        raise HTTPException(409, "Transcrição ainda não concluída")

    content, media_type = export_transcript(
        row["text"] or "", row["segments_json"], row["language"], format
    )
    out_name = f"{Path(row['filename']).stem}.{format}"
    return Response(
        content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{out_name}"'},
    )


@app.get("/api/transcriptions/{transcription_id}/audio")
async def get_audio(transcription_id: int):
    """Serve o arquivo de áudio para o player do frontend."""
    from fastapi.responses import FileResponse

    with get_conn() as conn:
        row = conn.execute(
            "SELECT filepath, filename FROM transcriptions WHERE id = ?",
            (transcription_id,),
        ).fetchone()
    if row is None or not Path(row["filepath"]).is_file():
        raise HTTPException(404, "Áudio não encontrado")
    return FileResponse(row["filepath"], filename=row["filename"])


# ---------------------------------------------------------------------------
# LLM (Ollama)
# ---------------------------------------------------------------------------

def _get_transcript_text(transcription_id: int) -> str:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT text, status FROM transcriptions WHERE id = ?",
            (transcription_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(404, "Transcrição não encontrada")
    if row["status"] != "done" or not row["text"]:
        raise HTTPException(409, "Transcrição ainda não concluída")
    return row["text"]


def _save_llm_result(transcription_id: int, action: str, model: str | None, output: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO llm_results (transcription_id, action, model, output)"
            " VALUES (?, ?, ?, ?)",
            (transcription_id, action, model or settings.ollama_model, output),
        )


def _llm_streaming_response(transcription_id: int, action: str, req: LLMRequest):
    """Cria uma StreamingResponse para uma ação de template único."""
    from fastapi.responses import StreamingResponse

    text = _get_transcript_text(transcription_id)

    async def generate():
        collected: list[str] = []
        try:
            async for token in llm_actions.run_action(action, text, req.model):
                collected.append(token)
                yield token
        except OllamaOfflineError as exc:
            yield f"\n[ERRO] {exc}"
            return
        _save_llm_result(transcription_id, action, req.model, "".join(collected))

    return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")


@app.get("/api/ollama/models")
async def get_ollama_models():
    try:
        return {"models": await list_models()}
    except OllamaOfflineError as exc:
        raise HTTPException(503, f"Ollama indisponível: {exc}")


@app.post("/api/transcriptions/{transcription_id}/summary")
async def llm_summary(transcription_id: int, req: LLMRequest = LLMRequest()):
    return _llm_streaming_response(transcription_id, "summary", req)


@app.post("/api/transcriptions/{transcription_id}/clean")
async def llm_clean(transcription_id: int, req: LLMRequest = LLMRequest()):
    return _llm_streaming_response(transcription_id, "clean", req)


@app.post("/api/transcriptions/{transcription_id}/action-items")
async def llm_action_items(transcription_id: int, req: LLMRequest = LLMRequest()):
    return _llm_streaming_response(transcription_id, "action_items", req)


@app.post("/api/transcriptions/{transcription_id}/chat")
async def llm_chat(transcription_id: int, req: ChatRequest):
    from fastapi.responses import StreamingResponse

    text = _get_transcript_text(transcription_id)
    with get_conn() as conn:
        history = [
            {"role": r["role"], "content": r["content"]}
            for r in conn.execute(
                "SELECT role, content FROM chat_messages"
                " WHERE transcription_id = ? ORDER BY id",
                (transcription_id,),
            )
        ]

    async def generate():
        collected: list[str] = []
        try:
            async for token in llm_actions.run_chat(text, history, req.message, req.model):
                collected.append(token)
                yield token
        except OllamaOfflineError as exc:
            yield f"\n[ERRO] {exc}"
            return
        answer = "".join(collected)
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO chat_messages (transcription_id, role, content) VALUES (?, 'user', ?)",
                (transcription_id, req.message),
            )
            conn.execute(
                "INSERT INTO chat_messages (transcription_id, role, content) VALUES (?, 'assistant', ?)",
                (transcription_id, answer),
            )

    return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")


@app.get("/api/transcriptions/{transcription_id}/chat")
async def get_chat_history(transcription_id: int):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT role, content, created_at FROM chat_messages"
            " WHERE transcription_id = ? ORDER BY id",
            (transcription_id,),
        ).fetchall()
    return {"messages": [dict(r) for r in rows]}


@app.get("/api/transcriptions/{transcription_id}/llm-results")
async def get_llm_results(transcription_id: int):
    """Últimos resultados salvos de cada ação (para reabrir transcripts antigos)."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT action, model, output, created_at FROM llm_results
            WHERE id IN (
                SELECT MAX(id) FROM llm_results
                WHERE transcription_id = ? GROUP BY action
            )
            """,
            (transcription_id,),
        ).fetchall()
    return {"results": {r["action"]: dict(r) for r in rows}}


@app.websocket("/ws/jobs/{job_id}")
async def job_progress(websocket: WebSocket, job_id: str):
    await websocket.accept()
    job = job_manager.get(job_id)
    if job is None:
        await websocket.send_json({"error": "job não encontrado"})
        await websocket.close()
        return
    try:
        async for snapshot in job_manager.watch(job_id):
            await websocket.send_json(snapshot)
    finally:
        await websocket.close()
