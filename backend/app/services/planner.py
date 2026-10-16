from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from ..models import Character, Project, ProjectStatus, Scene, Shot
from .llm import LLMClient, PlannedChunk
from .prompt_builder import build_prompts
from .router import classify_action


def heuristic_plan(text: str, max_shots: int = 30) -> dict[str, Any]:
    paragraphs = [item.strip() for item in re.split(r"\n\s*\n", text) if item.strip()]
    if not paragraphs:
        paragraphs = [text.strip()]
    scenes: list[dict[str, Any]] = []
    count = 0
    for scene_index, paragraph in enumerate(paragraphs, 1):
        if count >= max_shots:
            break
        sentences = [
            s.strip() for s in re.split(r"(?<=[。！？!?])", paragraph) if s.strip()
        ]
        shots = []
        for sentence in sentences:
            if count >= max_shots:
                break
            count += 1
            dialogue_match = re.search(r"[“\"]([^”\"]+)[”\"]", sentence)
            shots.append(
                {
                    "shot_type": "medium shot" if dialogue_match else "wide shot",
                    "camera": "static",
                    "action": sentence[:160],
                    "emotion": "neutral",
                    "dialogue": dialogue_match.group(1) if dialogue_match else None,
                    "characters": [],
                    "location": "",
                    "source_text": sentence,
                }
            )
        scenes.append(
            {
                "title": f"场景 {scene_index}",
                "location": "",
                "time_of_day": "",
                "weather": "",
                "summary": paragraph[:200],
                "source_text": paragraph,
                "shots": shots,
            }
        )
    return {"characters": [], "scenes": scenes}


async def create_plan(
    db: Session,
    project: Project,
    use_llm: bool,
    max_shots: int,
    target_shot_seconds: float = 2.0,
    selections: list[tuple[str, str]] | None = None,
    append_to_timeline: bool = False,
    llm_model: str | None = None,
    llm_base_url: str | None = None,
    llm_api_key: str | None = None,
    llm_protocol: str | None = None,
) -> tuple[int, int, int]:
    plan = await generate_plan(
        project,
        use_llm,
        max_shots,
        selections,
        llm_model,
        llm_base_url,
        llm_api_key,
        llm_protocol,
    )
    return apply_plan(
        db,
        project,
        plan,
        max_shots=max_shots,
        target_shot_seconds=target_shot_seconds,
        append_to_timeline=append_to_timeline,
    )


async def generate_plan(
    project: Project,
    use_llm: bool,
    max_shots: int,
    selections: list[tuple[str, str]] | None = None,
    llm_model: str | None = None,
    llm_base_url: str | None = None,
    llm_api_key: str | None = None,
    llm_protocol: str | None = None,
) -> dict[str, Any]:
    client = LLMClient(
        llm_model,
        base_url=llm_base_url,
        api_key=llm_api_key,
        protocol=llm_protocol,
    )
    selected = selections or []
    if use_llm:
        if not client.configured:
            raise RuntimeError(
                "已选择使用大模型，但尚未选择模型；请先刷新模型列表并选择模型"
            )
        plan = {"characters": [], "scenes": []}
        known: dict[str, dict[str, Any]] = {
            character.name: {
                "name": character.name,
                "age": character.age,
                "description": character.description,
                "positive_prompt": character.positive_prompt,
            }
            for character in project.characters
        }
        planned_shots = 0
        for selection_title, selection_text in selected:
            result = await client.plan_chunk(
                selection_text,
                selection_title=selection_title,
                known_characters=list(known.values()),
            )
            for character in result.get("characters", []):
                name = character.get("name", "").strip()
                if name:
                    known[name] = {**known.get(name, {}), **character}
            scenes = result.get("scenes", [])
            plan["scenes"].extend(scenes)
            planned_shots += sum(len(scene.get("shots", [])) for scene in scenes)
            if planned_shots >= max_shots:
                break
        plan["characters"] = list(known.values())
    else:
        combined = "\n\n".join(
            f"{title}\n{text}" for title, text in selected if text.strip()
        )
        plan = heuristic_plan(combined, max_shots=max_shots)
    return PlannedChunk.model_validate(plan).model_dump()


