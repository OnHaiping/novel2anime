from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from ..config import get_settings
from .comfyui import ComfyUIClient


REQUIRED_MODELS = {
    "checkpoint": "models/checkpoints/meinamix_meinaV11.safetensors",
    "motion_module": "models/animatediff_models/mm_sd_v15_v2.ckpt",
    "ipadapter": "models/ipadapter/ip-adapter-plus_sd15.safetensors",
    "clip_vision": "models/clip_vision/CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors",
    "controlnet_openpose": "models/controlnet/control_v11p_sd15_openpose.pth",
    "controlnet_config": "models/controlnet/control_v11p_sd15_openpose.yaml",
}

REQUIRED_NODE_TYPES = [
    "ADE_LoadAnimateDiffModel",
    "ADE_ApplyAnimateDiffModelSimple",
    "ADE_UseEvolvedSampling",
    "ADE_StandardStaticContextOptions",
    "VHS_LoadVideo",
    "VHS_VideoCombine",
    "IPAdapterUnifiedLoader",
    "IPAdapterAdvanced",
    "OpenposePreprocessor",
    "ControlNetApplyAdvanced",
]


def tail(path: Path, lines: int = 200) -> list[str]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return handle.readlines()[-lines:]


def sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


async def run_diagnostics(include_hashes: bool = False) -> dict[str, Any]:
    settings = get_settings()
    filesystem: dict[str, Any] = {
        "root": str(settings.comfyui_root),
        "exists": settings.comfyui_root.exists(),
        "models": {},
        "custom_nodes": {},
    }
    for name, relative in REQUIRED_MODELS.items():
        path = settings.comfyui_root / relative
        entry: dict[str, Any] = {"path": str(path), "exists": path.is_file()}
        if path.is_file():
            entry["size"] = path.stat().st_size
            if include_hashes:
                entry["sha256"] = sha256(path)
        filesystem["models"][name] = entry
    custom_root = settings.comfyui_root / "custom_nodes"
    for name in settings.required_custom_nodes:
        candidates = list(custom_root.glob(name)) + list(custom_root.glob(name.lower()))
        filesystem["custom_nodes"][name] = {
            "exists": any(path.is_dir() for path in candidates),
            "matches": [str(path) for path in candidates],
        }

    workers: dict[str, Any] = {}
    for name, url in settings.worker_map.items():
        client = ComfyUIClient(url)
        try:
            stats = await client.health()
            object_info = await client.object_info()
            missing_nodes = [
                node for node in REQUIRED_NODE_TYPES if node not in object_info
            ]
            queue = await client.queue()
            workers[name] = {
                "url": url,
                "online": True,
                "stats": stats,
                "missing_nodes": missing_nodes,
                "queue": queue,
            }
        except Exception as exc:  # diagnostic endpoint must report all workers
            workers[name] = {"url": url, "online": False, "error": str(exc)}

    logs = {str(path): tail(path) for path in settings.log_paths}
    missing_models = [
        key for key, value in filesystem["models"].items() if not value["exists"]
    ]
    offline_workers = [key for key, value in workers.items() if not value["online"]]
    return {
        "ok": filesystem["exists"] and not missing_models and not offline_workers,
        "filesystem": filesystem,
        "workers": workers,
        "logs": logs,
        "summary": {
            "missing_models": missing_models,
            "offline_workers": offline_workers,
        },
    }
