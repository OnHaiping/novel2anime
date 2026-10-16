from __future__ import annotations

from typing import Any

from ..config import get_settings


MODEL_CATALOG: dict[str, dict[str, str]] = {
    "animatediff_v2": {
        "name": "AnimateDiff SD1.5 v2",
        "url": "https://huggingface.co/guoyww/animatediff/resolve/main/mm_sd_v15_v2.ckpt",
        "target": "models/animatediff_models/mm_sd_v15_v2.ckpt",
    },
    "ipadapter_plus_sd15": {
        "name": "IP-Adapter Plus SD1.5",
        "url": "https://huggingface.co/h94/IP-Adapter/resolve/main/models/ip-adapter-plus_sd15.safetensors",
        "target": "models/ipadapter/ip-adapter-plus_sd15.safetensors",
    },
    "clip_vision_h": {
        "name": "CLIP Vision ViT-H",
        "url": "https://huggingface.co/h94/IP-Adapter/resolve/main/models/image_encoder/model.safetensors",
        "target": "models/clip_vision/CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors",
    },
    "controlnet_openpose": {
        "name": "ControlNet SD1.5 OpenPose",
        "url": "https://huggingface.co/lllyasviel/ControlNet-v1-1/resolve/main/control_v11p_sd15_openpose.pth",
        "target": "models/controlnet/control_v11p_sd15_openpose.pth",
    },
    "controlnet_openpose_config": {
        "name": "ControlNet OpenPose Config",
        "url": "https://huggingface.co/lllyasviel/ControlNet-v1-1/resolve/main/control_v11p_sd15_openpose.yaml",
        "target": "models/controlnet/control_v11p_sd15_openpose.yaml",
    },
}


def catalog_status() -> list[dict[str, Any]]:
    root = get_settings().comfyui_root.resolve()
    result = []
    for key, item in MODEL_CATALOG.items():
        path = (root / item["target"]).resolve()
        if root not in path.parents:
            continue
        result.append(
            {
                "key": key,
                **item,
                "path": str(path),
                "exists": path.is_file(),
                "size": path.stat().st_size if path.is_file() else 0,
            }
        )
    return result
