from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import MotionAsset, Shot


COMMON = (
    "走",
    "行走",
    "坐下",
    "起身",
    "站起",
    "转身",
    "挥手",
    "walk",
    "sit",
    "stand up",
    "turn",
    "wave",
)
COMPLEX = (
    "跑",
    "跳",
    "战斗",
    "打斗",
    "舞蹈",
    "追逐",
    "run",
    "jump",
    "fight",
    "dance",
    "chase",
)
MICRO = (
    "眨眼",
    "呼吸",
    "看向",
    "回头",
    "点头",
    "说",
    "blink",
    "breathe",
    "look",
    "nod",
    "talk",
)


def classify_action(action: str) -> str:
    lowered = action.lower()
    if any(word in lowered for word in COMPLEX):
        return "complex"
    if any(word in lowered for word in COMMON):
        return "common"
    if any(word in lowered for word in MICRO):
        return "micro"
    return "none"


def match_motion(db: Session, shot: Shot) -> MotionAsset | None:
    assets = db.scalars(select(MotionAsset)).all()
    best: tuple[int, MotionAsset] | None = None
    text = f"{shot.action} {shot.shot_type} {shot.camera}".lower()
    for asset in assets:
        score = 0
        if asset.action.lower() in text or any(
            str(tag).lower() in text for tag in asset.tags
        ):
            score += 50
        if asset.shot_type.lower() == shot.shot_type.lower():
            score += 10
        if asset.camera.lower() == shot.camera.lower():
            score += 10
        if asset.frames == shot.frames:
            score += 10
        if best is None or score > best[0]:
            best = (score, asset)
    return best[1] if best and best[0] >= 50 else None
