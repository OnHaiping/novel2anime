from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..models import Character, NovelSelection, Project, Scene, Shot
from ..schemas import (
    CharacterCreate,
    CharacterPatch,
    CharacterRead,
    LLMModelSelection,
    NovelContentRead,
    NovelSelectionCreate,
    NovelSelectionPatch,
    NovelSelectionRead,
    PlanApplyRequest,
    PlanDraftUpdate,
    PlanRequest,
    ProjectCreate,
    ProjectRead,
    SceneRead,
    ShotPatch,
    ShotRead,
)
from ..services.llm import LLMClient, PlannedChunk
from ..services.planner import apply_plan, create_plan, generate_plan


router = APIRouter(prefix="/projects", tags=["projects"])


def _draft_path(project_id: str) -> Path:
    return (
        get_settings().data_root / "projects" / project_id / "plans" / "plan_draft.json"
    )


def _save_draft(project_id: str, draft: dict) -> tuple[dict, Path]:
    normalized = PlannedChunk.model_validate(draft).model_dump()
    path = _draft_path(project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return normalized, path


def _load_draft(project_id: str) -> tuple[dict, Path]:
    path = _draft_path(project_id)
    if not path.is_file():
        raise HTTPException(404, "尚未生成分镜 JSON 草案")
    try:
        draft = json.loads(path.read_text(encoding="utf-8"))
        return PlannedChunk.model_validate(draft).model_dump(), path
    except (json.JSONDecodeError, ValidationError) as exc:
        raise HTTPException(409, f"已保存的分镜 JSON 无效：{exc}") from exc


def _selected_records(
    db: Session, project_id: str, selection_ids: list[str] | None
) -> list[NovelSelection]:
    query = select(NovelSelection).where(NovelSelection.project_id == project_id)
    if selection_ids is not None:
        if not selection_ids:
            raise HTTPException(400, "至少选择一条已记录选段")
        query = query.where(NovelSelection.id.in_(selection_ids))
    else:
        query = query.where(NovelSelection.selected.is_(True))
    records = list(db.scalars(query.order_by(NovelSelection.sequence)).all())
    if not records:
        raise HTTPException(400, "请先在原文中划线并记录至少一个选段")
    return records


def _project_llm_model(project: Project, requested: str | None = None) -> str:
    return (
        (requested or "").strip()
        or str((project.settings or {}).get("llm_model", "")).strip()
        or get_settings().llm_model.strip()
    )


def _save_project_llm_model(project: Project, model: str, db: Session) -> None:
    project.settings = {**(project.settings or {}), "llm_model": model}
    db.commit()


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


@router.put("/{project_id}/llm-model", response_model=ProjectRead)
def select_project_llm_model(
    project_id: str, payload: LLMModelSelection, db: Session = Depends(get_db)
):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "项目不存在")
    model = payload.model.strip()
    if not model:
        raise HTTPException(400, "模型 ID 不能为空")
    _save_project_llm_model(project, model, db)
    db.refresh(project)
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
    project_id: str,
    file: UploadFile = File(...),
    novel_type: str = Form(...),
    db: Session = Depends(get_db),
):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "项目不存在")
    if not file.filename or Path(file.filename).suffix.lower() not in {".txt", ".md"}:
        raise HTTPException(400, "第一版仅支持 TXT 和 Markdown")
    if novel_type not in {"long", "short"}:
        raise HTTPException(400, "novel_type 必须是 long 或 short")
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
    project.settings = {**(project.settings or {}), "novel_type": novel_type}
    for selection in list(project.selections):
        db.delete(selection)
    draft_path = _draft_path(project.id)
    if draft_path.is_file():
        draft_path.unlink()
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
    selections = _selected_records(db, project_id, payload.selection_ids)
    selection_input = [(item.title, item.source_text) for item in selections]
    llm_model = _project_llm_model(project, payload.llm_model)
    if payload.use_llm and llm_model:
        _save_project_llm_model(project, llm_model, db)
    try:
        characters, scenes, shots = await create_plan(
            db,
            project,
            payload.use_llm,
            payload.max_shots,
            payload.target_shot_seconds,
            selection_input,
            payload.append_to_timeline,
            llm_model,
        )
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc
    processed_at = datetime.now(timezone.utc)
    for selection in selections:
        selection.process_count += 1
        selection.last_processed_at = processed_at
    db.commit()
    return {
        "characters": characters,
        "scenes": scenes,
        "shots": shots,
        "selections_used": len(selection_input),
    }


@router.post("/{project_id}/plan-draft")
async def generate_plan_draft(
    project_id: str, payload: PlanRequest, db: Session = Depends(get_db)
):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "项目不存在")
    records = _selected_records(db, project_id, payload.selection_ids)
    selection_input = [(item.title, item.source_text) for item in records]
    llm_model = _project_llm_model(project, payload.llm_model)
    if payload.use_llm and llm_model:
        _save_project_llm_model(project, llm_model, db)
    try:
        draft = await generate_plan(
            project, payload.use_llm, payload.max_shots, selection_input, llm_model
        )
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, f"大模型生成分镜失败：{exc}") from exc
    normalized, path = _save_draft(project_id, draft)
    processed_at = datetime.now(timezone.utc)
    for record in records:
        record.process_count += 1
        record.last_processed_at = processed_at
    db.commit()
    return {
        "draft": normalized,
        "path": str(path.relative_to(get_settings().data_root)).replace("\\", "/"),
        "selections_used": len(records),
    }


