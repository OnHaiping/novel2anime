#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "用法：$0 input-video output.mp4" >&2
  exit 2
fi

ffmpeg -y -i "$1" \
  -vf "fps=8,scale=512:512:force_original_aspect_ratio=increase,crop=512:512" \
  -frames:v 16 -an -c:v libx264 -pix_fmt yuv420p "$2"

