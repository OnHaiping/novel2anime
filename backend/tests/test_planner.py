import asyncio

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Character, Project
from app.services.planner import create_plan, heuristic_plan


def test_heuristic_plan_creates_shots():
    result = heuristic_plan("雨落在站台上。\n\n她看向远处的列车。")
    assert len(result["scenes"]) == 2
    assert sum(len(scene["shots"]) for scene in result["scenes"]) == 2


def test_replanning_preserves_manual_character_and_reference():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        project = Project(name="样片", novel_text="她走到窗边。")
        db.add(project)
        db.flush()
        character = Character(
            project_id=project.id,
            name="主角",
            age=25,
            reference_image="projects/reference.png",
        )
        db.add(character)
        db.commit()

        asyncio.run(
            create_plan(db, project, False, 10, 2.5, [("人工选段", project.novel_text)])
        )
        db.refresh(character)

        assert character.reference_image == "projects/reference.png"
        assert project.shots[0].character_ids == [character.id]
        assert project.shots[0].workflow_key == "04"
        assert project.shots[0].frames == 20
