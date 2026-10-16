from __future__ import annotations

import asyncio
import mimetypes
import time
import uuid
from pathlib import Path
from typing import Any

import httpx


class ComfyUIError(RuntimeError):
    pass


class ComfyUIClient:
    def __init__(self, base_url: str, timeout: int = 1800) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client_id = str(uuid.uuid4())

    async def health(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{self.base_url}/system_stats")
            response.raise_for_status()
            return response.json()

    async def object_info(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(f"{self.base_url}/object_info")
            response.raise_for_status()
            return response.json()

    async def queue(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{self.base_url}/queue")
            response.raise_for_status()
            return response.json()

    async def upload(self, path: Path, overwrite: bool = True) -> str:
        if not path.exists():
            raise FileNotFoundError(path)
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        async with httpx.AsyncClient(timeout=300) as client:
            with path.open("rb") as handle:
                response = await client.post(
                    f"{self.base_url}/upload/image",
                    data={"type": "input", "overwrite": str(overwrite).lower()},
                    files={"image": (path.name, handle, mime)},
                )
            response.raise_for_status()
            data = response.json()
        return str(Path(data.get("subfolder", "")) / data["name"]).replace("\\", "/")

    async def submit(self, prompt: dict[str, Any]) -> str:
        payload = {"prompt": prompt, "client_id": self.client_id}
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(f"{self.base_url}/prompt", json=payload)
        if response.status_code >= 400:
            raise ComfyUIError(
                f"ComfyUI 拒绝工作流：{response.status_code} {response.text[:2000]}"
            )
        data = response.json()
        if data.get("node_errors"):
            raise ComfyUIError(f"工作流节点校验失败：{data['node_errors']}")
        return data["prompt_id"]

    async def wait(self, prompt_id: str, poll_seconds: float = 2.0) -> dict[str, Any]:
        deadline = time.monotonic() + self.timeout
        async with httpx.AsyncClient(timeout=30) as client:
            while time.monotonic() < deadline:
                response = await client.get(f"{self.base_url}/history/{prompt_id}")
                response.raise_for_status()
                history = response.json()
                if prompt_id in history:
                    item = history[prompt_id]
                    status = item.get("status", {})
                    if (
                        status.get("status_str") == "error"
                        or status.get("completed") is False
                    ):
                        messages = status.get("messages", [])
                        if any(
                            message[0] == "execution_error"
                            for message in messages
                            if message
                        ):
                            raise ComfyUIError(f"ComfyUI 执行失败：{messages}")
                    if status.get("completed") or item.get("outputs"):
                        return item
                await asyncio.sleep(poll_seconds)
        raise TimeoutError(f"等待 ComfyUI 任务 {prompt_id} 超时")

    @staticmethod
    def extract_outputs(history_item: dict[str, Any]) -> list[dict[str, Any]]:
        files: list[dict[str, Any]] = []
        for node_id, output in history_item.get("outputs", {}).items():
            for key in ("images", "gifs"):
                for item in output.get(key, []):
                    files.append({"node_id": node_id, **item})
        return files
