from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .models import AssemblyStatus, JobStatus, ProjectStatus, ShotStatus


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    novel_text: str = ""
    settings: dict[str, Any] = Field(default_factory=dict)


class ProjectRead(ORMModel):
    id: str
    name: str
    source_filename: str | None
    status: ProjectStatus
    settings: dict[str, Any]
    assembly_status: AssemblyStatus
    final_output: str | None
    assembly_error: str | None
    created_at: datetime
    updated_at: datetime


class CharacterCreate(BaseModel):
    name: str
    age: int | None = Field(default=None, ge=18)
    description: str = ""
    positive_prompt: str = ""
    negative_prompt: str = ""
    reference_image: str | None = None
    default_ipadapter_weight: float = Field(default=0.65, ge=0, le=2)


class CharacterRead(ORMModel):
    id: str
    project_id: str
    name: str
    age: int | None
    description: str
    positive_prompt: str
    negative_prompt: str
    reference_image: str | None
    default_ipadapter_weight: float


class SceneRead(ORMModel):
    id: str
    project_id: str
    sequence: int
    title: str
    location: str
    time_of_day: str
    weather: str
    summary: str
    source_text: str


class ShotPatch(BaseModel):
    shot_type: str | None = None
    camera: str | None = None
    action: str | None = None
    emotion: str | None = None
    dialogue: str | None = None
    motion_mode: str | None = None
    motion_asset_id: str | None = None
    workflow_key: str | None = None
    positive_prompt: str | None = None
    negative_prompt: str | None = None
    seed: int | None = None
    frames: int | None = Field(default=None, ge=1, le=128)
    width: int | None = Field(default=None, ge=256, le=2048)
    height: int | None = Field(default=None, ge=256, le=2048)


class ShotRead(ORMModel):
    id: str
    project_id: str
    scene_id: str | None
    code: str
    sequence: int
    duration: float
    fps: int
    frames: int
    width: int
    height: int
    shot_type: str
    camera: str
    action: str
    emotion: str
    dialogue: str | None
    character_ids: list
    location: str
    motion_mode: str
    motion_asset_id: str | None
    workflow_key: str
    positive_prompt: str
    negative_prompt: str
    seed: int
    status: ShotStatus
    output_file: str | None


class MotionAssetCreate(BaseModel):
    motion_id: str
    name: str
    action: str
    speed: str = "normal"
    direction: str = "any"
    shot_type: str = "full body"
    camera: str = "static"
    source_type: str = "generated"
    source_file: str
    preview_file: str | None = None
    fps: int = 8
    frames: int = 16
    width: int = 512
    height: int = 512
    loopable: bool = False
    tags: list[str] = Field(default_factory=list)


class MotionAssetRead(ORMModel):
    id: str
    motion_id: str
    name: str
    action: str
    speed: str
    direction: str
    shot_type: str
    camera: str
    source_type: str
    source_file: str
    preview_file: str | None
    fps: int
    frames: int
    width: int
    height: int
    loopable: bool
    tags: list


class RenderJobRead(ORMModel):
    id: str
    shot_id: str
    worker_name: str | None
    comfy_prompt_id: str | None
    celery_task_id: str | None
    status: JobStatus
    attempt: int
    output_metadata: dict
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class PlanRequest(BaseModel):
    use_llm: bool = True
    target_shot_seconds: float = Field(default=2.0, ge=1.0, le=6.0)
    max_shots: int = Field(default=30, ge=1, le=300)


class RenderRequest(BaseModel):
    force: bool = False


class AssembleRequest(BaseModel):
    width: int = Field(default=1024, ge=256, le=3840)
    height: int = Field(default=576, ge=256, le=2160)
    fps: int = Field(default=24, ge=1, le=60)
    crf: int = Field(default=18, ge=0, le=51)
