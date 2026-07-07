"""Implementação do Transcriber usando a lib openai-whisper deste repositório."""

import threading
from typing import Optional
from unittest import mock

import tqdm as _tqdm

from ..config import settings
from .base import ProgressCallback, Transcriber, TranscriptResult, TranscriptSegment


def _make_progress_tqdm(on_progress: ProgressCallback):
    """Cria uma subclasse de tqdm que reporta a fração concluída via callback.

    O whisper.transcribe usa tqdm(total=content_frames) e chama update() a cada
    janela de 30s processada — é a fonte de progresso mais fiel disponível.
    """

    class _ProgressTqdm(_tqdm.tqdm):
        def update(self, n=1):
            result = super().update(n)
            if self.total:
                on_progress(min(self.n / self.total, 1.0))
            return result

    return _ProgressTqdm


class WhisperBackend(Transcriber):
    """Carrega cada modelo Whisper uma única vez e o mantém em cache."""

    def __init__(self) -> None:
        self._models: dict[str, object] = {}
        self._lock = threading.Lock()

    def _get_model(self, model_name: str):
        with self._lock:
            if model_name not in self._models:
                import whisper

                self._models[model_name] = whisper.load_model(
                    model_name, device=settings.resolved_device
                )
            return self._models[model_name]

    def transcribe(
        self,
        audio_path: str,
        model_name: str,
        language: Optional[str] = None,
        on_progress: Optional[ProgressCallback] = None,
    ) -> TranscriptResult:
        model = self._get_model(model_name)

        kwargs: dict = {"verbose": False}
        if language:
            kwargs["language"] = language
        # fp16 só faz sentido em GPU; em CPU o próprio whisper avisa e desliga
        if settings.resolved_device == "cpu":
            kwargs["fp16"] = False

        if on_progress is not None:
            # Jobs rodam serializados (1 worker), então o patch não conflita.
            patched = _make_progress_tqdm(on_progress)
            with mock.patch("whisper.transcribe.tqdm.tqdm", patched):
                raw = model.transcribe(audio_path, **kwargs)
        else:
            raw = model.transcribe(audio_path, **kwargs)

        segments = [
            TranscriptSegment(
                id=s["id"], start=s["start"], end=s["end"], text=s["text"].strip()
            )
            for s in raw.get("segments", [])
        ]
        duration = segments[-1].end if segments else None
        return TranscriptResult(
            text=raw.get("text", "").strip(),
            language=raw.get("language"),
            duration=duration,
            segments=segments,
        )


# Instância única compartilhada pelo app
transcriber = WhisperBackend()
