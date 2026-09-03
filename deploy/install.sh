#!/usr/bin/env bash
set -euo pipefail

# DecisionJury one-time setup for a single server in China.
# Uses domestic mirrors (npmmirror / tuna) because GitHub/nodesource/astral are blocked.
# Usage:  bash deploy/install.sh

# China-friendly defaults (override via env if needed)
PIP_INDEX="${PIP_INDEX:-https://pypi.tuna.tsinghua.edu.cn/simple}"
NPM_REGISTRY="${NPM_REGISTRY:-https://registry.npmmirror.com}"
NODE_MIRROR="${NODE_MIRROR:-https://npmmirror.com/mirrors/node}"
NODE_VERSION="${NODE_VERSION:-20.18.0}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> [1/5] Node.js + npm (via npmmirror)"
if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
  echo "    Installing Node ${NODE_VERSION} from npmmirror ..."
  curl -fL "${NODE_MIRROR}/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.xz" -o /tmp/node.tar.xz
  sudo rm -rf /usr/local/bin/node /usr/local/bin/npm /usr/local/bin/npx /usr/local/lib/node_modules
  sudo tar -xJf /tmp/node.tar.xz -C /usr/local --strip-components=1
  rm -f /tmp/node.tar.xz
else
  echo "    node/npm already present."
fi
echo "    node: $(node --version 2>/dev/null || echo MISSING)   npm: $(npm --version 2>/dev/null || echo MISSING)"
npm config set registry "${NPM_REGISTRY}" >/dev/null 2>&1 || true

echo "==> [2/5] Python venv + deps (via tuna pip index)"
if [ ! -x ".venv/bin/python" ]; then
  python3 -m venv .venv
fi
"./.venv/bin/python" -m pip install --upgrade pip -i "${PIP_INDEX}"
"./.venv/bin/pip" install -i "${PIP_INDEX}" -r backend/requirements.txt -r rag/requirements.txt

echo "==> [3/5] Frontend deps (via npmmirror registry)"
cd "$ROOT/frontend"
npm install --registry="${NPM_REGISTRY}"
cd "$ROOT"

echo "==> [4/5] .env"
if [ ! -f "$ROOT/.env" ]; then
  cp "$ROOT/deploy/.env.example" "$ROOT/.env"
  echo "    Created $ROOT/.env from deploy/.env.example"
  echo "    >>> Edit .env and set DEEPSEEK_API_KEY (and confirm ENV=production)."
else
  echo "    .env already exists, skip."
fi

echo "==> [5/5] Done."
echo "Next:  nano "$ROOT/.env"  then  bash deploy/start.sh"