def apply_plan(
    db: Session,
    project: Project,
    plan: dict[str, Any],
    *,
    max_shots: int,
    target_shot_seconds: float = 2.0,
    append_to_timeline: bool = False,
) -> tuple[int, int, int]:
    plan = PlannedChunk.model_validate(plan).model_dump()

    if not append_to_timeline:
        for shot in list(project.shots):
            db.delete(shot)
        for scene in list(project.scenes):
            db.delete(scene)
        db.flush()

    # 重建分镜时保留手工上传的角色和参考图，并用规划结果补充角色描述。
    character_by_name: dict[str, Character] = {
        character.name: character for character in project.characters
    }
    for item in plan.get("characters", []):
        age = item.get("age")
        if age is not None and int(age) < 18:
            age = None
        name = item.get("name") or "未命名角色"
        character = character_by_name.get(name)
        if character is None:
            character = Character(project_id=project.id, name=name)
            db.add(character)
        if age is not None:
            character.age = age
        character.description = item.get("description") or character.description
        character.positive_prompt = (
            item.get("positive_prompt") or character.positive_prompt
        )
        db.flush()
        character_by_name[character.name] = character

    scene_offset = (
        max((scene.sequence for scene in project.scenes), default=0)
        if append_to_timeline
        else 0
    )
    shot_sequence = (
        max((shot.sequence for shot in project.shots), default=0)
        if append_to_timeline
        else 0
    )
    generated_shots = 0
    for relative_scene_sequence, scene_data in enumerate(plan.get("scenes", []), 1):
        scene_sequence = scene_offset + relative_scene_sequence
        scene = Scene(
            project_id=project.id,
            sequence=scene_sequence,
            title=scene_data.get("title") or f"场景 {scene_sequence}",
            location=scene_data.get("location", ""),
            time_of_day=scene_data.get("time_of_day", ""),
            weather=scene_data.get("weather", ""),
            summary=scene_data.get("summary", ""),
            source_text=scene_data.get("source_text", ""),
        )
        db.add(scene)
        db.flush()
        for shot_data in scene_data.get("shots", []):
            if generated_shots >= max_shots:
                break
            shot_sequence += 1
            generated_shots += 1
            names = shot_data.get("characters", [])
            if not names and len(character_by_name) == 1:
                names = list(character_by_name)
            character_ids = [
                character_by_name[name].id
                for name in names
                if name in character_by_name
            ]
            motion_class = classify_action(shot_data.get("action", ""))
            workflow_key = (
                "02"
                if not character_ids
                else ("04" if motion_class in {"common", "complex"} else "03")
            )
            motion_mode = "pose_required" if workflow_key == "04" else "free"
            positive, negative = build_prompts(
                shot_data=shot_data,
                characters=[
                    character_by_name[name]
                    for name in names
                    if name in character_by_name
                ],
                scene=scene,
            )
            if shot_data.get("positive_prompt"):
                positive = f"{positive}, {shot_data['positive_prompt']}"
            if shot_data.get("negative_prompt"):
                negative = f"{negative}, {shot_data['negative_prompt']}"
            shot = Shot(
                project_id=project.id,
                scene_id=scene.id,
                code=f"S{shot_sequence:04d}",
                sequence=shot_sequence,
                duration=target_shot_seconds,
                frames=max(8, round(target_shot_seconds * 8)),
                shot_type=shot_data.get("shot_type", "medium shot"),
                camera=shot_data.get("camera", "static"),
                action=shot_data.get("action", ""),
                emotion=shot_data.get("emotion", "neutral"),
                dialogue=shot_data.get("dialogue"),
                character_ids=character_ids,
                location=shot_data.get("location") or scene.location,
                motion_mode=motion_mode,
                workflow_key=workflow_key,
                positive_prompt=positive,
                negative_prompt=negative,
                seed=10000 + shot_sequence,
                source_text=shot_data.get("source_text", ""),
                metadata_json={"motion_class": motion_class},
            )
            db.add(shot)

    project.status = ProjectStatus.planned
    db.commit()
    return len(character_by_name), len(plan.get("scenes", [])), generated_shots
