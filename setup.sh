#!/usr/bin/env bash
# Setup do Transcritor Local (modo sem Docker): venv + dependências + verificações.
set -euo pipefail
cd "$(dirname "$0")"

echo "== Transcritor Local — setup =="

# 1) Python
if ! command -v python3 >/dev/null; then
  echo "ERRO: python3 não encontrado. Instale Python 3.10+ e rode de novo."; exit 1
fi
echo "-> Criando venv em .venv/"
python3 -m venv .venv
source .venv/bin/activate

echo "-> Instalando a lib whisper (este repositório) e o backend"
pip install --quiet --upgrade pip
pip install --quiet -e .
pip install --quiet -r app/backend/requirements.txt

# 2) Frontend
if command -v npm >/dev/null; then
  echo "-> Instalando dependências do frontend"
  (cd app/frontend && npm install --silent)
else
  echo "AVISO: npm não encontrado — instale Node.js 18+ para rodar o frontend."
fi

# 3) ffmpeg
if command -v ffmpeg >/dev/null; then
  echo "-> ffmpeg OK: $(ffmpeg -version | head -1)"
else
  echo "AVISO: ffmpeg não encontrado — a transcrição NÃO funcionará sem ele."
  echo "       Ubuntu/Debian: sudo apt install ffmpeg | macOS: brew install ffmpeg"
fi

# 4) Ollama
if curl -s --max-time 2 "${OLLAMA_URL:-http://localhost:11434}/api/tags" >/dev/null 2>&1; then
  echo "-> Ollama OK"
else
  echo "AVISO: Ollama não está rodando — os recursos de IA ficarão desativados."
  echo "       Instale em https://ollama.com, rode 'ollama serve' e 'ollama pull llama3.1:8b'."
fi

# 5) .env
if [ ! -f .env ]; then
  cp .env.example .env
  echo "-> .env criado a partir do .env.example"
fi

cat <<FIM

== Pronto! Para iniciar ==
Terminal 1 (backend):
  source .venv/bin/activate
  python -m uvicorn app.backend.main:app --port 8000

Terminal 2 (frontend):
  cd app/frontend && npm run dev

Depois abra http://localhost:5173
FIM
