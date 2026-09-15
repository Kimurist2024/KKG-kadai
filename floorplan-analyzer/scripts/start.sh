#!/usr/bin/env bash
# バックエンド (8000) とフロントエンド (5173) をまとめて起動する。
# 既にポートを使っているプロセスがあれば先に停止する。Ctrl+C で両方止まる。
set -euo pipefail
cd "$(dirname "$0")/.."
BACK_PORT="${BACK_PORT:-8000}"
FRONT_PORT="${FRONT_PORT:-5173}"

free_port() {
  local pids
  pids=$(lsof -tiTCP:"$1" -sTCP:LISTEN 2>/dev/null || true)
  if [ -n "$pids" ]; then
    echo "ポート $1 を使用中のプロセス ($pids) を停止します"
    kill $pids 2>/dev/null || true
    sleep 1
    pids=$(lsof -tiTCP:"$1" -sTCP:LISTEN 2>/dev/null || true)
    [ -n "$pids" ] && kill -9 $pids 2>/dev/null || true
  fi
}
free_port "$BACK_PORT"
free_port "$FRONT_PORT"

# 初回のみセットアップ
if [ ! -x backend/.venv/bin/uvicorn ]; then
  echo "== backend: venv を作成して依存をインストール"
  python3 -m venv backend/.venv
  backend/.venv/bin/pip install -q -r backend/requirements.txt
fi
if [ ! -d frontend/node_modules ]; then
  echo "== frontend: npm install"
  (cd frontend && npm install --no-audit --no-fund)
fi

echo "== backend  : http://127.0.0.1:$BACK_PORT  (API / docs は /docs)"
(cd backend && .venv/bin/uvicorn app.main:app --reload --port "$BACK_PORT") &
BACK_PID=$!
echo "== frontend : http://localhost:$FRONT_PORT  ← ブラウザでこちらを開く"
(cd frontend && API_PROXY_TARGET="http://127.0.0.1:$BACK_PORT" npx next dev --port "$FRONT_PORT") &
FRONT_PID=$!

trap 'echo; echo "停止します"; kill $BACK_PID $FRONT_PID 2>/dev/null; wait 2>/dev/null; exit 0' INT TERM
wait
