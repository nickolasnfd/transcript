"""Interface abstrata de transcrição — permite trocar o backend (ex.: faster-whisper)."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class TranscriptSegment:
    id: int
    start: float
    end: float
    text: str


@dataclass
class TranscriptResult:
    text: str
    language: Optional[str]
    duration: Optional[float]
    segments: list[TranscriptSegment] = field(default_factory=list)


# Callback de progresso: recebe fração 0.0–1.0
ProgressCallback = Callable[[float], None]


class Transcriber(ABC):
    """Contrato do backend de STT. Implementações devem cachear o modelo."""

    @abstractmethod
    def transcribe(
        self,
        audio_path: str,
        model_name: str,
        language: Optional[str] = None,
        on_progress: Optional[ProgressCallback] = None,
    ) -> TranscriptResult:
        ...
