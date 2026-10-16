from __future__ import annotations

from typing import Any

from ..models import Character, Scene


BASE_POSITIVE = (
    "masterpiece, best quality, anime screencap, clean anime lineart, cel shading"
)
BASE_NEGATIVE = (
    "worst quality, low quality, lowres, bad anatomy, bad hands, extra fingers, missing fingers, "
    "fused fingers, deformed limbs, deformed face, duplicate, multiple views, text, logo, watermark, "
    "signature, photorealistic, 3d, CGI, flicker, frame inconsistency, temporal artifacts, motion smear"
)


def build_prompts(
    shot_data: dict[str, Any], characters: list[Character], scene: Scene
) -> tuple[str, str]:
    positive_parts = [BASE_POSITIVE]
    negative_parts = [BASE_NEGATIVE]
    for character in characters:
        positive_parts.append(character.name)
        if character.age is not None:
            positive_parts.append(f"adult {character.age}-year-old character")
        if character.description:
            positive_parts.append(character.description)
        if character.positive_prompt:
            positive_parts.append(character.positive_prompt)
        if character.negative_prompt:
            negative_parts.append(character.negative_prompt)
    for value in [
        shot_data.get("emotion"),
        shot_data.get("action"),
        shot_data.get("shot_type"),
        shot_data.get("camera"),
        shot_data.get("location") or scene.location,
        scene.time_of_day,
        scene.weather,
    ]:
        if value:
            positive_parts.append(str(value))
    if characters:
        positive_parts.append("same character as reference image")
        negative_parts.append(
            "different character, inconsistent hair, inconsistent clothes"
        )
    return ", ".join(positive_parts), ", ".join(negative_parts)
