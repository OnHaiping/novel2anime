from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid.uuid4())


class ProjectStatus(str, enum.Enum):
    draft = "draft"
    planned = "planned"
    rendering = "rendering"
    completed = "completed"
    failed = "failed"


class AssemblyStatus(str, enum.Enum):
    idle = "idle"
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class ShotStatus(str, enum.Enum):
    pending = "pending"
    preparing = "preparing"
    queued = "queued"
    rendering = "rendering"
    completed = "completed"
    failed = "failed"
    manual_review = "manual_review"


class JobStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class AssetJobType(str, enum.Enum):
    portrait = "portrait"
    motion = "motion"
    model_download = "model_download"


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    source_filename: Mapped[str | None] = mapped_column(String(500), nullable=True)
    novel_text: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus), default=ProjectStatus.draft
    )
    settings: Mapped[dict] = mapped_column(JSON, default=dict)
    assembly_status: Mapped[AssemblyStatus] = mapped_column(
        Enum(AssemblyStatus), default=AssemblyStatus.idle
    )
    final_output: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    assembly_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    characters: Mapped[list[Character]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    selections: Mapped[list[NovelSelection]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    scenes: Mapped[list[Scene]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    shots: Mapped[list[Shot]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class Character(Base):
    __tablename__ = "characters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    positive_prompt: Mapped[str] = mapped_column(Text, default="")
    negative_prompt: Mapped[str] = mapped_column(Text, default="")
    reference_image: Mapped[str | None] = mapped_column(String(500), nullable=True)
    default_ipadapter_weight: Mapped[float] = mapped_column(Float, default=0.65)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    project: Mapped[Project] = relationship(back_populates="characters")


class NovelSelection(Base):
    __tablename__ = "novel_selections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, index=True)
    title: Mapped[str] = mapped_column(String(300))
    source_text: Mapped[str] = mapped_column(Text)
    char_start: Mapped[int] = mapped_column(Integer, default=0)
    char_end: Mapped[int] = mapped_column(Integer, default=0)
    selected: Mapped[bool] = mapped_column(Boolean, default=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    process_count: Mapped[int] = mapped_column(Integer, default=0)
    last_processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    project: Mapped[Project] = relationship(back_populates="selections")


class Scene(Base):
    __tablename__ = "scenes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(200))
    location: Mapped[str] = mapped_column(String(200), default="")
    time_of_day: Mapped[str] = mapped_column(String(80), default="")
    weather: Mapped[str] = mapped_column(String(80), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    source_text: Mapped[str] = mapped_column(Text, default="")

    project: Mapped[Project] = relationship(back_populates="scenes")
    shots: Mapped[list[Shot]] = relationship(back_populates="scene")


class Shot(Base):
    __tablename__ = "shots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    scene_id: Mapped[str | None] = mapped_column(
        ForeignKey("scenes.id", ondelete="SET NULL"), nullable=True
    )
    code: Mapped[str] = mapped_column(String(40), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    duration: Mapped[float] = mapped_column(Float, default=2.0)
    fps: Mapped[int] = mapped_column(Integer, default=8)
    frames: Mapped[int] = mapped_column(Integer, default=16)
    width: Mapped[int] = mapped_column(Integer, default=512)
    height: Mapped[int] = mapped_column(Integer, default=512)
    shot_type: Mapped[str] = mapped_column(String(80), default="medium shot")
    camera: Mapped[str] = mapped_column(String(100), default="static")
    action: Mapped[str] = mapped_column(String(300), default="")
    emotion: Mapped[str] = mapped_column(String(100), default="neutral")
    dialogue: Mapped[str | None] = mapped_column(Text, nullable=True)
    character_ids: Mapped[list] = mapped_column(JSON, default=list)
    location: Mapped[str] = mapped_column(String(200), default="")
    motion_mode: Mapped[str] = mapped_column(String(40), default="free")
    motion_asset_id: Mapped[str | None] = mapped_column(
        ForeignKey("motion_assets.id"), nullable=True
    )
    workflow_key: Mapped[str] = mapped_column(String(20), default="03")
    positive_prompt: Mapped[str] = mapped_column(Text, default="")
    negative_prompt: Mapped[str] = mapped_column(Text, default="")
    seed: Mapped[int] = mapped_column(Integer, default=10001)
    status: Mapped[ShotStatus] = mapped_column(
        Enum(ShotStatus), default=ShotStatus.pending
    )
    output_file: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    source_text: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)

    project: Mapped[Project] = relationship(back_populates="shots")
    scene: Mapped[Scene | None] = relationship(back_populates="shots")
    motion_asset: Mapped[MotionAsset | None] = relationship()
    jobs: Mapped[list[RenderJob]] = relationship(
        back_populates="shot", cascade="all, delete-orphan"
    )


class MotionAsset(Base):
    __tablename__ = "motion_assets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    motion_id: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    action: Mapped[str] = mapped_column(String(100), index=True)
    speed: Mapped[str] = mapped_column(String(40), default="normal")
    direction: Mapped[str] = mapped_column(String(80), default="any")
    shot_type: Mapped[str] = mapped_column(String(80), default="full body")
    camera: Mapped[str] = mapped_column(String(80), default="static")
    source_type: Mapped[str] = mapped_column(String(40), default="generated")
    source_file: Mapped[str] = mapped_column(String(1000))
    preview_file: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    thumbnail_file: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    fps: Mapped[int] = mapped_column(Integer, default=8)
    frames: Mapped[int] = mapped_column(Integer, default=16)
    width: Mapped[int] = mapped_column(Integer, default=512)
    height: Mapped[int] = mapped_column(Integer, default=512)
    loopable: Mapped[bool] = mapped_column(Boolean, default=False)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class RenderJob(Base):
    __tablename__ = "render_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    shot_id: Mapped[str] = mapped_column(
        ForeignKey("shots.id", ondelete="CASCADE"), index=True
    )
    worker_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    comfy_prompt_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True
    )
    celery_task_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.queued)
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    submitted_workflow: Mapped[dict] = mapped_column(JSON, default=dict)
    output_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    shot: Mapped[Shot] = relationship(back_populates="jobs")


class AssetJob(Base):
    __tablename__ = "asset_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    job_type: Mapped[AssetJobType] = mapped_column(Enum(AssetJobType), index=True)
    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True
    )
    character_id: Mapped[str | None] = mapped_column(
        ForeignKey("characters.id", ondelete="CASCADE"), nullable=True
    )
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus), default=JobStatus.queued, index=True
    )
    worker_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    comfy_prompt_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    request_json: Mapped[dict] = mapped_column(JSON, default=dict)
    output_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
