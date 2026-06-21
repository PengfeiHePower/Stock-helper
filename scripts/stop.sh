#!/usr/bin/env bash
# Stop stock-helper scheduler + Telegram bot.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

stop_pidfile() {
  local name="$1"
  local pidfile="$ROOT/logs/${name}.pid"
  if [[ ! -f "$pidfile" ]]; then
    echo "$name: not running (no pid file)"
    return 0
  fi
  local pid
  pid="$(cat "$pidfile")"
  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid"
    echo "stopped $name (pid $pid)"
  else
    echo "$name: stale pid file (pid $pid not running)"
  fi
  rm -f "$pidfile"
}

stop_pidfile schedule
stop_pidfile telegram

# Fallback: kill any leftover processes started from this project
pkill -f "$ROOT.*stock-helper schedule" 2>/dev/null || true
pkill -f "$ROOT.*stock-helper telegram" 2>/dev/null || true

echo "done"
