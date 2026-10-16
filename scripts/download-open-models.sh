#!/usr/bin/env bash
set -euo pipefail

COMFY_ROOT="${COMFYUI_ROOT:-/work/comfyui/main}"

download() {
  local url="$1"
  local target="$2"
  mkdir -p "$(dirname "$target")"
  if [[ -s "$target" ]]; then
    echo "[skip] $target"
  else
    echo "[download] $target"
    curl --fail --location --retry 3 --continue-at - --output "$target" "$url"
  fi
}

download "https://huggingface.co/guoyww/animatediff/resolve/main/mm_sd_v15_v2.ckpt" \
  "$COMFY_ROOT/models/animatediff_models/mm_sd_v15_v2.ckpt"
download "https://huggingface.co/h94/IP-Adapter/resolve/main/models/ip-adapter-plus_sd15.safetensors" \
  "$COMFY_ROOT/models/ipadapter/ip-adapter-plus_sd15.safetensors"
download "https://huggingface.co/h94/IP-Adapter/resolve/main/models/image_encoder/model.safetensors" \
  "$COMFY_ROOT/models/clip_vision/CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors"
download "https://huggingface.co/lllyasviel/ControlNet-v1-1/resolve/main/control_v11p_sd15_openpose.pth" \
  "$COMFY_ROOT/models/controlnet/control_v11p_sd15_openpose.pth"
download "https://huggingface.co/lllyasviel/ControlNet-v1-1/resolve/main/control_v11p_sd15_openpose.yaml" \
  "$COMFY_ROOT/models/controlnet/control_v11p_sd15_openpose.yaml"

cat <<'EOF'
开放模型下载完成。
MeinaMix 不由本脚本自动下载：请确认模型页许可后，将 V11 文件放到：
  /work/comfyui/main/models/checkpoints/meinamix_meinaV11.safetensors
若实际文件名不同，请改名，或同步修改 workflows/api/*.json 中的 ckpt_name。
EOF
