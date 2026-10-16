from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..config import get_settings
from ..models import Character
from .prompt_builder import BASE_NEGATIVE, BASE_POSITIVE


def _load(name: str) -> dict[str, Any]:
    path = get_settings().workflow_root / "api" / name
    return json.loads(path.read_text(encoding="utf-8"))


def build_portrait_workflow(
    character: Character, request: dict[str, Any]
) -> dict[str, Any]:
    workflow = _load("01_character_portrait_api.json")
    positive = ", ".join(
        value
        for value in [
            BASE_POSITIVE,
            "anime character reference sheet, solo, full body, front view, simple background",
            character.description,
            character.positive_prompt,
            request.get("extra_prompt", ""),
        ]
        if value
    )
    negative = ", ".join(
        value for value in [BASE_NEGATIVE, character.negative_prompt] if value
    )
    workflow["2"]["inputs"]["text"] = positive
    workflow["3"]["inputs"]["text"] = negative
    workflow["4"]["inputs"].update(
        {"width": request.get("width", 512), "height": request.get("height", 768)}
    )
    workflow["5"]["inputs"]["seed"] = request.get("seed", 10001)
    workflow["7"]["inputs"]["filename_prefix"] = (
        f"novel2anime/{character.project_id}/portraits/{character.id}"
    )
    return workflow


def build_motion_workflow(request: dict[str, Any]) -> dict[str, Any]:
    workflow = _load("05_motion_draft_api.json")
    workflow["2"]["inputs"]["text"] = ", ".join(
        [
            BASE_POSITIVE,
            "anime animation, single adult character, full body visible, fixed camera",
            request["prompt"],
            request["action"],
        ]
    )
    workflow["3"]["inputs"]["text"] = BASE_NEGATIVE + ", cropped body, multiple people"
    workflow["9"]["inputs"]["seed"] = request.get("seed", 10001)
    safe_id = Path(request["motion_id"]).name
    workflow["11"]["inputs"]["filename_prefix"] = f"novel2anime/motion_drafts/{safe_id}"
    return workflow
