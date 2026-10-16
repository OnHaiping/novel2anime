from __future__ import annotations

import json
import subprocess
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..models import MotionAsset
from ..schemas import MotionAssetCreate, MotionAssetRead


router = APIRouter(prefix="/motions", tags=["motions"])


@router.get("", response_model=list[MotionAssetRead])
def list_motions(db: Session = Depends(get_db)):
    return db.scalars(
        select(MotionAsset).order_by(MotionAsset.action, MotionAsset.motion_id)
    ).all()


@router.post("", response_model=MotionAssetRead, status_code=201)
def create_motion(payload: MotionAssetCreate, db: Session = Depends(get_db)):
    if db.scalar(select(MotionAsset).where(MotionAsset.motion_id == payload.motion_id)):
        raise HTTPException(409, "motion_id 已存在")
    motion = MotionAsset(**payload.model_dump())
    db.add(motion)
    db.commit()
    db.refresh(motion)
    return motion


@router.post("/upload", response_model=MotionAssetRead, status_code=201)
async def upload_motion(
    file: UploadFile = File(...),
    metadata: str = Form(...),
    db: Session = Depends(get_db),
):
    try:
        payload = json.loads(metadata)
        spec = MotionAssetCreate(**{**payload, "source_file": "pending"})
    except Exception as exc:
        raise HTTPException(400, f"metadata 无效：{exc}") from exc
    if db.scalar(select(MotionAsset).where(MotionAsset.motion_id == spec.motion_id)):
        raise HTTPException(409, "motion_id 已存在")
    settings = get_settings()
    directory = settings.data_root / "motion_library" / spec.action / spec.motion_id
    directory.mkdir(parents=True, exist_ok=True)
    raw = directory / f"raw{Path(file.filename or '.mp4').suffix.lower()}"
    raw.write_bytes(await file.read())
    normalized = directory / "source.mp4"
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(raw),
        "-vf",
        "fps=8,scale=512:512:force_original_aspect_ratio=increase,crop=512:512",
        "-frames:v",
        "16",
        "-an",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        str(normalized),
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise HTTPException(400, f"FFmpeg 标准化失败：{result.stderr[-2000:]}")
    data = spec.model_dump()
    data["source_file"] = str(normalized.relative_to(settings.data_root))
    motion = MotionAsset(**data)
    db.add(motion)
    db.commit()
    db.refresh(motion)
    return motion


@router.delete("/{motion_id}", status_code=204)
def delete_motion(motion_id: str, db: Session = Depends(get_db)):
    motion = db.get(MotionAsset, motion_id)
    if not motion:
        raise HTTPException(404, "动作不存在")
    db.delete(motion)
    db.commit()
