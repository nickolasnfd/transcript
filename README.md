# 🎙 Transcritor Local — Whisper + Ollama

Aplicação web **local e offline** de transcrição de áudio para uso pessoal:

- **Transcrição** com o [OpenAI Whisper](https://github.com/openai/whisper) (a lib original está na pasta `whisper/` deste repositório e é usada como dependência, sem modificações — [documentação original](model-card.md)).
- **Recursos de IA** com [Ollama](https://ollama.com) (LLM local e gratuito): resumo, limpeza/pontuação, extração de itens de ação e chat sobre o conteúdo do áudio — tudo com resposta em streaming.
- **Histórico pesquisável** (SQLite + busca full-text), player sincronizado com os segmentos e export em TXT/SRT/VTT/JSON.
- 100% na sua máquina: nenhum áudio ou texto sai do seu computador.

![Fluxo](approach.png)

## Pré-requisitos

| Dependência | Para quê | Instalação |
|---|---|---|
| Python 3.10+ | backend | [python.org](https://python.org) |
| Node.js 18+ | frontend | [nodejs.org](https://nodejs.org) |
| ffmpeg | decodificar áudio | `sudo apt install ffmpeg` / `brew install ffmpeg` |
| Ollama (opcional) | recursos de IA | [ollama.com/download](https://ollama.com/download) |

> Sem GPU funciona (CPU); com GPU NVIDIA (CUDA) a transcrição fica bem mais rápida. O app detecta automaticamente.

## Opção A — Docker (mais simples)

```bash
docker compose up --build -d          # sobe app + Ollama
docker compose exec ollama ollama pull llama3.1:8b   # baixa o modelo de LLM (uma vez)
```

Abra **http://localhost:8000**. Pronto.

- Os pesos do Whisper baixam automaticamente no primeiro uso (ex.: `turbo` ≈ 1,6 GB).
- Modelos e dados ficam em volumes Docker (`app-data`, `whisper-models`, `ollama-models`).
- Para GPU no Ollama, descomente o bloco `deploy` no `docker-compose.yml`.

## Opção B — Sem Docker

```bash
./setup.sh    # cria .venv, instala dependências e verifica ffmpeg/Ollama
```

Depois, em dois terminais:

```bash
# Terminal 1 — backend
source .venv/bin/activate
python -m uvicorn app.backend.main:app --port 8000

# Terminal 2 — frontend (com hot reload)
cd app/frontend && npm run dev
```

Abra **http://localhost:5173**.

Para os recursos de IA (opcional):

```bash
ollama serve              # se não estiver rodando como serviço
ollama pull llama3.1:8b   # modelo padrão (configurável no .env)
```

## Configuração (`.env`)

Copie `.env.example` para `.env` e ajuste se quiser:

| Variável | Padrão | Descrição |
|---|---|---|
| `WHISPER_MODEL` | `turbo` | `tiny`/`base`/`small`/`medium`/`large`/`turbo` ou caminho de um checkpoint `.pt` fine-tunado |
| `OLLAMA_URL` | `http://localhost:11434` | endereço da API do Ollama |
| `OLLAMA_MODEL` | `llama3.1:8b` | modelo de LLM padrão |
| `DATA_DIR` | `./data` | onde ficam áudios, exports e o banco |
| `PORT` | `8000` | porta do backend |
| `DEVICE` | `auto` | `auto`/`cpu`/`cuda` |

Qual modelo Whisper escolher? `turbo` é o melhor custo-benefício (rápido e preciso, ~6 GB VRAM); em CPU ou máquina modesta use `small` ou `base`. Para **traduzir** para inglês use `medium`/`large` (o `turbo` não traduz).

Os prompts das ações de IA são templates editáveis em `app/backend/llm/prompts/*.txt`.

## Como usar

1. Arraste um arquivo de áudio (mp3, wav, m4a, flac, ogg, mp4) ou clique em **Gravar do microfone**.
2. Acompanhe o progresso; ao concluir, o texto aparece com os segmentos e o player sincronizado (clique num trecho para ouvir).
3. Use as abas de IA: **Resumo**, **Limpeza** (lado a lado com o original), **Itens de ação** e **Chat**.
4. Exporte em TXT/SRT/VTT/JSON, e encontre tudo depois no **Histórico** (com busca no conteúdo).

## Testes

```bash
source .venv/bin/activate
python -m pytest app/backend/tests/ -q
```

Os testes usam um transcritor fake e um Ollama mockado (`app/backend/tests/mock_ollama.py`) — não precisam de GPU nem de rede.

## Troubleshooting

**"ffmpeg ✗" no topo da página** — instale o ffmpeg (`sudo apt install ffmpeg` / `brew install ffmpeg`) e reinicie o backend.

**"Ollama ✗ (recursos de IA desativados)"** — o Ollama não está acessível. Rode `ollama serve`, confirme com `curl http://localhost:11434/api/tags` e verifique `OLLAMA_URL` no `.env`. A transcrição continua funcionando sem ele.

**Transcrição falha com "memória insuficiente"** — o modelo é grande demais para sua RAM/VRAM. Escolha um menor no seletor (ex.: `small`) ou mude `WHISPER_MODEL` no `.env`.

**Primeiro uso demora muito** — é o download dos pesos do Whisper (até ~3 GB no `large`). Ficam em cache (`~/.cache/whisper`) para as próximas.

**Erro ao instalar `tiktoken` no pip** — instale Rust ([rustup.rs](https://rustup.rs)) e `pip install setuptools-rust`.

**Gravação do microfone não aparece** — o navegador só libera o microfone em `localhost` ou HTTPS, e você precisa aceitar a permissão.

**Porta 8000 ocupada** — mude `PORT` no `.env` (e o proxy em `app/frontend/vite.config.ts`).

## Arquitetura

```
app/
  backend/    FastAPI — upload, fila de transcrição (1 worker), WebSocket de
              progresso, export (reusa whisper/utils.py), LLM via Ollama em
              streaming, SQLite com FTS5
  frontend/   React + Vite + TS — upload/gravação, player sincronizado,
              painel de IA com abas, histórico com busca
whisper/      lib original do OpenAI Whisper (intocada, instalada como dependência)
data/         áudios, exports e app.db (fora do git)
```

O backend de transcrição é plugável (`app/backend/transcription/base.py`): para usar [faster-whisper](https://github.com/SYSTRAN/faster-whisper), implemente `Transcriber` numa nova classe e troque a instância em `whisper_backend.py`, sem tocar no resto.

## Licença

MIT (igual ao Whisper original — veja [LICENSE](LICENSE)).
