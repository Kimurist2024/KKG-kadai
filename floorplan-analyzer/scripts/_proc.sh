# 起動・停止スクリプト共通のプロセス操作。source して使う。macOS 既定の bash 3.2 でも動く書き方にしている。
# 「このアプリのディレクトリで動いているもの」だけを対象にし、他のプロジェクトのプロセスには触れない。

# pid の全子孫を、深い方から順に列挙する（pid 自身は含まない）
proc_descendants() { # proc_descendants <pid>
  local parent="$1" child
  for child in $(ps -eo pid=,ppid= | awk -v p="$parent" '$2 == p { print $1 }'); do
    proc_descendants "$child"
    echo "$child"
  done
}

# プロセスの作業ディレクトリ（取得できなければ空）
proc_cwd() { lsof -a -p "$1" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p'; }

# TERM を送り、grace 秒たっても残っているものだけ KILL する。
# next dev の親プロセスは SIGTERM で終わらないことがあり、待ち続けると古い起動が溜まる。
proc_stop() { # proc_stop <grace 秒> <pid>...
  local grace="$1" waited=0 alive p
  shift
  [ "$#" -gt 0 ] || return 0
  kill -TERM "$@" 2>/dev/null || true
  while [ "$waited" -lt $((grace * 10)) ]; do
    alive=0
    for p in "$@"; do if kill -0 "$p" 2>/dev/null; then alive=1; fi; done
    [ "$alive" -eq 0 ] && return 0
    sleep 0.1
    waited=$((waited + 1))
  done
  for p in "$@"; do if kill -0 "$p" 2>/dev/null; then kill -KILL "$p" 2>/dev/null || true; fi; done
  return 0
}

# pid とその子孫をまとめて止める
proc_stop_tree() { # proc_stop_tree <grace 秒> <pid>
  local grace="$1" root="$2" tree
  tree="$(proc_descendants "$root")"
  # shellcheck disable=SC2086
  proc_stop "$grace" $tree "$root"
}

# 前回の start.sh を子孫ごと止める。旧版の終了処理は wait で固まるため、trap を走らせないよう親は KILL し、
# 先に列挙しておいた子孫を TERM → KILL で止める。
proc_stop_start_instance() { # proc_stop_start_instance <grace 秒> <start.sh の pid>
  local grace="$1" root="$2" tree
  tree="$(proc_descendants "$root")"
  kill -KILL "$root" 2>/dev/null || true
  # shellcheck disable=SC2086
  proc_stop "$grace" $tree
}

# このアプリで動いている別の start.sh の pid（自分自身・自分の祖先・自分の子孫は除く）
# ps のコマンド文字列は、空白を含むパスで起動されると途中で分断されるので照合に使わない。
# シェルのプロセスに絞ったうえで、(1) 作業ディレクトリがこのアプリ、(2) このアプリの scripts/start.sh を
# 開いている（bash は実行中のスクリプトを開いたままにする）ことで判定する。
proc_other_starts() { # proc_other_starts <アプリの絶対パス>
  local app="$1" pid skip=" " p=$$
  while [ -n "$p" ] && [ "$p" -gt 1 ]; do
    skip="$skip$p "
    p="$(ps -o ppid= -p "$p" 2>/dev/null | tr -d ' ')"
  done
  for pid in $(proc_descendants $$); do skip="$skip$pid "; done
  for pid in $(ps -eo pid=,comm= | awk '$2 ~ /(^|\/)-?(ba)?sh$/ { print $1 }'); do
    case "$skip" in *" $pid "*) continue ;; esac
    [ "$(proc_cwd "$pid")" = "$app" ] || continue
    if lsof -a -p "$pid" -Fn 2>/dev/null | grep -qxF "n$app/scripts/start.sh"; then echo "$pid"; fi
  done
}

# 親の start.sh を失って残った next / uvicorn（作業ディレクトリがこのアプリ配下で、親が init のもの）
proc_orphans() { # proc_orphans <アプリの絶対パス>
  local app="$1" pid
  for pid in $(ps -eo pid=,ppid=,command= | awk '$2 == 1 && ($0 ~ /next dev|next-server|uvicorn app\.main/) { print $1 }'); do
    case "$(proc_cwd "$pid")" in "$app"|"$app"/*) echo "$pid" ;; esac
  done
}
