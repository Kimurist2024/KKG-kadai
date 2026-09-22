#!/usr/bin/env bash
# このアプリの開発用プロセスをすべて止める。
#   1. 残っている start.sh とその子孫（next dev の親は SIGTERM で終わらないことがあるので、猶予後に KILL）
#   2. バックエンド (8000) とフロントエンド (5173) のポートを使っているプロセス
#   3. 親の start.sh を失って残った next / uvicorn（作業ディレクトリがこのアプリ配下のものだけ）
set -uo pipefail
cd "$(dirname "$0")/.."
# shellcheck source=scripts/_proc.sh
. scripts/_proc.sh
APP_DIR="$(pwd -P)"
STOP_GRACE="${STOP_GRACE:-5}"

for other in $(proc_other_starts "$APP_DIR"); do
  echo "start.sh (PID $other) とその子プロセスを停止"
  proc_stop_start_instance "$STOP_GRACE" "$other"
done
for port in "${BACK_PORT:-8000}" "${FRONT_PORT:-5173}"; do
  pids=$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
  if [ -n "$pids" ]; then
    echo "ポート $port: プロセス $(echo $pids | tr '\n' ' ')を停止"
    # shellcheck disable=SC2086
    proc_stop "$STOP_GRACE" $pids
  else
    echo "ポート $port: 使用中のプロセスなし"
  fi
done
for pid in $(proc_orphans "$APP_DIR"); do
  echo "親を失ったプロセス (PID $pid) を停止"
  proc_stop_tree "$STOP_GRACE" "$pid"
done
