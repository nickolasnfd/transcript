"""Ações de LLM sobre um transcript: resumo, limpeza, itens de ação e chat."""

from pathlib import Path
from typing import AsyncIterator

from .ollama_client import chat_stream

PROMPTS_DIR = Path(__file__).parent / "prompts"

# ~24k chars ≈ 6-8k tokens: cabe com folga no contexto padrão dos modelos do Ollama
CHUNK_SIZE = 24_000
CHUNK_PROMPT = (
    "O texto a seguir é a PARTE {part} de {total} de uma transcrição longa. "
    "Processe apenas esta parte seguindo as mesmas instruções.\n\n{chunk}"
)


def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.txt").read_text(encoding="utf-8")


def _chunks(text: str, size: int = CHUNK_SIZE) -> list[str]:
    """Divide o texto em pedaços, preferindo quebrar em fim de parágrafo/frase."""
    if len(text) <= size:
        return [text]
    parts, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            # tenta quebrar num limite natural olhando os últimos 2k chars da janela
            window = text[start:end]
            cut = max(window.rfind("\n\n"), window.rfind(". "))
            if cut > size - 2000:
                end = start + cut + 1
        parts.append(text[start:end])
        start = end
    return parts


async def run_action(
    action: str, transcript: str, model: str | None = None
) -> AsyncIterator[str]:
    """Executa uma ação de template único (summary, clean, action_items) em streaming.

    Transcripts longos são processados em partes, com um separador entre elas.
    """
    template = load_prompt(action)
    parts = _chunks(transcript)
    total = len(parts)
    for i, part in enumerate(parts, start=1):
        content = part if total == 1 else CHUNK_PROMPT.format(part=i, total=total, chunk=part)
        prompt = template.replace("{transcript}", content)
        if total > 1 and i > 1:
            yield f"\n\n---\n*Parte {i} de {total}*\n\n"
        async for token in chat_stream([{"role": "user", "content": prompt}], model):
            yield token


async def run_chat(
    transcript: str,
    history: list[dict],
    question: str,
    model: str | None = None,
) -> AsyncIterator[str]:
    """Q&A sobre o transcript, com histórico da conversa no contexto."""
    # Para o chat, transcripts muito longos são truncados com aviso no system prompt
    # (as ações de resumo/limpeza usam chunking; para Q&A o começo+fim costuma bastar).
    context = transcript
    if len(transcript) > CHUNK_SIZE:
        head = transcript[: CHUNK_SIZE // 2]
        tail = transcript[-CHUNK_SIZE // 2 :]
        context = f"{head}\n\n[... trecho central omitido por limite de contexto ...]\n\n{tail}"

    system = load_prompt("chat_system").replace("{transcript}", context)
    messages = [{"role": "system", "content": system}, *history, {"role": "user", "content": question}]
    async for token in chat_stream(messages, model):
        yield token
