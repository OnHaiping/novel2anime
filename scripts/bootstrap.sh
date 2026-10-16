#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
[[ -f .env ]] || cp .env.example .env
mkdir -p data/projects data/motion_library outputs
docker compose pull
docker compose build
echo "初始化完成。先执行 scripts/start-comfyui.sh，再执行 docker compose up -d。"

