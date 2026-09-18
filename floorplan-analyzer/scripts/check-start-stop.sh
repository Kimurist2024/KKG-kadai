#!/usr/bin/env bash
# start.sh / stop.sh が古いプロセスを残さないことを確かめる回帰チェック。exit 0 = 合格、1 = 不合格。
# 本物のサーバーは使わない。一時ディレクトリにスタブのアプリを作り、本物と同じ癖（next dev の親は SIGTERM で
# 終わらず、子のサーバーだけが終わる）を再現して、次の 3 場面で残骸が出ないことを数える。
# 一時ディレクトリは空白を含むパスにし、相対パスでの起動と、別の場所からの絶対パスでの起動の両方を試す。
#   1. 起動し直し（start.sh を続けて 2 回）  2. 最新の start.sh の終了（Ctrl+C と同じ終了処理）  3. stop.sh
# 使うポートは CHECK_BACK_PORT / CHECK_FRONT_PORT（既定 8010 / 5183）。開発中の 8000 / 5173 には触れない。
set -u
SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd -P)"
TMP_ROOT="$(cd "$(mktemp -d)" && pwd -P)"
FAKE="$TMP_ROOT/fake app"   # 空白を含むパスでも前回の start.sh を検出できることを確かめる
mkdir -p "$FAKE"
export BACK_PORT="${CHECK_BACK_PORT:-8010}" FRONT_PORT="${CHECK_FRONT_PORT:-5183}" READY_TIMEOUT=15 STOP_GRACE=2
fail=0

under_fake() { local c; c=$(lsof -a -p "$1" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p'); case "$c" in "$FAKE"|"$FAKE"/*) return 0 ;; *) return 1 ;; esac; }
mine() { ps -eo pid=,command= | grep -E "scripts/start\.sh|\.bin/next|uvicorn|stub-server\.py" | grep -v grep | while read -r pid cmd; do if under_fake "$pid"; then echo "$pid $cmd"; fi; done; }
count() { mine | grep -cE "$1" || true; }
finish() { mine | awk '{ print $1 }' | while read -r p; do kill -KILL "$p" 2>/dev/null; done; rm -rf "$TMP_ROOT"; }
trap finish EXIT
expect() { # expect <説明> <実際> <期待>
  if [ "$2" = "$3" ]; then echo "  OK   $1: $2"; else echo "  FAIL $1: ${2}（期待 ${3}）"; mine | sed 's/^/         残り: /' | cut -c1-110; fail=1; fi
}

mkdir -p "$FAKE/scripts" "$FAKE/backend/.venv/bin" "$FAKE/frontend/node_modules/.bin"
cp "$SCRIPTS_DIR/start.sh" "$SCRIPTS_DIR/stop.sh" "$SCRIPTS_DIR/_proc.sh" "$FAKE/scripts/"
cat > "$FAKE/stub-server.py" <<'PY'
import http.server, signal, sys
signal.signal(signal.SIGTERM, signal.SIG_DFL)   # 親が TERM を無視していても、子（next-server 役）は TERM で終わる
class H(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b'{"status":"ok"}')
    def log_message(self, *a): pass
http.server.HTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
PY
cat > "$FAKE/backend/.venv/bin/uvicorn" <<STUB
#!/usr/bin/env bash
port=8000; while [ \$# -gt 0 ]; do [ "\$1" = "--port" ] && port="\$2"; shift; done
exec python3 "$FAKE/stub-server.py" "\$port"
STUB
cat > "$FAKE/frontend/node_modules/.bin/next" <<STUB
#!/usr/bin/env bash
trap '' TERM    # 本物の next dev の親と同じく、SIGTERM では終わらない
port=3000; while [ \$# -gt 0 ]; do [ "\$1" = "--port" ] && port="\$2"; shift; done
python3 "$FAKE/stub-server.py" "\$port" &
wait \$!
while :; do sleep 60; done
STUB
chmod +x "$FAKE/backend/.venv/bin/uvicorn" "$FAKE/frontend/node_modules/.bin/next"

launch() { # launch <ログ名> [absolute]   absolute: 別の作業ディレクトリから絶対パスで起動する
  if [ "${2:-}" = absolute ]; then
    ( cd / && nohup bash "$FAKE/scripts/start.sh" > "$FAKE/$1.log" 2>&1 & ) 2>/dev/null
  else
    ( cd "$FAKE" && nohup bash ./scripts/start.sh > "$FAKE/$1.log" 2>&1 & ) 2>/dev/null
  fi
  local i=0
  while [ "$i" -lt 200 ]; do if grep -q "起動完了" "$FAKE/$1.log" 2>/dev/null; then return 0; fi; sleep 0.1; i=$((i + 1)); done
  echo "  FAIL $1 が起動完了しませんでした"; tail -3 "$FAKE/$1.log" | sed 's/^/         /'; fail=1; return 1
}

echo "check-start-stop（ポート $BACK_PORT / ${FRONT_PORT}、一時ディレクトリ ${FAKE}）"
launch first && launch second absolute; sleep 1
expect "起動し直し後の start.sh の数" "$(count 'scripts/start\.sh')" 1
expect "起動し直し後の next dev 役の数" "$(count '\.bin/next')" 1
latest="$(mine | awk '/scripts\/start\.sh/ { print $1 }' | tail -1)"
# 非対話シェルから & で起動したプロセスは SIGINT が無視されるため、同じ終了処理を通る SIGTERM で確かめる
kill -TERM "$latest" 2>/dev/null; sleep $((STOP_GRACE + 3))
expect "start.sh 終了後に残ったプロセス" "$(mine | wc -l | tr -d ' ')" 0
launch third absolute; sleep 1
( cd / && bash "$FAKE/scripts/stop.sh" ) > "$FAKE/stop.log" 2>&1; sleep 1
expect "stop.sh 後に残ったプロセス" "$(mine | wc -l | tr -d ' ')" 0
expect "stop.sh 後にポートを握るプロセス" "$( { lsof -tiTCP:"$BACK_PORT" -sTCP:LISTEN; lsof -tiTCP:"$FRONT_PORT" -sTCP:LISTEN; } 2>/dev/null | wc -l | tr -d ' ')" 0
if [ "$fail" -eq 0 ]; then echo "check-start-stop: PASS"; else echo "check-start-stop: FAIL"; fi
exit "$fail"
