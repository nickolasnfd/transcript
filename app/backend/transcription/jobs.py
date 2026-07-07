"""Fila de jobs de transcrição com 1 worker em background e progresso observável."""

import asyncio
import json
import logging
import queue
import threading
import uuid
from dataclasses import dataclass, field
from typing import Optional

from ..db import get_conn
from .whisper_backend import transcriber

logger = logging.getLogger(__name__)


@dataclass
class Job:
    job_id: str
    transcription_id: int
    audio_path: str
    model: str
    language: Optional[str]
    status: str = "queued"  # queued | transcribing | done | error
    progress: float = 0.0
    error: Optional[str] = None
    # Evento por job para acordar os WebSockets quando algo muda
    updated: threading.Event = field(default_factory=threading.Event)


class JobManager:
    """Um worker único processa a fila (modelos Whisper não são thread-safe)."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._queue: "queue.Queue[Job]" = queue.Queue()
        self._worker: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def _ensure_worker(self) -> None:
        with self._lock:
            if self._worker is None or not self._worker.is_alive():
                self._worker = threading.Thread(target=self._run, daemon=True)
                self._worker.start()

    def enqueue(
        self,
        transcription_id: int,
        audio_path: str,
        model: str,
        language: Optional[str],
    ) -> Job:
        job = Job(
            job_id=uuid.uuid4().hex,
            transcription_id=transcription_id,
            audio_path=audio_path,
            model=model,
            language=language,
        )
        self._jobs[job.job_id] = job
        self._queue.put(job)
        self._ensure_worker()
        return job

    def get(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def _set(self, job: Job, **changes) -> None:
        for key, value in changes.items():
            setattr(job, key, value)
        job.updated.set()

    def _run(self) -> None:
        while True:
            job = self._queue.get()
            try:
                self._process(job)
            except Exception as exc:  # último recurso; erros já tratados em _process
                logger.exception("job %s falhou", job.job_id)
                self._fail(job, str(exc))
            finally:
                self._queue.task_done()

    def _process(self, job: Job) -> None:
        self._set(job, status="transcribing", progress=0.0)
        self._update_db(job.transcription_id, status="transcribing")

        def on_progress(fraction: float) -> None:
            self._set(job, progress=round(fraction, 4))

        try:
            result = transcriber.transcribe(
                job.audio_path, job.model, job.language, on_progress
            )
        except FileNotFoundError as exc:
            # ffmpeg ausente aparece como FileNotFoundError ao invocar o binário
            self._fail(job, f"ffmpeg não encontrado ou arquivo inválido: {exc}")
            return
        except RuntimeError as exc:
            msg = str(exc)
            if "out of memory" in msg.lower():
                msg = (
                    "Memória insuficiente para este modelo. "
                    "Tente um modelo menor (ex.: small ou base)."
                )
            elif "Failed to load audio" in msg:
                msg = f"Arquivo de áudio inválido ou formato não suportado: {msg}"
            self._fail(job, msg)
            return
        except Exception as exc:
            self._fail(job, str(exc))
            return

        segments = [
            {"id": s.id, "start": s.start, "end": s.end, "text": s.text}
            for s in result.segments
        ]
        self._update_db(
            job.transcription_id,
            status="done",
            text=result.text,
            segments_json=json.dumps(segments, ensure_ascii=False),
            language=result.language,
            duration=result.duration,
        )
        self._set(job, status="done", progress=1.0)

    def _fail(self, job: Job, message: str) -> None:
        self._update_db(job.transcription_id, status="error", error=message)
        self._set(job, status="error", error=message)

    @staticmethod
    def _update_db(transcription_id: int, **fields) -> None:
        keys = ", ".join(f"{k} = ?" for k in fields)
        with get_conn() as conn:
            conn.execute(
                f"UPDATE transcriptions SET {keys} WHERE id = ?",
                (*fields.values(), transcription_id),
            )

    async def watch(self, job_id: str):
        """Gera snapshots do job a cada mudança (para o WebSocket)."""
        job = self._jobs.get(job_id)
        if job is None:
            return
        while True:
            yield {
                "job_id": job.job_id,
                "transcription_id": job.transcription_id,
                "status": job.status,
                "progress": job.progress,
                "error": job.error,
            }
            if job.status in ("done", "error"):
                return
            job.updated.clear()
            # Espera a próxima mudança sem bloquear o event loop
            await asyncio.get_event_loop().run_in_executor(None, job.updated.wait, 1.0)


job_manager = JobManager()
