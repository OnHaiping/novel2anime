from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AssetJob, AssetJobType, Character, JobStatus
from ..schemas import AssetJobRead, PortraitGenerateRequest
from ..tasks import generate_asset_job


router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("/jobs", response_model=list[AssetJobRead])
def list_asset_jobs(limit: int = 100, db: Session = Depends(get_db)):
    return db.scalars(
        select(AssetJob).order_by(AssetJob.created_at.desc()).limit(min(limit, 500))
    ).all()


@router.post(
    "/projects/{project_id}/characters/{character_id}/portrait",
    response_model=AssetJobRead,
    status_code=202,
)
def queue_portrait(
    project_id: str,
    character_id: str,
    payload: PortraitGenerateRequest,
    db: Session = Depends(get_db),
):
    character = db.get(Character, character_id)
    if not character or character.project_id != project_id:
        raise HTTPException(404, "角色不存在")
    job = AssetJob(
        job_type=AssetJobType.portrait,
        project_id=project_id,
        character_id=character_id,
        status=JobStatus.queued,
        request_json=payload.model_dump(),
    )
    db.add(job)
    db.commit()
    task = generate_asset_job.delay(job.id)
    job.celery_task_id = task.id
    db.commit()
    db.refresh(job)
    return job
