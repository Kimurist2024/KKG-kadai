#!/usr/bin/env bash
# 決定論的な検証ゲート。exit 0 = 合格、1 = 不合格。
# 使い方: .claude/scripts/verify.sh [quick|all]
#   quick … pytest + typecheck + vitest（速い。実装中の反復用）
#   all   … quick + next build（PR 前の必須ゲート。既定）
# 方針: 成功は 1 行だけ、失敗したときだけ詳細を出す（コンテキストを汚さない）。
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
APP="$ROOT/floorplan-analyzer"
SCOPE="${1:-all}"
PY="$APP/backend/.venv/bin/python"
fail=0

run() { # run <表示名> <作業ディレクトリ> <コマンド...>
  local name="$1" dir="$2"; shift 2
  local out
  if out="$(cd "$dir" && "$@" 2>&1)"; then
    printf '  OK   %s\n' "$name"
  else
    printf '  FAIL %s\n' "$name"
    printf '%s\n' "$out" | tail -40 | sed 's/^/       /'
    fail=1
  fi
}

echo "verify ($SCOPE)"
[ -x "$PY" ] || { echo "  FAIL backend: $PY がありません。README の環境構築手順を実行してください"; exit 1; }
run "backend pytest"      "$APP/backend"  "$PY" -m pytest -q
run "frontend typecheck"  "$APP/frontend" npm run typecheck
run "frontend vitest"     "$APP/frontend" npm test
if [ "$SCOPE" = "all" ]; then
  run "frontend build"    "$APP/frontend" npm run build
fi

if [ "$fail" -eq 0 ]; then echo "verify: PASS"; else echo "verify: FAIL"; fi
exit "$fail"
