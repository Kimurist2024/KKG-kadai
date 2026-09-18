#!/usr/bin/env bash
# 決定論的な検証ゲート。exit 0 = 合格、1 = 不合格。
# 使い方: .claude/scripts/verify.sh [quick|all]
#   quick … pytest + typecheck + vitest（速い。実装中の反復用）
#   all   … quick + next build（PR 前の必須ゲート。既定）
#
# 出力の方針:
#   - コンソールには各ステップ 1 行（結果・所要時間・要約）と最終行だけを出す
#   - 各ステップの全出力は .claude/logs/verify/<実行時刻>/NN-<名前>.log に保存する
#   - 失敗したステップだけ、ログの末尾 40 行とパスを表示する
#   - pytest / vitest は JUnit XML（pytest.junit.xml / vitest.junit.xml）も同じ場所に出す
#   - 直近の実行は .claude/logs/verify/latest から開ける（保存は最新 10 回分）
#   - 色は端末に直接出すときだけ使う（NO_COLOR を設定すると無効）
# 環境変数: VERIFY_LOG_DIR … ログの保存先を変える（既定: <repo>/.claude/logs/verify）
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
APP="$ROOT/floorplan-analyzer"
SCOPE="${1:-all}"
PY="$APP/backend/.venv/bin/python"
case "$SCOPE" in quick|all) ;; *) echo "使い方: verify.sh [quick|all]" >&2; exit 2;; esac

LOGROOT="${VERIFY_LOG_DIR:-$ROOT/.claude/logs/verify}"
STAMP="$(date +%Y%m%d-%H%M%S)"
RUN="$LOGROOT/$STAMP"
mkdir -p "$RUN"

if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
  C_OK=$'\033[32m'; C_NG=$'\033[31m'; C_DIM=$'\033[2m'; C_BOLD=$'\033[1m'; C_0=$'\033[0m'
else
  C_OK=""; C_NG=""; C_DIM=""; C_BOLD=""; C_0=""
fi

now_ms() { python3 -c 'import time; print(int(time.time() * 1000))'; }
fmt_ms() { awk -v ms="$1" 'BEGIN { printf "%.1fs", ms / 1000 }'; }

# 各ステップの要約（ログの全文から 1 行だけ拾う）。見つからなければ空文字
sum_pytest() {
  grep -oE '([0-9]+ (passed|failed|errors?|skipped|xfailed|xpassed|warnings?)(, )?)+' "$1" | tail -1
}
sum_typecheck() {
  local n; n="$(grep -cE 'error TS[0-9]+' "$1")"
  if [ "$n" -gt 0 ]; then printf '%s 件の型エラー' "$n"; else printf '型エラーなし'; fi
}
sum_vitest() {
  local t f
  t="$(grep -E '^[[:space:]]*Tests[[:space:]]' "$1" | tail -1 | sed -E 's/^[[:space:]]*Tests[[:space:]]+//; s/ \([0-9]+\)$//')"
  f="$(grep -E '^[[:space:]]*Test Files[[:space:]]' "$1" | tail -1 | sed -E 's/^[[:space:]]*Test Files[[:space:]]+//; s/ .*$//')"
  [ -n "$t" ] && printf '%s / %s files' "$t" "$f"
}
sum_build() {
  if grep -qE 'Compiled successfully' "$1"; then printf '本番ビルド成功'; fi
}

# 失敗時の抜粋: pytest の 'slowest N durations' ブロックは除いてから末尾 40 行を出す（ログ本体には残る）
failure_tail() {
  awk '/^=+ slowest [0-9]+ durations =+$/ { skip = 1; next } skip && /^=+/ { skip = 0 } !skip' "$1" | tail -40
}

step=0
fail=0
failed=""
: > "$RUN/summary.tsv"

run() { # run <表示名> <作業ディレクトリ> <要約関数> <コマンド...>
  local name="$1" dir="$2" summarize="$3"; shift 3
  step=$((step + 1))
  local slug log t0 t1 rc dur summary
  slug="$(printf '%s' "$name" | tr ' /' '--')"
  log="$RUN/$(printf '%02d' "$step")-$slug.log"
  t0="$(now_ms)"
  ( cd "$dir" && "$@" ) > "$log" 2>&1
  rc=$?
  t1="$(now_ms)"
  dur="$(fmt_ms $((t1 - t0)))"
  summary="$("$summarize" "$log")"
  if [ "$rc" -eq 0 ]; then
    printf '  %sOK%s    %-20s %7s  %s%s%s\n' "$C_OK" "$C_0" "$name" "$dur" "$C_DIM" "$summary" "$C_0"
  else
    printf '  %sFAIL%s  %-20s %7s  exit %s%s%s\n' "$C_NG" "$C_0" "$name" "$dur" "$C_DIM" "$rc" "$C_0"
    printf '        %s--- %s（末尾 40 行）---%s\n' "$C_DIM" "$log" "$C_0"
    failure_tail "$log" | sed 's/^/        /'
    fail=1
    failed="$failed $name"
  fi
  printf '%s\t%s\t%s\t%s\t%s\n' "$name" "$rc" "$dur" "$summary" "$log" >> "$RUN/summary.tsv"
}

T0="$(now_ms)"
printf '%sverify (%s)%s  %s\n' "$C_BOLD" "$SCOPE" "$C_0" "$(date '+%Y-%m-%d %H:%M:%S')"
[ -x "$PY" ] || { printf '  %sFAIL%s  backend: %s がありません。README の環境構築手順を実行してください\n' "$C_NG" "$C_0" "$PY"; exit 1; }

run "backend pytest"     "$APP/backend"  sum_pytest    "$PY" -m pytest -q -ra --durations=10 --junitxml="$RUN/pytest.junit.xml"
run "frontend typecheck" "$APP/frontend" sum_typecheck npm run typecheck
run "frontend vitest"    "$APP/frontend" sum_vitest    npx vitest run --reporter=verbose --reporter=junit --outputFile.junit="$RUN/vitest.junit.xml"
if [ "$SCOPE" = "all" ]; then
  run "frontend build"   "$APP/frontend" sum_build     npm run build
fi

T1="$(now_ms)"
total="$(fmt_ms $((T1 - T0)))"
ln -sfn "$RUN" "$LOGROOT/latest"
# 古い実行ディレクトリを削除して最新 10 回分だけ残す
ls -1d "$LOGROOT"/[0-9]* 2>/dev/null | sort -r | tail -n +11 | while IFS= read -r old; do rm -rf "$old"; done

if [ "$fail" -eq 0 ]; then
  printf 'verify: %sPASS%s  合計 %s  ログ: %s\n' "$C_OK" "$C_0" "$total" "$RUN"
else
  printf 'verify: %sFAIL%s  合計 %s  失敗:%s  ログ: %s\n' "$C_NG" "$C_0" "$total" "$failed" "$RUN"
fi
exit "$fail"
