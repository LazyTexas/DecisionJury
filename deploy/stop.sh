#!/usr/bin/env bash
set -uo pipefail

# Stop all DecisionJury screen sessions and free the project ports.
# Usage:  bash deploy/stop.sh

if ! command -v screen >/dev/null 2>&1; then
  echo "[ERROR] screen not found. Install: sudo apt install -y screen"
  exit 1
fi

for name in decisionjury-backend decisionjury-rag decisionjury-frontend; do
  if screen -ls 2>/dev/null | grep -q "\.${name}\."; then
    echo "[STOP] screen ${name}"
    screen -S "$name" -X quit
  else
    echo "[SKIP] screen ${name} not running"
  fi
done

echo "[FALLBACK] freeing ports 8000/8001/5173 if still in use ..."
for port in 8000 8001 5173; do
  fuser -k "${port}/tcp" >/dev/null 2>&1 || true
done

echo "[OK] Stopped."
