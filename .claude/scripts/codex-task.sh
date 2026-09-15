#!/usr/bin/env bash
# コーディング作業を Codex (gpt-6-astra) に委譲する共通ラッパー。
# 使い方: .claude/scripts/codex-task.sh <作業ディレクトリ> <medium|high> <プロンプト文字列 or プロンプトファイル> [read-only|workspace-write]
# 出力: Codex の最終メッセージだけを表示する (途中経過はログファイルへ)。
set -euo pipefail
DIR="$1"; EFFORT="$2"; PROMPT="$3"; MODE="${4:-workspace-write}"
case "$EFFORT" in medium|high) ;; *) echo "effort は medium か high" >&2; exit 2;; esac
[ -f "$PROMPT" ] && PROMPT="$(cat "$PROMPT")"
STAMP="$(date +%Y%m%d-%H%M%S)"
# ログはプロジェクト内に残す (README に「使用したプロンプト」を記載する課題要件のため)。
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOGDIR="${CODEX_TASK_LOGDIR:-$REPO_ROOT/.claude/logs}"; mkdir -p "$LOGDIR"
LOG="$LOGDIR/$STAMP.log"; OUT="$LOGDIR/$STAMP.last.md"
KADAI="$(cat "$REPO_ROOT/kadai.md")"
PREFIX="## 課題要件（最優先。判断の基準にする）
$KADAI

## 作業制約
ブラウザやネイティブアプリの UI 自動操作 (computer use) は禁止。検証はコード・CLI・テストで行う。
依存ライブラリは追加しない。
完了の申告には必ず、実行したコマンドとその出力を添える。実行していない検証を合格として報告しない。
作業後、最終メッセージに「変更ファイル」「実行したコマンドと結果」「未実施・残る問題」を箇条書きでまとめる。"
codex exec --skip-git-repo-check -C "$DIR" -m gpt-6-astra -c model_reasoning_effort="$EFFORT" \
  -s "$MODE" -o "$OUT" "$PREFIX

$PROMPT" < /dev/null > "$LOG" 2>&1 || { echo "codex exec failed (log: $LOG)"; tail -30 "$LOG"; exit 1; }
echo "--- codex last message (effort=$EFFORT, log=$LOG) ---"
cat "$OUT"
