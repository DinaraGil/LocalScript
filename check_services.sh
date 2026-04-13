#!/usr/bin/env bash
# Проверка состояния всех сервисов LocalScript
set -uo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$PROJECT_DIR/.env" 2>/dev/null || true

OLLAMA_PORT=11435
BACKEND_PORT=18080
LUA_DIR="$PROJECT_DIR/.local/lua"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

total=0
up=0

check() {
    local name="$1"
    local status="$2"  # 0 = ok
    local detail="$3"
    total=$((total + 1))
    if [ "$status" -eq 0 ]; then
        echo -e "  ${GREEN}✔${NC}  $name  ${GREEN}$detail${NC}"
        up=$((up + 1))
    else
        echo -e "  ${RED}✘${NC}  $name  ${RED}$detail${NC}"
    fi
}

echo ""
echo "══════════════════════════════════════════"
echo "  LocalScript — service health check"
echo "══════════════════════════════════════════"
echo ""

# ── Ollama ─────────────────────────────────────────────────────────
ollama_resp=$(curl -sf --max-time 3 "http://127.0.0.1:$OLLAMA_PORT/api/tags" 2>/dev/null)
ollama_rc=$?
if [ $ollama_rc -eq 0 ]; then
    model_count=$(echo "$ollama_resp" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('models',[])))" 2>/dev/null || echo "?")
    check "Ollama (port $OLLAMA_PORT)" 0 "running, $model_count model(s) loaded"
else
    check "Ollama (port $OLLAMA_PORT)" 1 "not running"
fi

# ── Lua 5.4 ────────────────────────────────────────────────────────
if [ -x "$LUA_DIR/bin/lua5.4" ]; then
    lua_ver=$("$LUA_DIR/bin/lua5.4" -v 2>&1 | head -1)
    check "Lua validator" 0 "$lua_ver"
else
    check "Lua validator" 1 "lua5.4 not found at $LUA_DIR/bin/"
fi

# ── Qdrant (local storage) ────────────────────────────────────────
qdrant_path="${QDRANT_LOCAL_PATH:-./qdrant_storage}"
if [ -d "$PROJECT_DIR/$qdrant_path" ] || [ -d "$qdrant_path" ]; then
    check "Qdrant storage" 0 "directory exists ($qdrant_path)"
else
    check "Qdrant storage" 1 "directory not found ($qdrant_path)"
fi

# ── Chat storage ──────────────────────────────────────────────────
chat_path="${CHAT_STORAGE_DIR:-./chat_storage}"
if [ -d "$PROJECT_DIR/$chat_path" ] || [ -d "$chat_path" ]; then
    file_count=$(ls -1 "$PROJECT_DIR/$chat_path"/*.json 2>/dev/null | wc -l || echo "0")
    check "Chat storage" 0 "directory exists ($chat_path, $file_count session(s))"
else
    check "Chat storage" 1 "directory not found ($chat_path)"
fi

# ── Backend (FastAPI) ──────────────────────────────────────────────
backend_resp=$(curl -sf --max-time 5 "http://localhost:$BACKEND_PORT/docs" -o /dev/null -w "%{http_code}" 2>/dev/null)
backend_rc=$?
if [ $backend_rc -eq 0 ] && [ "$backend_resp" = "200" ]; then
    check "Backend API (port $BACKEND_PORT)" 0 "responding (HTTP 200)"
else
    check "Backend API (port $BACKEND_PORT)" 1 "not responding"
fi

# ── Итоги ──────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════"
if [ "$up" -eq "$total" ]; then
    echo -e "  ${GREEN}All $total services are UP${NC}"
else
    echo -e "  ${YELLOW}$up / $total services are UP${NC}"
fi
echo "══════════════════════════════════════════"
echo ""

[ "$up" -eq "$total" ]
