#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCAL_DIR="$PROJECT_DIR/.local"
PG_DIR="$LOCAL_DIR/pgsql"
PG_DATA="$LOCAL_DIR/pgdata"

echo "Stopping LocalScript services..."

pkill -f "uvicorn app.main:app" 2>/dev/null && echo "Stopped backend" || true

if [ -f "$LOCAL_DIR/ollama.pid" ]; then
    PID=$(cat "$LOCAL_DIR/ollama.pid")
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID"
        echo "Stopped Ollama (PID $PID)"
    fi
    rm -f "$LOCAL_DIR/ollama.pid"
fi

if [ -x "$PG_DIR/bin/pg_ctl" ] && [ -d "$PG_DATA" ]; then
    export LD_LIBRARY_PATH="${PG_DIR}/lib:${LD_LIBRARY_PATH:-}"
    "$PG_DIR/bin/pg_ctl" -D "$PG_DATA" stop -m fast 2>/dev/null && echo "Stopped PostgreSQL" || true
fi

echo "Done."
