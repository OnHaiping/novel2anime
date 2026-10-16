from __future__ import annotations

import asyncio
import traceback
from datetime import datetime, timezone
from pathlib import Path

from celery import Celery
from redis import Redis
from sqlalchemy import select

from .config import get_settings
from .database import SessionLocal
from .models import (
    AssemblyStatus,
    Character,
    JobStatus,
    Project,
    ProjectStatus,
    RenderJob,
    Shot,
    ShotStatus,
)
from .services.assembler import assemble_project
from .services.comfyui import ComfyUIClient
from .services.workflow import WorkflowBuilder


settings = get_settings()
celery_app = Celery(
    "novel2anime", broker=settings.redis_url, backend=settings.redis_url
)
celery_app.conf.update(
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_time_limit=settings.render_timeout + 120,
)


def now() -> datetime:
    return datetime.now(timezone.utc)


def _select_worker(redis_client: Redis) -> tuple[str, str, object]:
    for name, url in settings.worker_map.items():
        lock = redis_client.lock(
            f"novel2anime:worker:{name}", timeout=settings.render_timeout + 300
        )
        if lock.acquire(blocking=False):
            return name, url, lock
    raise RuntimeError("没有空闲的 ComfyUI worker")


async def _run_render(job_id: str) -> None:
    redis_client = Redis.from_url(settings.redis_url)
    worker_lock = None
    with SessionLocal() as db:
        job = db.get(RenderJob, job_id)
        if not job:
            raise ValueError(f"渲染任务不存在：{job_id}")
        shot = db.get(Shot, job.shot_id)
        if not shot:
            raise ValueError(f"镜头不存在：{job.shot_id}")
        try:
            worker_name, worker_url, worker_lock = _select_worker(redis_client)
            job.worker_name = worker_name
            job.status = JobStatus.running
            job.started_at = now()
            shot.status = ShotStatus.rendering
            db.commit()

            client = ComfyUIClient(worker_url, timeout=settings.render_timeout)
            await client.health()
            characters = (
                db.scalars(
                    select(Character).where(Character.id.in_(shot.character_ids))
                ).all()
                if shot.character_ids
                else []
            )
            motion_asset = shot.motion_asset

            reference_name = None
            if characters and characters[0].reference_image:
                path = Path(characters[0].reference_image)
                if not path.is_absolute():
                    path = settings.data_root / path
                reference_name = await client.upload(path)

            driver_name = None
            if motion_asset:
                path = Path(motion_asset.source_file)
                if not path.is_absolute():
                    path = settings.data_root / path
                driver_name = await client.upload(path)

            prompt = WorkflowBuilder().build(
                shot,
                list(characters),
                motion_asset,
                reference_image_name=reference_name,
                driver_video_name=driver_name,
            )
            job.submitted_workflow = prompt
            db.commit()

            prompt_id = await client.submit(prompt)
            job.comfy_prompt_id = prompt_id
            db.commit()

            history = await client.wait(prompt_id)
            outputs = client.extract_outputs(history)
            job.output_metadata = {
                "files": outputs,
                "history_status": history.get("status", {}),
            }
            job.status = JobStatus.completed
            job.completed_at = now()
            shot.status = ShotStatus.completed
            if outputs:
                selected = outputs[-1]
                shot.output_file = str(
                    Path(selected.get("subfolder", "")) / selected["filename"]
                ).replace("\\", "/")
            db.commit()
        except Exception as exc:
            job.status = JobStatus.failed
            job.completed_at = now()
            job.error_message = f"{exc}\n{traceback.format_exc(limit=12)}"
            shot.status = ShotStatus.failed
            db.commit()
            raise
        finally:
            if worker_lock is not None:
                try:
                    worker_lock.release()
                except Exception:
                    pass


@celery_app.task(
    bind=True,
    autoretry_for=(RuntimeError,),
    retry_backoff=5,
    retry_kwargs={"max_retries": 20},
)
def render_job(self, job_id: str) -> None:
    asyncio.run(_run_render(job_id))


@celery_app.task(bind=True)
def assemble_project_job(
    self,
    project_id: str,
    width: int = 1024,
    height: int = 576,
    fps: int = 24,
    crf: int = 18,
) -> str:
    with SessionLocal() as db:
        project = db.get(Project, project_id)
        if not project:
            raise ValueError(f"项目不存在：{project_id}")
        project.assembly_status = AssemblyStatus.running
        project.assembly_error = None
        db.commit()
        try:
            shots = db.scalars(
                select(Shot)
                .where(Shot.project_id == project_id)
                .order_by(Shot.sequence)
            ).all()
            incomplete = [
                shot.code
                for shot in shots
                if shot.status != ShotStatus.completed or not shot.output_file
            ]
            if incomplete:
                raise ValueError(f"以下镜头尚未完成：{', '.join(incomplete)}")
            final_path = assemble_project(
                project_id, list(shots), width=width, height=height, fps=fps, crf=crf
            )
            project.final_output = str(
                final_path.relative_to(settings.data_root)
            ).replace("\\", "/")
            project.assembly_status = AssemblyStatus.completed
            project.status = ProjectStatus.completed
            db.commit()
            return project.final_output
        except Exception as exc:
            project.assembly_status = AssemblyStatus.failed
            project.assembly_error = f"{exc}\n{traceback.format_exc(limit=12)}"
            db.commit()
            raise
