#!/usr/bin/env bash
set -euo pipefail

API_URL="${NOVEL2ANIME_API:-http://127.0.0.1:8000}"
curl -fsS "$API_URL/api/system/diagnostics" | python -m json.tool