@router.get("/{project_id}/plan-draft")
def get_plan_draft(
    project_id: str, download: bool = False, db: Session = Depends(get_db)
):
    if not db.get(Project, project_id):
        raise HTTPException(404, "项目不存在")
    draft, path = _load_draft(project_id)
    if download:
        return FileResponse(
            path, media_type="application/json", filename=f"{project_id}-plan.json"
        )
    return {"draft": draft, "path": str(path)}


@router.put("/{project_id}/plan-draft")
def update_plan_draft(
    project_id: str, payload: PlanDraftUpdate, db: Session = Depends(get_db)
):
    if not db.get(Project, project_id):
        raise HTTPException(404, "项目不存在")
    try:
        draft, path = _save_draft(project_id, payload.draft)
    except ValidationError as exc:
        raise HTTPException(400, f"分镜 JSON 校验失败：{exc}") from exc
    return {"draft": draft, "path": str(path)}


@router.post("/{project_id}/plan-draft/prompts")
async def generate_draft_prompts(project_id: str, db: Session = Depends(get_db)):
    if not db.get(Project, project_id):
        raise HTTPException(404, "项目不存在")
    draft, _ = _load_draft(project_id)
    try:
        project = db.get(Project, project_id)
        enhanced = await LLMClient(_project_llm_model(project)).generate_prompts(draft)
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, f"大模型生成镜头提示词失败：{exc}") from exc
    normalized, path = _save_draft(project_id, enhanced)
    return {"draft": normalized, "path": str(path)}


@router.post("/{project_id}/plan-draft/apply")
def apply_plan_draft(
    project_id: str, payload: PlanApplyRequest, db: Session = Depends(get_db)
):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "项目不存在")
    draft, _ = _load_draft(project_id)
    characters, scenes, shots = apply_plan(
        db,
        project,
        draft,
        max_shots=payload.max_shots,
        target_shot_seconds=payload.target_shot_seconds,
        append_to_timeline=payload.append_to_timeline,
    )
    return {"characters": characters, "scenes": scenes, "shots": shots}


@router.get("/{project_id}/novel-content", response_model=NovelContentRead)
def novel_content(project_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "项目不存在")
    settings = get_settings()
    return {
        "novel_type": (project.settings or {}).get("novel_type", "long"),
        "text": project.novel_text,
        "length": len(project.novel_text),
        "max_selection_chars": settings.llm_max_selection_chars,
    }


@router.get("/{project_id}/selections", response_model=list[NovelSelectionRead])
def list_selections(project_id: str, db: Session = Depends(get_db)):
    if not db.get(Project, project_id):
        raise HTTPException(404, "项目不存在")
    return db.scalars(
        select(NovelSelection)
        .where(NovelSelection.project_id == project_id)
        .order_by(NovelSelection.sequence)
    ).all()


@router.post(
    "/{project_id}/selections", response_model=NovelSelectionRead, status_code=201
)
def create_selection(
    project_id: str,
    payload: NovelSelectionCreate,
    db: Session = Depends(get_db),
):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "项目不存在")
    if not project.novel_text.strip():
        raise HTTPException(400, "请先上传小说")
    if payload.char_end <= payload.char_start:
        raise HTTPException(400, "选段结束位置必须大于开始位置")
    if payload.char_end > len(project.novel_text):
        raise HTTPException(400, "选段超出原文范围")
    max_chars = get_settings().llm_max_selection_chars
    if payload.char_end - payload.char_start > max_chars:
        raise HTTPException(400, f"单个选段不能超过 {max_chars} 字")
    source_text = project.novel_text[payload.char_start : payload.char_end]
    if not source_text.strip():
        raise HTTPException(400, "不能记录空白选段")
    sequence = max((item.sequence for item in project.selections), default=0) + 1
    selection = NovelSelection(
        project_id=project_id,
        sequence=sequence,
        title=payload.title,
        source_text=source_text,
        char_start=payload.char_start,
        char_end=payload.char_end,
        selected=True,
    )
    db.add(selection)
    db.commit()
    db.refresh(selection)
    return selection


@router.patch(
    "/{project_id}/selections/{selection_id}", response_model=NovelSelectionRead
)
def patch_selection(
    project_id: str,
    selection_id: str,
    payload: NovelSelectionPatch,
    db: Session = Depends(get_db),
):
    selection = db.get(NovelSelection, selection_id)
    if not selection or selection.project_id != project_id:
        raise HTTPException(404, "选段不存在")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(selection, key, value)
    db.commit()
    db.refresh(selection)
    return selection


@router.delete("/{project_id}/selections/{selection_id}", status_code=204)
def delete_selection(project_id: str, selection_id: str, db: Session = Depends(get_db)):
    selection = db.get(NovelSelection, selection_id)
    if not selection or selection.project_id != project_id:
        raise HTTPException(404, "选段不存在")
    db.delete(selection)
    db.commit()


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


@router.patch("/{project_id}/characters/{character_id}", response_model=CharacterRead)
def patch_character(
    project_id: str,
    character_id: str,
    payload: CharacterPatch,
    db: Session = Depends(get_db),
):
    character = db.get(Character, character_id)
    if not character or character.project_id != project_id:
        raise HTTPException(404, "角色不存在")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(character, key, value)
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
