#!/usr/bin/env bash
# Show whether schedule + telegram are running.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

check_pidfile() {
  local name="$1"
  local pidfile="$ROOT/logs/${name}.pid"
  if [[ -f "$pidfile" ]] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
    echo "$name: running (pid $(cat "$pidfile"))"
  else
    echo "$name: stopped"
  fi
}

check_pidfile schedule
check_pidfile telegram

if [[ -x "/egr/research-dselab/hepengf1/anaconda3/envs/stock/bin/stock-helper" ]]; then
  /egr/research-dselab/hepengf1/anaconda3/envs/stock/bin/stock-helper status
elif command -v stock-helper >/dev/null 2>&1; then
  stock-helper status
fi
