#!/usr/bin/env bash
# バックエンド (8000) とフロントエンド (5173) のポートを使っているプロセスを停止する。
for port in "${BACK_PORT:-8000}" "${FRONT_PORT:-5173}"; do
  pids=$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
  if [ -n "$pids" ]; then
    echo "ポート $port: プロセス $pids を停止"
    kill $pids 2>/dev/null || true
  else
    echo "ポート $port: 使用中のプロセスなし"
  fi
done
