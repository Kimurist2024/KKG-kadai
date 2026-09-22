#!/usr/bin/env bash
# Compatibility entry point; implementation lives in scripts/.
set -euo pipefail
exec bash "$(dirname "$0")/scripts/stop.sh" "$@"
