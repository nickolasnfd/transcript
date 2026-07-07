"""Configuração do app — lê variáveis do ambiente e de um arquivo .env."""

import os
from dataclasses import dataclass, field
from pathlib import Path

# Raiz do repositório (dois níveis acima de app/backend/)
REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _load_dotenv(path: Path) -> None:
    """Carrega um .env simples (KEY=VALUE) sem dependências externas.

    Variáveis já definidas no ambiente têm precedência sobre o .env.
    """
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip("'\"")
        os.environ.setdefault(key, value)


def _resolve_device(device: str) -> str:
    """Resolve DEVICE=auto para cuda/cpu conforme o hardware disponível."""
    if device != "auto":
        return device
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


@dataclass
class Settings:
    whisper_model: str = "turbo"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    data_dir: Path = field(default_factory=lambda: REPO_ROOT / "data")
    port: int = 8000
    device: str = "auto"

    @property
    def resolved_device(self) -> str:
        return _resolve_device(self.device)

    @property
    def db_path(self) -> Path:
        return self.data_dir / "app.db"

    @property
    def audio_dir(self) -> Path:
        return self.data_dir / "audio"

    @property
    def exports_dir(self) -> Path:
        return self.data_dir / "exports"

    def ensure_dirs(self) -> None:
        self.audio_dir.mkdir(parents=True, exist_ok=True)
        self.exports_dir.mkdir(parents=True, exist_ok=True)


def load_settings() -> Settings:
    _load_dotenv(REPO_ROOT / ".env")
    data_dir = Path(os.environ.get("DATA_DIR", str(REPO_ROOT / "data")))
    if not data_dir.is_absolute():
        data_dir = (REPO_ROOT / data_dir).resolve()
    return Settings(
        whisper_model=os.environ.get("WHISPER_MODEL", "turbo"),
        ollama_url=os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/"),
        ollama_model=os.environ.get("OLLAMA_MODEL", "llama3.1:8b"),
        data_dir=data_dir,
        port=int(os.environ.get("PORT", "8000")),
        device=os.environ.get("DEVICE", "auto"),
    )


settings = load_settings()
