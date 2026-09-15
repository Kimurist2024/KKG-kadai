# gh / GitHub API 用のトークンを macOS キーチェーンの git 資格情報から取り出す。
# 使い方: source .claude/scripts/gh-env.sh
export PATH="$HOME/.local/bin:$PATH"
GH_TOKEN="$(printf 'protocol=https\nhost=github.com\n\n' | git credential fill 2>/dev/null | awk -F= '/^password=/{print $2}')"
export GH_TOKEN
[ -n "${GH_TOKEN:-}" ] || { echo "GitHub トークンを取得できません。git credential の設定を確認してください" >&2; return 1 2>/dev/null || exit 1; }
