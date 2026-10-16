#!/usr/bin/env bash
set -euo pipefail

COMFY_ROOT="${COMFYUI_ROOT:-/work/comfyui/main}"
LOG_DIR="${COMFYUI_LOG_DIR:-$COMFY_ROOT/logs}"

for pid_file in "$LOG_DIR"/gpu*.pid; do
  [[ -e "$pid_file" ]] || continue
  pid="$(cat "$pid_file")"
  if kill -0 "$pid" 2>/dev/null; then
    echo "停止 PID $pid"
    kill "$pid"
  fi
  rm -f "$pid_file"
done

