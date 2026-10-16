from __future__ import annotations

import mimetypes
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AssemblyStatus, JobStatus, Project, RenderJob, Shot, ShotStatus
from ..schemas import AssembleRequest, RenderJobRead, RenderRequest
from ..config import get_settings
from ..services.router import match_motion
from ..tasks import assemble_project_job, render_job


router = APIRouter(prefix="/renders", tags=["renders"])


@router.get("/jobs", response_model=list[RenderJobRead])
def list_jobs(limit: int = 100, db: Session = Depends(get_db)):
    return db.scalars(
        select(RenderJob).order_by(RenderJob.created_at.desc()).limit(min(limit, 500))
    ).all()


def _completed_result(shot: Shot, db: Session) -> tuple[RenderJob, Path, str]:
    if shot.status != ShotStatus.completed or not shot.output_file:
        raise HTTPException(409, "镜头尚未生成完成")
    job = db.scalar(
        select(RenderJob)
        .where(RenderJob.shot_id == shot.id)
        .where(RenderJob.status == JobStatus.completed)
        .order_by(RenderJob.completed_at.desc(), RenderJob.created_at.desc())
    )
    if not job:
        raise HTTPException(404, "找不到该镜头的已完成任务记录")
    settings = get_settings()
    output_root = (settings.comfyui_root / "output").resolve()
    path = (output_root / shot.output_file).resolve()
    if output_root not in path.parents or not path.is_file():
        raise HTTPException(404, f"镜头输出文件不存在：{shot.output_file}")
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return job, path, media_type


@router.get("/shots/{shot_id}/result")
def shot_result(shot_id: str, db: Session = Depends(get_db)):
    shot = db.get(Shot, shot_id)
    if not shot:
        raise HTTPException(404, "镜头不存在")
    job, path, media_type = _completed_result(shot, db)
    return {
        "shot_id": shot.id,
        "code": shot.code,
        "output_file": shot.output_file,
        "filename": path.name,
        "media_type": media_type,
        "size": path.stat().st_size,
        "worker_name": job.worker_name,
        "comfy_prompt_id": job.comfy_prompt_id,
        "completed_at": job.completed_at,
        "output_metadata": job.output_metadata,
        "preview_url": f"/api/renders/shots/{shot.id}/output",
        "download_url": f"/api/renders/shots/{shot.id}/output?download=true",
    }


@router.get("/shots/{shot_id}/output")
def shot_output(shot_id: str, download: bool = False, db: Session = Depends(get_db)):
    shot = db.get(Shot, shot_id)
    if not shot:
        raise HTTPException(404, "镜头不存在")
    _, path, media_type = _completed_result(shot, db)
    if download:
        return FileResponse(path, media_type=media_type, filename=path.name)
    return FileResponse(path, media_type=media_type)


@router.post("/shots/{shot_id}", response_model=RenderJobRead, status_code=202)
def queue_shot(shot_id: str, payload: RenderRequest, db: Session = Depends(get_db)):
    shot = db.get(Shot, shot_id)
    if not shot:
        raise HTTPException(404, "镜头不存在")
    if shot.status == ShotStatus.completed and not payload.force:
        raise HTTPException(409, "镜头已经完成；如需重做请使用 force=true")
    if shot.workflow_key == "04" and not shot.motion_asset_id:
        motion = match_motion(db, shot)
        if motion:
            shot.motion_asset_id = motion.id
        else:
            shot.workflow_key = "03" if shot.character_ids else "02"
            shot.motion_mode = "free_fallback"
    attempt = (
        db.scalar(
            select(func.count())
            .select_from(RenderJob)
            .where(RenderJob.shot_id == shot.id)
        )
        or 0
    ) + 1
    job = RenderJob(shot_id=shot.id, status=JobStatus.queued, attempt=attempt)
    shot.status = ShotStatus.queued
    db.add(job)
    db.commit()
    task = render_job.delay(job.id)
    job.celery_task_id = task.id
    db.commit()
    db.refresh(job)
    return job


@router.post("/projects/{project_id}")
def queue_project(
    project_id: str, payload: RenderRequest, db: Session = Depends(get_db)
):
    shots = db.scalars(
        select(Shot).where(Shot.project_id == project_id).order_by(Shot.sequence)
    ).all()
    if not shots:
        raise HTTPException(404, "项目没有镜头")
    jobs = []
    for shot in shots:
        if shot.status == ShotStatus.completed and not payload.force:
            continue
        if shot.workflow_key == "04" and not shot.motion_asset_id:
            motion = match_motion(db, shot)
            if motion:
                shot.motion_asset_id = motion.id
            else:
                shot.workflow_key = "03" if shot.character_ids else "02"
                shot.motion_mode = "free_fallback"
        attempt = (
            db.scalar(
                select(func.count())
                .select_from(RenderJob)
                .where(RenderJob.shot_id == shot.id)
            )
            or 0
        ) + 1
        job = RenderJob(shot_id=shot.id, status=JobStatus.queued, attempt=attempt)
        shot.status = ShotStatus.queued
        db.add(job)
        db.flush()
        jobs.append(job)
    db.commit()
    for job in jobs:
        task = render_job.delay(job.id)
        job.celery_task_id = task.id
    db.commit()
    return {"queued": len(jobs), "job_ids": [job.id for job in jobs]}


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str, db: Session = Depends(get_db)):
    job = db.get(RenderJob, job_id)
    if not job:
        raise HTTPException(404, "任务不存在")
    if job.celery_task_id:
        render_job.app.control.revoke(job.celery_task_id, terminate=False)
    job.status = JobStatus.cancelled
    job.shot.status = ShotStatus.pending
    db.commit()
    return {"cancelled": True}


@router.post("/projects/{project_id}/assemble", status_code=202)
def queue_assembly(
    project_id: str, payload: AssembleRequest, db: Session = Depends(get_db)
):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "项目不存在")
    shots = db.scalars(
        select(Shot).where(Shot.project_id == project_id).order_by(Shot.sequence)
    ).all()
    if not shots:
        raise HTTPException(409, "项目没有镜头")
    incomplete = [
        shot.code
        for shot in shots
        if shot.status != ShotStatus.completed or not shot.output_file
    ]
    if incomplete:
        raise HTTPException(409, f"以下镜头尚未完成：{', '.join(incomplete)}")
    project.assembly_status = AssemblyStatus.queued
    project.assembly_error = None
    db.commit()
    task = assemble_project_job.delay(
        project_id, payload.width, payload.height, payload.fps, payload.crf
    )
    return {"task_id": task.id, "status": "queued"}


@router.get("/projects/{project_id}/final")
def download_final(project_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "项目不存在")
    if project.assembly_status != AssemblyStatus.completed or not project.final_output:
        raise HTTPException(409, "成片尚未完成")
    settings = get_settings()
    path = (settings.data_root / project.final_output).resolve()
    root = settings.data_root.resolve()
    if root not in path.parents or not path.is_file():
        raise HTTPException(404, "成片文件不存在")
    return FileResponse(path, media_type="video/mp4", filename=f"{project.name}.mp4")
