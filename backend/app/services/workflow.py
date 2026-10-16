from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from ..config import get_settings
from ..models import Character, MotionAsset, Shot


REGISTRY = {
    "02": {
        "file": "api/02_environment_api.json",
        "positive": "2",
        "negative": "3",
        "latent": "8",
        "sampler": "9",
        "output": "11",
    },
    "03": {
        "file": "api/03_character_free_motion_api.json",
        "positive": "2",
        "negative": "3",
        "reference": "8",
        "ipadapter": "9",
        "latent": "11",
        "sampler": "12",
        "output": "14",
    },
    "04": {
        "file": "api/04_character_openpose_api.json",
        "positive": "2",
        "negative": "3",
        "reference": "8",
        "ipadapter": "9",
        "driver": "11",
        "controlnet_apply": "14",
        "latent": "15",
        "sampler": "16",
        "output": "18",
    },
}


class WorkflowBuilder:
    def __init__(self) -> None:
        self.settings = get_settings()

    def build(
        self,
        shot: Shot,
        characters: list[Character],
        motion_asset: MotionAsset | None,
        reference_image_name: str | None = None,
        driver_video_name: str | None = None,
    ) -> dict[str, Any]:
        key = shot.workflow_key
        if key == "04" and motion_asset is None and not driver_video_name:
            key = "03" if characters else "02"
        if key == "03" and not characters:
            key = "02"
        spec = REGISTRY[key]
        path = self.settings.workflow_root / spec["file"]
        workflow = json.loads(path.read_text(encoding="utf-8"))
        prompt = copy.deepcopy(workflow)

        prompt[spec["positive"]]["inputs"]["text"] = shot.positive_prompt
        prompt[spec["negative"]]["inputs"]["text"] = shot.negative_prompt
        prompt[spec["latent"]]["inputs"].update(
            {"width": shot.width, "height": shot.height, "batch_size": shot.frames}
        )
        prompt[spec["sampler"]]["inputs"]["seed"] = shot.seed
        prompt[spec["output"]]["inputs"]["frame_rate"] = shot.fps
        prompt[spec["output"]]["inputs"]["filename_prefix"] = (
            f"novel2anime/{shot.project_id}/{shot.code}"
        )

        if key in {"03", "04"}:
            reference = reference_image_name or characters[0].reference_image
            if not reference:
                raise ValueError(f"镜头 {shot.code} 缺少角色参考图")
            prompt[spec["reference"]]["inputs"]["image"] = Path(reference).name
            weight = characters[0].default_ipadapter_weight
            prompt[spec["ipadapter"]]["inputs"]["weight"] = (
                weight if key == "03" else min(weight, 0.55)
            )

        if key == "04":
            driver = driver_video_name or (
                motion_asset.source_file if motion_asset else None
            )
            if not driver:
                raise ValueError(f"镜头 {shot.code} 缺少动作指导视频")
            prompt[spec["driver"]]["inputs"].update(
                {
                    "video": Path(driver).name,
                    "frame_load_cap": shot.frames,
                    "force_rate": shot.fps,
                }
            )
        return prompt


def validate_api_workflow(workflow: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for node_id, node in workflow.items():
        if not isinstance(node, dict):
            errors.append(f"节点 {node_id} 不是对象")
            continue
        if "class_type" not in node:
            errors.append(f"节点 {node_id} 缺少 class_type")
        if "inputs" not in node:
            errors.append(f"节点 {node_id} 缺少 inputs")
    return errors
