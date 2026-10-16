#!/usr/bin/env bash
set -euo pipefail

COMFY_ROOT="${COMFYUI_ROOT:-/work/comfyui/main}"
CONDA_ENV="${COMFYUI_CONDA_ENV:-comfyui}"
LOG_DIR="${COMFYUI_LOG_DIR:-$COMFY_ROOT/logs}"
MODE="${1:-dual}"

mkdir -p "$LOG_DIR"
cd "$COMFY_ROOT"

start_one() {
  local gpu="$1"
  local port="$2"
  local name="gpu${gpu}"
  local pid_file="$LOG_DIR/${name}.pid"
  local log_file="$LOG_DIR/${name}.log"

  if [[ -f "$pid_file" ]] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
    echo "$name 已运行，PID $(cat "$pid_file")，端口 $port"
    return
  fi

  echo "启动 $name：CUDA_VISIBLE_DEVICES=$gpu，端口 $port"
  nohup env CUDA_VISIBLE_DEVICES="$gpu" conda run -n "$CONDA_ENV" --no-capture-output \
    python main.py --enable-manager --listen 0.0.0.0 --port "$port" \
    >>"$log_file" 2>&1 &
  echo $! >"$pid_file"
}

if [[ "$MODE" == "single" ]]; then
  start_one 0 8188
else
  start_one 0 8188
  start_one 1 8189
fi

echo "日志目录：$LOG_DIR"

