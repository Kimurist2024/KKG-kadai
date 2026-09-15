#!/usr/bin/env bash
# サイクル開始: feature/kimura の最新から作業ブランチを切る。
# 使い方: .claude/scripts/cycle-start.sh <話題(英小文字とハイフン)>
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"; cd "$ROOT"
TOPIC="${1:?話題を指定してください 例: backend-test-layout}"
BASE=feature/kimura
[ -z "$(git status --porcelain)" ] || { echo "未コミットの変更があります。先に片付けてください"; git status --short; exit 1; }
git fetch -q origin "$BASE"
git switch -q -C "work/$TOPIC" "origin/$BASE"
echo "作業ブランチ: work/$TOPIC (基点: origin/$BASE)"
