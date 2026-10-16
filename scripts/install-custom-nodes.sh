#!/usr/bin/env bash
set -euo pipefail

COMFY_ROOT="${COMFYUI_ROOT:-/work/comfyui/main}"
CUSTOM_ROOT="$COMFY_ROOT/custom_nodes"
mkdir -p "$CUSTOM_ROOT"

CONDA_BIN="${COMFYUI_CONDA_BIN:-$(type -P conda 2>/dev/null || true)}"
for candidate in \
  "$CONDA_BIN" \
  "${CONDA_EXE:-}" \
  "$HOME/miniconda3/bin/conda" \
  "$HOME/anaconda3/bin/conda" \
  "/opt/conda/bin/conda"; do
  if [[ -n "$candidate" && -x "$candidate" ]]; then
    CONDA_BIN="$candidate"
    break
  fi
done
if [[ -z "$CONDA_BIN" || ! -x "$CONDA_BIN" ]]; then
  echo "找不到 conda；请设置 COMFYUI_CONDA_BIN=/conda/绝对路径/bin/conda" >&2
  exit 1
fi

install_repo() {
  local name="$1"
  local url="$2"
  local target="$CUSTOM_ROOT/$name"
  if [[ -d "$target/.git" ]]; then
    echo "[skip] $name 已存在；为避免升级破坏现有工作流，不自动 git pull"
    return
  fi
  if [[ -e "$target" ]]; then
    echo "[error] $target 已存在但不是 Git 仓库，请人工检查" >&2
    exit 1
  fi
  git clone --depth 1 "$url" "$target"
  if [[ -f "$target/requirements.txt" ]]; then
    "$CONDA_BIN" run -n comfyui python -m pip install -r "$target/requirements.txt"
  fi
}

install_repo "ComfyUI-AnimateDiff-Evolved" "https://github.com/Kosinkadink/ComfyUI-AnimateDiff-Evolved.git"
install_repo "ComfyUI-VideoHelperSuite" "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git"
install_repo "ComfyUI_IPAdapter_plus" "https://github.com/cubiq/ComfyUI_IPAdapter_plus.git"
install_repo "comfyui_controlnet_aux" "https://github.com/Fannovel16/comfyui_controlnet_aux.git"

echo "节点安装完成。请重启 ComfyUI，再运行 scripts/doctor.sh。"
