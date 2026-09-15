#!/usr/bin/env bash
# 差分レビューを Codex に依頼する。書き手とは別の使い捨てコンテキスト・read-only。
# 使い方: .claude/scripts/review.sh <ベースブランチ> <受入条件の文字列 or ファイル>
# 判定: 標準出力の先頭行が VERDICT: OK か VERDICT: BLOCK。BLOCK なら exit 1。
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BASE="${1:?ベースブランチを指定してください (例: feature/kimura)}"
CRITERIA="${2:?受入条件を指定してください}"
[ -f "$CRITERIA" ] && CRITERIA="$(cat "$CRITERIA")"
STAMP="$(date +%Y%m%d-%H%M%S)"
LOGDIR="$ROOT/.claude/logs"; mkdir -p "$LOGDIR"
OUT="$LOGDIR/$STAMP.review.md"

DIFF_STAT="$(git -C "$ROOT" diff --stat "$BASE"...HEAD)"
[ -n "$DIFF_STAT" ] || { echo "VERDICT: OK (差分なし)"; exit 0; }

PROMPT="あなたはコードレビュアーです。以下の差分だけを見て判定してください。

## 報告してよいもの（これ以外は報告しない）
- 正しさの誤り（バグ、境界条件、数値の誤り、競合状態、例外の握り潰し）
- 下の受入条件への違反
- 明らかなセキュリティ上の問題

## 報告してはいけないもの
- スタイル・命名・書き方の好み
- 「念のため」の防御的コードやテストの追加提案
- 起こり得ないケースへの対処提案
指摘が思いつかない場合は、無理に作らず OK と判定してください。

## 受入条件
$CRITERIA

## 出力形式（厳守）
1 行目に VERDICT: OK または VERDICT: BLOCK。
BLOCK の場合のみ、以降に指摘を列挙する。各指摘は次の 3 行:
- file:line
- 何が起きるか（具体的な入力と結果）
- どう直すか（1 文）

## 差分の範囲
$DIFF_STAT

差分の中身は 'git diff $BASE...HEAD' で確認してください。必要ならリポジトリ内のファイルを読んで構いません。コードは変更しないでください。"

codex exec --skip-git-repo-check -C "$ROOT" -m gpt-6-astra -c model_reasoning_effort=high \
  -s read-only -o "$OUT" "$PROMPT" < /dev/null > "$LOGDIR/$STAMP.review.log" 2>&1 || {
    echo "review: codex exec failed (log: $LOGDIR/$STAMP.review.log)"; exit 2; }

cat "$OUT"
head -1 "$OUT" | grep -q "VERDICT: OK" && exit 0 || exit 1
