#!/usr/bin/env bash
# Start stock-helper scheduler (daily brief) + Telegram bot.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Prefer conda env "stock"; override with STOCK_HELPER_PYTHON if needed.
if [[ -n "${STOCK_HELPER_PYTHON:-}" ]]; then
  STOCK_HELPER_BIN="$(dirname "$STOCK_HELPER_PYTHON")"
elif [[ -x "/egr/research-dselab/hepengf1/anaconda3/envs/stock/bin/stock-helper" ]]; then
  STOCK_HELPER_BIN="/egr/research-dselab/hepengf1/anaconda3/envs/stock/bin"
else
  STOCK_HELPER_BIN="$(dirname "$(command -v stock-helper)")"
fi

STOCK_HELPER="$STOCK_HELPER_BIN/stock-helper"
mkdir -p "$ROOT/logs"

# On NFS, deleting logs while a process is running leaves .nfs* stubs — stop orphans first.
if pgrep -f "stock-helper schedule" >/dev/null 2>&1 || pgrep -f "stock-helper telegram" >/dev/null 2>&1; then
  if [[ -f "$ROOT/logs/schedule.pid" ]] && kill -0 "$(cat "$ROOT/logs/schedule.pid")" 2>/dev/null \
     && [[ -f "$ROOT/logs/telegram.pid" ]] && kill -0 "$(cat "$ROOT/logs/telegram.pid")" 2>/dev/null; then
    echo "schedule + telegram already running"
    echo "Stop first: $ROOT/scripts/stop.sh"
    exit 0
  fi
  echo "Cleaning up orphaned stock-helper processes..."
  pkill -f "stock-helper schedule" 2>/dev/null || true
  pkill -f "stock-helper telegram" 2>/dev/null || true
  rm -f "$ROOT/logs/schedule.pid" "$ROOT/logs/telegram.pid"
  sleep 1
fi

if [[ ! -x "$STOCK_HELPER" ]]; then
  echo "stock-helper not found. Install with: conda activate stock && pip install -e ."
  exit 1
fi

if [[ -f "$ROOT/logs/schedule.pid" ]] && kill -0 "$(cat "$ROOT/logs/schedule.pid")" 2>/dev/null; then
  echo "schedule already running (pid $(cat "$ROOT/logs/schedule.pid"))"
else
  nohup "$STOCK_HELPER" schedule >> "$ROOT/logs/schedule.log" 2>&1 &
  echo $! > "$ROOT/logs/schedule.pid"
  echo "started schedule (pid $(cat "$ROOT/logs/schedule.pid"))"
fi

if [[ -f "$ROOT/logs/telegram.pid" ]] && kill -0 "$(cat "$ROOT/logs/telegram.pid")" 2>/dev/null; then
  echo "telegram already running (pid $(cat "$ROOT/logs/telegram.pid"))"
else
  nohup "$STOCK_HELPER" telegram >> "$ROOT/logs/telegram.log" 2>&1 &
  echo $! > "$ROOT/logs/telegram.pid"
  echo "started telegram (pid $(cat "$ROOT/logs/telegram.pid"))"
fi

echo ""
echo "Logs:"
echo "  tail -f $ROOT/logs/schedule.log"
echo "  tail -f $ROOT/logs/telegram.log"
echo ""
echo "Stop: $ROOT/scripts/stop.sh"
