# LocalScript — AI-agent for local Lua code generation

A fully local AI agent system that generates Lua code from natural language prompts
(Russian and English). Runs entirely on your own infrastructure with no external API calls.

## Architecture

```
┌────────────┐     ┌───────────────────┐     ┌────────────────┐
│   Client    │── ▶│  FastAPI Backend    │──▶│  Ollama (GPU)   │
│  (curl/UI)  │     │     :8080           │     │    :11434       │
└────────────┘     └──────┬───┬────────┘     └────────────────┘
                            │   │
                   ┌───────┘   └──────┐
                   ▼                   ▼
            ┌────────────┐    ┌────────────┐
            │ JSON files  │    │   Qdrant    │
            │ chat_store  │    │   :6333     │
            └────────────┘    └────────────┘
```

**Components:**
- **Backend** — FastAPI app with agent pipeline (RAG + LLM + validation + self-fix loop)
- **Ollama** — local LLM runtime with GPU acceleration
- **Chat storage** — JSON file-based session and message history
- **Qdrant** — vector database for RAG (local file mode or server)

## Model

```
ollama pull qwen2.5-coder:7b-instruct-q4_K_M
```

**Parameters (fixed for evaluation):**

| Parameter     | Value |
|---------------|-------|
| `num_ctx`     | 4096  |
| `num_predict` | 256   |

**VRAM usage:** ~5 GB peak (well under 8 GB limit).

## Quick Start (without Docker)

### One-command deploy

```bash
./deploy.sh
```

This script automatically:
1. Installs system packages (`lua5.4`, `curl`)
2. Installs Ollama and pulls the model
3. Creates Python venv and installs dependencies
4. Runs initialization (RAG knowledge indexing)
5. Starts the FastAPI backend on **http://localhost:8080**

To stop all services:
```bash
./stop.sh
```

### Manual step-by-step

```bash
# 1. Install system deps
sudo apt-get install -y lua5.4 curl

# 2. Install and start Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama serve &              # start in background
ollama pull qwen2.5-coder:7b-instruct-q4_K_M

# 3. Python environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 4. Initialize (RAG index + pull model check)
python -m scripts.init

# 5. Start backend
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

### Docker Compose (alternative)

```bash
docker compose up --build
```

Backend will be available at **http://localhost:18080** (mapped from container port 8080).

The compose file starts Qdrant, Ollama, an init container (pulls model + indexes knowledge),
and the backend. All env variables are read from `.env` and overridden where needed.

## API Usage

**`POST /generate`** — stateless code generation:

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

**Chat session API** — multi-turn conversations with history:

```bash
# Create session
curl -X POST http://localhost:8080/chat/sessions

# Send message
curl -X POST http://localhost:8080/chat/sessions/{id}/messages \
  -H "Content-Type: application/json" \
  -d '{"content": "Напиши функцию суммы массива"}'

# Get message history
curl http://localhost:8080/chat/sessions/{id}/messages
```

## Agent Pipeline

1. **RAG retrieval** — user query is embedded and matched against the Lua knowledge base
   (examples, patterns, Lua reference) stored in Qdrant.
2. **Prompt construction** — system prompt with platform rules + retrieved context + few-shot examples + chat history.
3. **LLM generation** — code generated via local Ollama model.
4. **Lua syntax validation** — generated code is checked with `lua5.4 -p`.
5. **Self-fix loop** — if syntax errors are found, the error is fed back to the LLM
   for correction (up to 2 iterations).
6. **Clarifying questions** — if the task is ambiguous, the agent asks a clarifying question
   instead of guessing.

## Knowledge Base

The RAG knowledge base (`knowledge/lua_domain.json`) includes:
- 4 example prompt-code pairs (complex tasks: ISO 8601, array normalization, Unix timestamp, etc.)
- 6 common Lua patterns (filtering, field removal, type checking, etc.)
- 4 Lua reference entries (string, table, math functions, pattern matching)

Platform rules and basic examples are hardcoded in the system prompt to always be available.

Embedding model: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (CPU, ~120 MB).

## Project Structure

```
LocalScript/
├── deploy.sh               # One-command deployment (no Docker)
├── stop.sh                 # Stop all services
├── check_services.sh       # Health check for all services
├── requests.sh             # Test curl requests (8 tasks + chat test)
├── docker-compose.yml      # Docker alternative
├── Dockerfile
├── requirements.txt
├── .env
├── app/
│   ├── main.py             # FastAPI app, routes
│   ├── config.py           # Settings (pydantic-settings)
│   ├── chat_store.py       # JSON file-based chat storage
│   ├── schemas.py          # Request/response DTOs
│   └── agent/
│       ├── pipeline.py     # Agent orchestration
│       ├── prompts.py      # System prompt templates
│       ├── validator.py    # Lua syntax validation
│       ├── rag.py          # RAG embedding + retrieval
│       ├── context_manager.py  # Chat context windowing
│       └── token_counter.py    # Token counting utils
├── knowledge/
│   └── lua_domain.json     # RAG knowledge base
└── scripts/
    └── init.py             # Qdrant + model initialization
```

## Configuration

All settings are in `.env`:

| Variable            | Default (local mode)                                          |
|---------------------|---------------------------------------------------------------|
| `OLLAMA_BASE_URL`   | `http://localhost:11434`                                      |
| `OLLAMA_MODEL`      | `qwen2.5-coder:7b-instruct-q4_K_M`                           |
| `QDRANT_URL`        | _(empty = use local file mode)_                               |
| `QDRANT_LOCAL_PATH` | `./qdrant_storage`                                            |
| `QDRANT_COLLECTION` | `lua_knowledge`                                               |
| `EMBEDDING_MODEL`   | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` |
| `CHAT_STORAGE_DIR`  | `./chat_storage`                                              |
