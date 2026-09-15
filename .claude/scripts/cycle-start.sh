#!/usr/bin/env bash
# サイクル開始: feature/kimura の最新から作業ブランチを切る。
# 使い方: .claude/scripts/cycle-start.sh <話題(英小文字とハイフン)>
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"; cd "$ROOT"
TOPIC="${1:?話題を指定してください 例: backend-test-layout}"
BASE=feature/kimura
[ -z "$(git status --porcelain)" ] || { echo "未コミットの変更があります。先に片付けてください"; git status --short; exit 1; }
git fetch -q origin "$BASE"
# 既存ブランチを強制的に基点へ戻すと未マージのコミットが失われるため、上書きしない
if git show-ref --quiet --verify "refs/heads/work/$TOPIC"; then
  echo "ブランチ work/$TOPIC は既に存在します。続きから作業するか、別の話題名にしてください"
  exit 1
fi
git switch -q -c "work/$TOPIC" "origin/$BASE"
echo "作業ブランチ: work/$TOPIC (基点: origin/$BASE)"
