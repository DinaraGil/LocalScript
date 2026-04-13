#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
LOCAL_DIR="$PROJECT_DIR/.local"
LUA_DIR="$LOCAL_DIR/lua"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[+]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
err()  { echo -e "${RED}[x]${NC} $*" >&2; }

source "$PROJECT_DIR/.env" 2>/dev/null || true

BACKEND_PORT=18080
OLLAMA_MODEL_NAME="${OLLAMA_MODEL:-qwen2.5-coder:7b-instruct-q4_K_M}"
OLLAMA_PORT=11435
OLLAMA_HOST="127.0.0.1:$OLLAMA_PORT"
OLLAMA_GPU=0

mkdir -p "$LOCAL_DIR"

# ── 1. Lua 5.4 (build from source) ──────────────────────────────────
install_lua() {
    if [ -x "$LUA_DIR/bin/lua5.4" ]; then
        log "Lua 5.4 already built."
        return
    fi
    log "Building Lua 5.4 from source..."
    local tmpdir
    tmpdir=$(mktemp -d)
    curl -fsSL "https://www.lua.org/ftp/lua-5.4.7.tar.gz" -o "$tmpdir/lua.tar.gz"
    tar xzf "$tmpdir/lua.tar.gz" -C "$tmpdir"
    cd "$tmpdir/lua-5.4.7"
    make linux -j"$(nproc)" MYCFLAGS="-DLUA_USE_READLINE" MYLIBS="" > /dev/null 2>&1 || \
        make linux -j"$(nproc)" MYCFLAGS="" MYLIBS="" > /dev/null 2>&1
    make install INSTALL_TOP="$LUA_DIR" > /dev/null 2>&1
    ln -sf "$LUA_DIR/bin/lua" "$LUA_DIR/bin/lua5.4"
    cd "$PROJECT_DIR"
    rm -rf "$tmpdir"
    log "Lua 5.4 installed at $LUA_DIR/bin/lua5.4"
}

# ── 2. Ollama (own instance on dedicated port + GPU) ─────────────────
install_ollama() {
    if [ -x "$LOCAL_DIR/bin/ollama" ]; then
        log "Ollama binary already present."
        return
    fi
    log "Downloading Ollama..."
    mkdir -p "$LOCAL_DIR/bin"
    local tmpdir
    tmpdir=$(mktemp -d)
    curl -fsSL -L "https://github.com/ollama/ollama/releases/latest/download/ollama-linux-amd64.tar.zst" \
        -o "$tmpdir/ollama.tar.zst"
    tar --use-compress-program=unzstd -xf "$tmpdir/ollama.tar.zst" -C "$LOCAL_DIR"
    rm -rf "$tmpdir"
    log "Ollama installed at $LOCAL_DIR/bin/ollama"
}

start_ollama() {
    local ollama_bin="$LOCAL_DIR/bin/ollama"
    if curl -sf "http://$OLLAMA_HOST/api/tags" > /dev/null 2>&1; then
        log "Ollama is already running on port $OLLAMA_PORT."
        return
    fi
    log "Starting Ollama on port $OLLAMA_PORT (GPU $OLLAMA_GPU)..."
    OLLAMA_HOST="$OLLAMA_HOST" \
    OLLAMA_MODELS="$LOCAL_DIR/ollama_models" \
    CUDA_VISIBLE_DEVICES="$OLLAMA_GPU" \
    nohup "$ollama_bin" serve > "$LOCAL_DIR/ollama.log" 2>&1 &
    echo $! > "$LOCAL_DIR/ollama.pid"
    for i in $(seq 1 30); do
        if curl -sf "http://$OLLAMA_HOST/api/tags" > /dev/null 2>&1; then
            log "Ollama started (PID $(cat "$LOCAL_DIR/ollama.pid"), GPU $OLLAMA_GPU)."
            return
        fi
        sleep 1
    done
    err "Ollama failed to start. Check $LOCAL_DIR/ollama.log"
    exit 1
}

pull_model() {
    local ollama_bin="$LOCAL_DIR/bin/ollama"
    if curl -sf "http://$OLLAMA_HOST/api/tags" 2>/dev/null | grep -q "$OLLAMA_MODEL_NAME"; then
        log "Model '$OLLAMA_MODEL_NAME' already pulled."
        return
    fi
    log "Pulling model '$OLLAMA_MODEL_NAME'..."
    OLLAMA_HOST="$OLLAMA_HOST" "$ollama_bin" pull "$OLLAMA_MODEL_NAME"
    log "Model ready."
}

# ── 3. Python env (uv) ──────────────────────────────────────────────
setup_venv() {
    if ! command -v uv &> /dev/null; then
        log "Installing uv..."
        curl -LsSf https://astral.sh/uv/install.sh | sh
        export PATH="$HOME/.local/bin:$PATH"
    fi
    cd "$PROJECT_DIR"
    if [ ! -d "$VENV_DIR" ]; then
        log "Creating virtual environment with uv..."
        uv venv "$VENV_DIR"
    fi
    log "Installing Python dependencies with uv..."
    uv pip install -r "$PROJECT_DIR/requirements.txt"
    log "Python dependencies installed."
}

# ── 4. Init (RAG index + chat storage) ───────────────────────────────
run_init() {
    cd "$PROJECT_DIR"
    local lock_file="$PROJECT_DIR/qdrant_storage/.lock"
    if [ -f "$lock_file" ]; then
        if ! fuser "$lock_file" > /dev/null 2>&1; then
            log "Removing stale Qdrant lock file..."
            rm -f "$lock_file"
        else
            warn "Qdrant storage is locked by another process."
        fi
    fi
    log "Running initialization (RAG knowledge index + chat storage)..."
    uv run python -m scripts.init
    log "Initialization complete."
}

# ── 5. Start backend ────────────────────────────────────────────────
start_backend() {
    cd "$PROJECT_DIR"
    export PATH="$LUA_DIR/bin:$PATH"
    log "Starting FastAPI backend on http://localhost:$BACKEND_PORT ..."
    uv run uvicorn app.main:app --host 0.0.0.0 --port "$BACKEND_PORT"
}

# ── Main ─────────────────────────────────────────────────────────────
main() {
    echo ""
    echo "========================================="
    echo "  LocalScript — deployment (no sudo)"
    echo "========================================="
    echo ""

    install_lua
    install_ollama
    start_ollama
    pull_model
    setup_venv
    run_init
    start_backend
}

main "$@"
