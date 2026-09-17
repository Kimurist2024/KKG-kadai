#!/usr/bin/env bash
# バックエンド (8000) とフロントエンド (5173) を並列で準備・起動する。
# 既にポートを使っているプロセスがあれば先に停止する。Ctrl+C で両方止まる。
set -euo pipefail
cd "$(dirname "$0")/.."
BACK_PORT="${BACK_PORT:-8000}"
FRONT_PORT="${FRONT_PORT:-5173}"
BACK_RELOAD="${BACK_RELOAD:-1}"
READY_TIMEOUT="${READY_TIMEOUT:-30}"
BACK_PID=""
FRONT_PID=""
BACK_SETUP_PID=""
FRONT_SETUP_PID=""
BACK_READY_PID=""
FRONT_READY_PID=""

stop_pid() {
  [ -n "$1" ] || return 0
  kill "$1" 2>/dev/null || true
}

cleanup() {
  status=$?
  trap - EXIT INT TERM
  stop_pid "$BACK_SETUP_PID"
  stop_pid "$FRONT_SETUP_PID"
  stop_pid "$BACK_READY_PID"
  stop_pid "$FRONT_READY_PID"
  stop_pid "$BACK_PID"
  stop_pid "$FRONT_PID"
  wait 2>/dev/null || true
  exit "$status"
}
trap cleanup EXIT INT TERM

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

# 両ポートの停止待ちは独立なので並列化する。
free_port "$BACK_PORT" &
BACK_FREE_PID=$!
free_port "$FRONT_PORT" &
FRONT_FREE_PID=$!
wait "$BACK_FREE_PID"
wait "$FRONT_FREE_PID"

# 初回セットアップも別ディレクトリで独立しているため並列化する。
if [ ! -x backend/.venv/bin/uvicorn ]; then
  (
    echo "== backend: venv を作成して依存をインストール"
    python3 -m venv backend/.venv
    backend/.venv/bin/pip install -q -r backend/requirements.txt
  ) &
  BACK_SETUP_PID=$!
fi
if [ ! -x frontend/node_modules/.bin/next ]; then
  (
    echo "== frontend: npm install"
    cd frontend
    npm install --no-audit --no-fund
  ) &
  FRONT_SETUP_PID=$!
fi
if [ -n "$BACK_SETUP_PID" ]; then wait "$BACK_SETUP_PID"; BACK_SETUP_PID=""; fi
if [ -n "$FRONT_SETUP_PID" ]; then wait "$FRONT_SETUP_PID"; FRONT_SETUP_PID=""; fi

# subshell を exec で置き換え、保存する PID と実サーバーを一致させる。
if [ "$BACK_RELOAD" = "1" ]; then
  (cd backend && exec .venv/bin/uvicorn app.main:app --reload --port "$BACK_PORT") &
else
  (cd backend && exec .venv/bin/uvicorn app.main:app --port "$BACK_PORT") &
fi
BACK_PID=$!
(cd frontend && exec env API_PROXY_TARGET="http://127.0.0.1:$BACK_PORT" ./node_modules/.bin/next dev --port "$FRONT_PORT") &
FRONT_PID=$!

wait_for_url() {
  name=$1
  url=$2
  pid=$3
  attempts=$((READY_TIMEOUT * 20))
  while [ "$attempts" -gt 0 ]; do
    kill -0 "$pid" 2>/dev/null || { echo "$name の起動に失敗しました" >&2; return 1; }
    if curl -fsS --max-time 1 "$url" >/dev/null 2>&1; then return 0; fi
    attempts=$((attempts - 1))
    sleep 0.05
  done
  echo "$name が ${READY_TIMEOUT}秒以内に応答しませんでした" >&2
  return 1
}

# API import と Next.js の初回ページコンパイルを並列で先行する。
wait_for_url "backend" "http://127.0.0.1:$BACK_PORT/api/health" "$BACK_PID" &
BACK_READY_PID=$!
wait_for_url "frontend" "http://127.0.0.1:$FRONT_PORT/" "$FRONT_PID" &
FRONT_READY_PID=$!
wait "$BACK_READY_PID"
BACK_READY_PID=""
wait "$FRONT_READY_PID"
FRONT_READY_PID=""

echo "== 起動完了"
echo "== backend  : http://127.0.0.1:$BACK_PORT  (API / docs は /docs)"
echo "== frontend : http://localhost:$FRONT_PORT  ← ブラウザでこちらを開く"

# どちらかが異常終了したら、EXIT trap がもう一方も停止する。
while kill -0 "$BACK_PID" 2>/dev/null && kill -0 "$FRONT_PID" 2>/dev/null; do
  sleep 1
done
echo "開発サーバーが停止しました" >&2
exit 1
