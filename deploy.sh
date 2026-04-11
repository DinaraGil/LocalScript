#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
LOCAL_DIR="$PROJECT_DIR/.local"
PG_DIR="$LOCAL_DIR/pgsql"
PG_DATA="$LOCAL_DIR/pgdata"
LUA_DIR="$LOCAL_DIR/lua"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[+]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
err()  { echo -e "${RED}[x]${NC} $*" >&2; }

source "$PROJECT_DIR/.env" 2>/dev/null || true

PG_USER="${POSTGRES_USER:-localscript}"
PG_PASS="${POSTGRES_PASSWORD:-localscript}"
PG_DB="${POSTGRES_DB:-localscript}"
PG_PORT=15432
BACKEND_PORT=18080
PG_SOCK_DIR="$LOCAL_DIR/pgsock"
OLLAMA_MODEL_NAME="${OLLAMA_MODEL:-qwen2.5-coder:7b-instruct-q4_K_M}"
OLLAMA_PORT=11435
OLLAMA_HOST="127.0.0.1:$OLLAMA_PORT"
OLLAMA_GPU=0

mkdir -p "$LOCAL_DIR" "$PG_SOCK_DIR"

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
    # create lua5.4 symlink expected by the validator
    ln -sf "$LUA_DIR/bin/lua" "$LUA_DIR/bin/lua5.4"
    cd "$PROJECT_DIR"
    rm -rf "$tmpdir"
    log "Lua 5.4 installed at $LUA_DIR/bin/lua5.4"
}

# ── 2. PostgreSQL (build from source, no sudo needed) ────────────────
install_postgres() {
    if [ -x "$PG_DIR/bin/pg_isready" ]; then
        log "PostgreSQL already built."
        return
    fi
    log "Building PostgreSQL 16 from source (this takes a few minutes)..."
    local tmpdir
    tmpdir=$(mktemp -d)
    curl -fsSL "https://ftp.postgresql.org/pub/source/v16.8/postgresql-16.8.tar.gz" \
        -o "$tmpdir/pg.tar.gz"
    tar xzf "$tmpdir/pg.tar.gz" -C "$tmpdir"
    cd "$tmpdir/postgresql-16.8"
    ./configure --prefix="$PG_DIR" --without-readline --without-icu > /dev/null 2>&1
    make -j"$(nproc)" > /dev/null 2>&1
    make install > /dev/null 2>&1
    cd "$PROJECT_DIR"
    rm -rf "$tmpdir"
    log "PostgreSQL installed at $PG_DIR"
}

start_postgres() {
    export PATH="$PG_DIR/bin:$PATH"
    export LD_LIBRARY_PATH="${PG_DIR}/lib:${LD_LIBRARY_PATH:-}"

    if pg_isready -h localhost -p "$PG_PORT" > /dev/null 2>&1; then
        log "PostgreSQL is already running."
        return
    fi

    if [ ! -d "$PG_DATA" ]; then
        log "Initializing PostgreSQL data directory..."
        "$PG_DIR/bin/initdb" -D "$PG_DATA" -U "$PG_USER" --no-locale -E UTF8 > /dev/null 2>&1
        # allow password auth for local TCP connections
        echo "host all all 127.0.0.1/32 md5" >> "$PG_DATA/pg_hba.conf"
        echo "host all all ::1/128 md5" >> "$PG_DATA/pg_hba.conf"
    fi

    log "Starting PostgreSQL on port $PG_PORT..."
    "$PG_DIR/bin/pg_ctl" -D "$PG_DATA" -l "$LOCAL_DIR/pg.log" \
        -o "-p $PG_PORT -k $PG_SOCK_DIR" start > /dev/null 2>&1

    for i in $(seq 1 20); do
        if pg_isready -h localhost -p "$PG_PORT" > /dev/null 2>&1; then
            log "PostgreSQL started."
            break
        fi
        sleep 1
    done
}

setup_postgres_db() {
    export PATH="$PG_DIR/bin:$PATH"
    export LD_LIBRARY_PATH="${PG_DIR}/lib:${LD_LIBRARY_PATH:-}"

    if "$PG_DIR/bin/psql" -h "$PG_SOCK_DIR" -p "$PG_PORT" -U "$PG_USER" -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$PG_DB'" 2>/dev/null | grep -q 1; then
        log "Database '$PG_DB' already exists."
    else
        "$PG_DIR/bin/psql" -h "$PG_SOCK_DIR" -p "$PG_PORT" -U "$PG_USER" -d postgres -c "CREATE DATABASE $PG_DB;" 2>/dev/null
        log "Created database '$PG_DB'."
    fi

    # set password so asyncpg can connect via TCP with md5
    "$PG_DIR/bin/psql" -h "$PG_SOCK_DIR" -p "$PG_PORT" -U "$PG_USER" -d "$PG_DB" \
        -c "ALTER USER $PG_USER WITH PASSWORD '$PG_PASS';" > /dev/null 2>&1

    log "PostgreSQL is ready."
}

# ── 3. Ollama (own instance on dedicated port + GPU) ─────────────────
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

# ── 4. Python env (uv) ──────────────────────────────────────────────
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

# ── 5. Init (DB tables + RAG index) ─────────────────────────────────
run_init() {
    cd "$PROJECT_DIR"
    # remove stale qdrant lock if no process holds it
    local lock_file="$PROJECT_DIR/qdrant_storage/.lock"
    if [ -f "$lock_file" ]; then
        if ! fuser "$lock_file" > /dev/null 2>&1; then
            log "Removing stale Qdrant lock file..."
            rm -f "$lock_file"
        else
            warn "Qdrant storage is locked by another process."
        fi
    fi
    log "Running initialization (DB tables + RAG knowledge index)..."
    uv run python -m scripts.init
    log "Initialization complete."
}

# ── 6. Start backend ────────────────────────────────────────────────
start_backend() {
    cd "$PROJECT_DIR"
    export PATH="$LUA_DIR/bin:$PG_DIR/bin:$PATH"
    export LD_LIBRARY_PATH="${PG_DIR}/lib:${LD_LIBRARY_PATH:-}"
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
    install_postgres
    start_postgres
    setup_postgres_db
    install_ollama
    start_ollama
    pull_model
    setup_venv
    run_init
    start_backend
}

main "$@"
