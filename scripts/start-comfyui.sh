#!/usr/bin/env bash
set -euo pipefail

COMFY_ROOT="${COMFYUI_ROOT:-/work/comfyui/main}"
CONDA_ENV="${COMFYUI_CONDA_ENV:-comfyui}"
LOG_DIR="${COMFYUI_LOG_DIR:-$COMFY_ROOT/logs}"
MODE="${1:-dual}"

find_conda() {
  if [[ -n "${COMFYUI_CONDA_BIN:-}" && -x "$COMFYUI_CONDA_BIN" ]]; then
    printf '%s\n' "$COMFYUI_CONDA_BIN"
    return
  fi

  local path_candidate
  path_candidate="$(type -P conda 2>/dev/null || true)"
  if [[ -n "$path_candidate" ]]; then
    printf '%s\n' "$path_candidate"
    return
  fi

  for path_candidate in \
    "${CONDA_EXE:-}" \
    "$HOME/miniconda3/bin/conda" \
    "$HOME/anaconda3/bin/conda" \
    "/opt/conda/bin/conda" \
    "/usr/local/miniconda3/bin/conda" \
    "/usr/local/anaconda3/bin/conda"; do
    if [[ -n "$path_candidate" && -x "$path_candidate" ]]; then
      printf '%s\n' "$path_candidate"
      return
    fi
  done

  echo "找不到 conda。请先执行 source ~/.bashrc，或设置 COMFYUI_CONDA_BIN=/conda/绝对路径/bin/conda" >&2
  return 1
}

CONDA_BIN="$(find_conda)"

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
  nohup env CUDA_VISIBLE_DEVICES="$gpu" "$CONDA_BIN" run -n "$CONDA_ENV" --no-capture-output \
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

echo "Conda：$CONDA_BIN"
echo "日志目录：$LOG_DIR"

