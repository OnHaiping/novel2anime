from __future__ import annotations

import asyncio

import httpx
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import __version__
from ..config import get_settings
from ..database import get_db
from ..models import AssetJob, AssetJobType, JobStatus
from ..services.comfyui import ComfyUIClient
from ..services.diagnostics import run_diagnostics, tail
from ..services.model_catalog import MODEL_CATALOG, catalog_status
from ..tasks import download_model_job


router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health")
def health():
    return {
        "status": "ok",
        "version": __version__,
        "capabilities": [
            "manual_novel_selections",
            "asset_generation",
            "model_downloader",
            "shot_output_preview",
            "editable_plan_json",
            "llm_prompt_refinement",
        ],
    }


@router.get("/diagnostics")
async def diagnostics(include_hashes: bool = False):
    return await run_diagnostics(include_hashes=include_hashes)


@router.get("/models")
def models():
    return catalog_status()


@router.post("/models/{model_key}/download", status_code=202)
def download_model(model_key: str, db: Session = Depends(get_db)):
    if model_key not in MODEL_CATALOG:
        raise HTTPException(404, "模型不在允许下载的目录中")
    status = next(item for item in catalog_status() if item["key"] == model_key)
    if status["exists"]:
        return {"status": "already_exists", "path": status["path"]}
    existing_jobs = db.scalars(
        select(AssetJob)
        .where(AssetJob.job_type == AssetJobType.model_download)
        .where(AssetJob.status.in_([JobStatus.queued, JobStatus.running]))
    ).all()
    existing = next(
        (
            job
            for job in existing_jobs
            if job.request_json.get("model_key") == model_key
        ),
        None,
    )
    if existing:
        return {"status": existing.status.value, "job_id": existing.id}
    job = AssetJob(
        job_type=AssetJobType.model_download,
        status=JobStatus.queued,
        request_json={"model_key": model_key},
    )
    db.add(job)
    db.commit()
    task = download_model_job.delay(job.id)
    job.celery_task_id = task.id
    db.commit()
    return {"status": "queued", "job_id": job.id}


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
