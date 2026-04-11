# LocalScript — AI-agent for local Lua code generation

A fully local AI agent system that generates Lua code from natural language prompts
(Russian and English). Runs entirely on your own infrastructure with no external API calls.

## Architecture

```
┌────────────┐     ┌──────────────────┐     ┌────────────────┐
│  Browser   │────▶│  FastAPI Backend  │────▶│  Ollama (GPU)  │
│  Chat UI   │     │     :8080         │     │    :11434      │
└────────────┘     └──────┬───┬────────┘     └────────────────┘
                          │   │
                   ┌──────┘   └──────┐
                   ▼                 ▼
            ┌────────────┐    ┌────────────┐
            │ PostgreSQL │    │Qdrant local│
            │   :5432    │    │  (file DB) │
            └────────────┘    └────────────┘
```

**Components:**
- **Backend** — FastAPI app with agent pipeline (RAG + LLM + validation + self-fix loop)
- **Ollama** — local LLM runtime with GPU acceleration
- **PostgreSQL** — chat session and message history storage
- **Qdrant** — vector database for RAG (local file mode, no server needed)

## Model

```
ollama pull qwen2.5-coder:7b-instruct-q4_K_M
```

**Parameters (fixed for evaluation):**

| Parameter     | Value |
|---------------|-------|
| `num_ctx`     | 4096  |
| `num_predict` | 256   |
| `batch`       | 1     |
| `parallel`    | 1     |

**VRAM usage:** ~5 GB peak (well under 8 GB limit).

## Quick Start (without Docker)

### One-command deploy

```bash
./deploy.sh
```

This script automatically:
1. Installs system packages (`lua5.4`, `postgresql`, `curl`)
2. Creates PostgreSQL user and database
3. Installs Ollama and pulls the model
4. Creates Python venv and installs dependencies
5. Runs initialization (DB tables + RAG knowledge indexing)
6. Starts the FastAPI backend on **http://localhost:8080**

To stop all services:
```bash
./stop.sh
```

### Manual step-by-step

```bash
# 1. Install system deps
sudo apt-get install -y lua5.4 postgresql postgresql-contrib curl

# 2. Start and configure PostgreSQL
sudo systemctl start postgresql
sudo -u postgres psql -c "CREATE USER localscript WITH PASSWORD 'localscript';"
sudo -u postgres psql -c "CREATE DATABASE localscript OWNER localscript;"

# 3. Install and start Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama serve &              # start in background
ollama pull qwen2.5-coder:7b-instruct-q4_K_M

# 4. Python environment (uv)
uv venv .venv
uv pip install -r requirements.txt

# 5. Initialize (DB tables + RAG index)
uv run python -m scripts.init

# 6. Start backend
uv run uvicorn app.main:app --host 0.0.0.0 --port 8080
```

Open **http://localhost:8080** in your browser.

### Docker Compose (alternative)

If Docker is available, update `.env` to use Docker service names:

```env
DATABASE_URL=postgresql+asyncpg://localscript:localscript@postgres:5432/localscript
OLLAMA_BASE_URL=http://ollama:11434
QDRANT_URL=http://qdrant:6333
QDRANT_LOCAL_PATH=
```

Then:
```bash
docker compose up --build
```

## API Usage

**`POST /generate`** — required API endpoint per the specification:

```bash
curl -X POST http://localhost:8080/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Функция factorial(n) для n >= 0"}'
```

Response:
```json
{
  "code": "function factorial(n)\n  if n <= 1 then return 1 end\n  return n * factorial(n - 1)\nend"
}
```

## Agent Pipeline

1. **RAG retrieval** — user query is embedded and matched against the Lua knowledge base
   (domain rules, example prompt-code pairs, Lua reference) stored in Qdrant.
2. **Prompt construction** — system prompt with platform rules + retrieved examples + chat history.
3. **LLM generation** — code generated via local Ollama model.
4. **Lua syntax validation** — generated code is checked with `lua5.4 -p`.
5. **Self-fix loop** — if syntax errors are found, the error is fed back to the LLM
   for correction (up to 2 iterations).
6. **Clarifying questions** — if the task is ambiguous, the agent asks a clarifying question
   instead of guessing.

## Chat Interface

The web UI provides:
- Session management (create, switch, history)
- Lua syntax highlighting (highlight.js)
- Code copy button
- Syntax validation badges (OK / Error)
- Dark theme
- Keyboard shortcut: Enter to send, Shift+Enter for newline

## Knowledge Base

The RAG knowledge base (`knowledge/lua_domain.json`) includes:
- MWS Octapi LowCode platform rules (wf.vars, _utils.array, etc.)
- 8 example prompt-code pairs from the public evaluation sample
- Lua string, table, math function reference
- Lua pattern matching reference
- JSON wrapper format documentation

Embedding model: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (CPU, ~120 MB).

## Project Structure

```
LocalScript/
├── deploy.sh               # One-command deployment (no Docker)
├── stop.sh                 # Stop all services
├── docker-compose.yml      # Docker alternative
├── Dockerfile
├── requirements.txt
├── .env
├── app/
│   ├── main.py             # FastAPI app, routes
│   ├── config.py           # Settings (pydantic-settings)
│   ├── database.py         # Async SQLAlchemy
│   ├── models.py           # ORM models (Session, Message)
│   ├── schemas.py          # Request/response DTOs
│   ├── agent/
│   │   ├── pipeline.py     # Agent orchestration
│   │   ├── prompts.py      # System prompt templates
│   │   ├── validator.py    # Lua syntax validation
│   │   └── rag.py          # RAG embedding + retrieval
│   └── static/
│       ├── index.html
│       ├── style.css
│       └── app.js
├── knowledge/
│   └── lua_domain.json     # RAG knowledge base
└── scripts/
    └── init.py             # DB + Qdrant initialization
```

## Configuration

All settings are in `.env`:

| Variable            | Default (local mode)                                                 |
|---------------------|----------------------------------------------------------------------|
| `DATABASE_URL`      | `postgresql+asyncpg://localscript:localscript@localhost:5432/localscript` |
| `OLLAMA_BASE_URL`   | `http://localhost:11434`                                             |
| `OLLAMA_MODEL`      | `qwen2.5-coder:7b-instruct-q4_K_M`                                  |
| `QDRANT_URL`        | _(empty = use local file mode)_                                      |
| `QDRANT_LOCAL_PATH` | `./qdrant_storage`                                                   |
| `QDRANT_COLLECTION` | `lua_knowledge`                                                      |
| `EMBEDDING_MODEL`   | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`        |
