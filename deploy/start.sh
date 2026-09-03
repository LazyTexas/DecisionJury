#!/usr/bin/env bash
set -euo pipefail

# Start all DecisionJury services inside named screen sessions (single server, screen only).
# Usage:  bash deploy/start.sh

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
LOG_DIR="$ROOT/logs"
mkdir -p "$LOG_DIR"

if ! command -v screen >/dev/null 2>&1; then
  echo "[ERROR] screen not found. Install: sudo apt install -y screen"
  exit 1
fi
if [ ! -x ".venv/bin/python" ]; then
  echo "[ERROR] .venv not found. Run: bash deploy/install.sh"
  exit 1
fi
if [ ! -f ".env" ]; then
  echo "[WARN] .env not found. Creating from deploy/.env.example ..."
  cp deploy/.env.example .env
  echo "       Remember to set DEEPSEEK_API_KEY in .env"
fi

# Create a detached screen session named $1 running the command in $2.
start_screen() {
  local name="$1"; shift
  if screen -ls 2>/dev/null | grep -q "\.${name}\."; then
    echo "[SKIP] screen ${name} already running"
    return
  fi
  echo "[START] ${name}"
  screen -dmS "$name" bash -c "$*"
}

start_screen decisionjury-backend "cd '$ROOT' && exec .venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 > '$LOG_DIR/backend.log' 2>&1"
start_screen decisionjury-rag "cd '$ROOT/rag' && exec ../.venv/bin/python -m uvicorn retriever:app --host 127.0.0.1 --port 8001 > '$LOG_DIR/rag.log' 2>&1"
start_screen decisionjury-frontend "cd '$ROOT/frontend' && exec node node_modules/vite/bin/vite.js --host 0.0.0.0 > '$LOG_DIR/frontend.log' 2>&1"

sleep 8
IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo "----------------------------------------------------"
echo "Backend : http://127.0.0.1:8000   (logs/backend.log)"
echo "RAG     : http://127.0.0.1:8001   (logs/rag.log)"
echo "Frontend: http://${IP:-<server-ip>}:5173   (logs/frontend.log)"
echo "Screens : screen -ls   |   Logs: tail -f logs/<name>.log"
echo "----------------------------------------------------"
