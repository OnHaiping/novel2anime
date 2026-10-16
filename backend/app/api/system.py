from __future__ import annotations

import asyncio

import httpx
from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from ..config import get_settings
from ..services.comfyui import ComfyUIClient
from ..services.diagnostics import run_diagnostics, tail


router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/diagnostics")
async def diagnostics(include_hashes: bool = False):
    return await run_diagnostics(include_hashes=include_hashes)


@router.get("/logs")
def logs(lines: int = Query(default=200, ge=1, le=2000)):
    settings = get_settings()
    return {str(path): tail(path, lines) for path in settings.log_paths}


@router.get("/comfyui/{worker_name}/view")
async def proxy_output(
    worker_name: str, filename: str, subfolder: str = "", type: str = "output"
):
    settings = get_settings()
    url = settings.worker_map.get(worker_name)
    if not url:
        raise HTTPException(404, "worker 不存在")
    client = httpx.AsyncClient(timeout=120)
    response = await client.send(
        client.build_request(
            "GET",
            f"{url}/view",
            params={"filename": filename, "subfolder": subfolder, "type": type},
        ),
        stream=True,
    )
    if response.status_code >= 400:
        await response.aclose()
        await client.aclose()
        raise HTTPException(response.status_code, "无法读取 ComfyUI 输出")

    async def stream():
        try:
            async for chunk in response.aiter_bytes():
                yield chunk
        finally:
            await response.aclose()
            await client.aclose()

    return StreamingResponse(stream(), media_type=response.headers.get("content-type"))


@router.websocket("/ws")
async def system_ws(websocket: WebSocket):
    await websocket.accept()
    settings = get_settings()
    try:
        while True:
            workers = {}
            for name, url in settings.worker_map.items():
                try:
                    workers[name] = {
                        "online": True,
                        "queue": await ComfyUIClient(url).queue(),
                    }
                except Exception as exc:
                    workers[name] = {"online": False, "error": str(exc)}
            await websocket.send_json(
                {
                    "workers": workers,
                    "logs": {str(path): tail(path, 30) for path in settings.log_paths},
                }
            )
            await asyncio.sleep(3)
    except WebSocketDisconnect:
        return
