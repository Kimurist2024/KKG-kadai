#!/usr/bin/env bash
# サイクル完了: 検証 → コミット → push → PR → Codex レビュー → 合格なら feature/kimura にマージ。
# main には一切触れない。
# 使い方: .claude/scripts/cycle-finish.sh "<コミット件名>" "<受入条件 or 受入条件ファイル>"
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"; cd "$ROOT"
SUBJECT="${1:?コミット件名を指定してください}"
CRITERIA="${2:?受入条件を指定してください}"
[ -f "$CRITERIA" ] && CRITERIA="$(cat "$CRITERIA")"
BASE=feature/kimura
BRANCH="$(git branch --show-current)"
case "$BRANCH" in work/*) ;; *) echo "work/* ブランチで実行してください (現在: $BRANCH)"; exit 1;; esac
# shellcheck source=/dev/null
. "$ROOT/.claude/scripts/gh-env.sh"

echo "== 1. 検証ゲート =="
"$ROOT/.claude/scripts/verify.sh" || { echo "verify が不合格です。マージしません"; exit 1; }

echo "== 2. コミットと push =="
git add -A
if git diff --cached --quiet; then
  # 新しい変更なし。push 失敗などからの再実行に備え、既存のコミットで続行する
  AHEAD="$(git rev-list --count "origin/$BASE..HEAD")"
  [ "$AHEAD" -gt 0 ] || { echo "$BASE との差分がありません"; exit 1; }
  echo "新しい変更はありません。コミット済みの $AHEAD 件で続行します"
else
git commit -q -F - <<COMMIT
$SUBJECT

受入条件:
$CRITERIA

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
COMMIT
fi
git push -q -u origin "$BRANCH"

echo "== 3. PR 作成 =="
EXISTING="$(gh pr view "$BRANCH" --json url,baseRefName,state -q '.state+" "+.baseRefName+" "+.url' 2>/dev/null || true)"
PR=""
if [ -n "$EXISTING" ]; then
  read -r PR_STATE PR_BASE PR_URL <<<"$EXISTING"
  # 別の宛先 (特に main) の PR を無検証で再利用してマージしない
  [ "$PR_BASE" = "$BASE" ] || { echo "既存 PR のマージ先が $PR_BASE です ($BASE ではありません): $PR_URL"; echo "この PR は使いません。閉じるかマージ先を変更してください"; exit 1; }
  [ "$PR_STATE" = "OPEN" ] || { echo "既存 PR が $PR_STATE です: $PR_URL"; exit 1; }
  PR="$PR_URL"
fi
if [ -z "$PR" ]; then
  PR="$(gh pr create --base "$BASE" --head "$BRANCH" --title "$SUBJECT" \
        --body "## 受入条件
$CRITERIA

## 検証
\`.claude/scripts/verify.sh\` が exit 0 (pytest / typecheck / vitest / build)。

マージ先は \`$BASE\`。\`main\` への反映は動作確認後に手動で行う。")"
fi
echo "PR: $PR"

echo "== 4. Codex レビュー =="
set +e
REVIEW="$("$ROOT/.claude/scripts/review.sh" "origin/$BASE" "$CRITERIA")"
RC=$?
set -e
printf '%s\n' "$REVIEW"
gh pr comment "$BRANCH" --body "## Codex レビュー結果

\`\`\`
$REVIEW
\`\`\`" >/dev/null || { echo "レビュー結果を PR に記録できませんでした。記録なしでマージしません"; exit 1; }
[ "$RC" -eq 0 ] || { echo "レビューが BLOCK です。修正して再実行してください。マージしません"; exit 1; }

echo "== 5. マージ ($BASE) =="
gh pr merge "$BRANCH" --squash --delete-branch
git switch -q "$BASE" 2>/dev/null || git switch -q -c "$BASE" "origin/$BASE"
git pull -q --ff-only origin "$BASE"
echo "完了: $BASE にマージしました。main には反映していません"
