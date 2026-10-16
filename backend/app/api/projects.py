from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..models import Character, Project, Scene, Shot
from ..schemas import (
    CharacterCreate,
    CharacterRead,
    PlanRequest,
    ProjectCreate,
    ProjectRead,
    SceneRead,
    ShotPatch,
    ShotRead,
)
from ..services.planner import create_plan


router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectRead])
def list_projects(db: Session = Depends(get_db)):
    return db.scalars(select(Project).order_by(Project.created_at.desc())).all()


@router.post("", response_model=ProjectRead, status_code=201)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    project = Project(**payload.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "项目不存在")
    return project


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "项目不存在")
    db.delete(project)
    db.commit()


@router.post("/{project_id}/novel", response_model=ProjectRead)
async def upload_novel(
    project_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)
):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "项目不存在")
    if not file.filename or Path(file.filename).suffix.lower() not in {".txt", ".md"}:
        raise HTTPException(400, "第一版仅支持 TXT 和 Markdown")
    content = await file.read()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(400, "小说文件必须是 UTF-8 编码") from exc
    settings = get_settings()
    project_dir = settings.data_root / "projects" / project.id / "source"
    project_dir.mkdir(parents=True, exist_ok=True)
    saved = project_dir / Path(file.filename).name
    saved.write_bytes(content)
    project.source_filename = str(saved.relative_to(settings.data_root))
    project.novel_text = text
    db.commit()
    db.refresh(project)
    return project


@router.post("/{project_id}/plan")
async def plan_project(
    project_id: str, payload: PlanRequest, db: Session = Depends(get_db)
):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "项目不存在")
    if not project.novel_text.strip():
        raise HTTPException(400, "请先上传小说")
    characters, scenes, shots = await create_plan(
        db,
        project,
        payload.use_llm,
        payload.max_shots,
        payload.target_shot_seconds,
    )
    return {"characters": characters, "scenes": scenes, "shots": shots}


@router.get("/{project_id}/characters", response_model=list[CharacterRead])
def list_characters(project_id: str, db: Session = Depends(get_db)):
    return db.scalars(select(Character).where(Character.project_id == project_id)).all()


@router.post("/{project_id}/characters", response_model=CharacterRead, status_code=201)
def add_character(
    project_id: str, payload: CharacterCreate, db: Session = Depends(get_db)
):
    if not db.get(Project, project_id):
        raise HTTPException(404, "项目不存在")
    character = Character(project_id=project_id, **payload.model_dump())
    db.add(character)
    db.commit()
    db.refresh(character)
    return character


@router.post(
    "/{project_id}/characters/{character_id}/reference", response_model=CharacterRead
)
async def upload_reference(
    project_id: str,
    character_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    character = db.get(Character, character_id)
    if not character or character.project_id != project_id:
        raise HTTPException(404, "角色不存在")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise HTTPException(400, "参考图仅支持 PNG/JPG/WebP")
    settings = get_settings()
    directory = (
        settings.data_root / "projects" / project_id / "characters" / character_id
    )
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"reference{suffix}"
    path.write_bytes(await file.read())
    character.reference_image = str(path.relative_to(settings.data_root))
    db.commit()
    db.refresh(character)
    return character


@router.get("/{project_id}/scenes", response_model=list[SceneRead])
def list_scenes(project_id: str, db: Session = Depends(get_db)):
    return db.scalars(
        select(Scene).where(Scene.project_id == project_id).order_by(Scene.sequence)
    ).all()


@router.get("/{project_id}/shots", response_model=list[ShotRead])
def list_shots(project_id: str, db: Session = Depends(get_db)):
    return db.scalars(
        select(Shot).where(Shot.project_id == project_id).order_by(Shot.sequence)
    ).all()


@router.patch("/{project_id}/shots/{shot_id}", response_model=ShotRead)
def patch_shot(
    project_id: str, shot_id: str, payload: ShotPatch, db: Session = Depends(get_db)
):
    shot = db.get(Shot, shot_id)
    if not shot or shot.project_id != project_id:
        raise HTTPException(404, "镜头不存在")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(shot, key, value)
    db.commit()
    db.refresh(shot)
    return shot
