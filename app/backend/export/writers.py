"""Export de transcrições reutilizando os writers de whisper/utils.py."""

import io
import json

from whisper.utils import WriteJSON, WriteSRT, WriteTXT, WriteVTT

_WRITERS = {
    "txt": (WriteTXT, "text/plain"),
    "srt": (WriteSRT, "application/x-subrip"),
    "vtt": (WriteVTT, "text/vtt"),
    "json": (WriteJSON, "application/json"),
}

SUPPORTED_FORMATS = tuple(_WRITERS)


def export_transcript(
    text: str, segments_json: str, language: str | None, fmt: str
) -> tuple[str, str]:
    """Gera o conteúdo exportado em memória. Retorna (conteúdo, media_type)."""
    if fmt not in _WRITERS:
        raise ValueError(f"Formato não suportado: {fmt}")
    writer_cls, media_type = _WRITERS[fmt]
    result = {
        "text": text,
        "language": language,
        "segments": json.loads(segments_json or "[]"),
    }
    buffer = io.StringIO()
    # Os SubtitlesWriter aceitam options com max_line_width/max_line_count/highlight_words
    writer = writer_cls.__new__(writer_cls)  # sem output_dir: escrevemos em memória
    writer.write_result(result, file=buffer, options={})
    return buffer.getvalue(), media_type
