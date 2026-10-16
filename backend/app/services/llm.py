from __future__ import annotations

import json
import re
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..config import get_settings


class PlannedCharacter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    age: int | None = None
    description: str = ""
    positive_prompt: str = ""


class PlannedShot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    shot_type: str = "medium shot"
    camera: str = "static"
    action: str
    emotion: str = "neutral"
    dialogue: str | None = None
    characters: list[str] = Field(default_factory=list)
    location: str = ""
    source_text: str = ""
    positive_prompt: str = ""
    negative_prompt: str = ""


class PlannedScene(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    location: str = ""
    time_of_day: str = ""
    weather: str = ""
    summary: str = ""
    source_text: str = ""
    shots: list[PlannedShot]


class PlannedChunk(BaseModel):
    model_config = ConfigDict(extra="forbid")
    characters: list[PlannedCharacter] = Field(default_factory=list)
    scenes: list[PlannedScene]


class PromptItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scene_index: int = Field(ge=0)
    shot_index: int = Field(ge=0)
    positive_prompt: str
    negative_prompt: str


class PromptBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[PromptItem]


SYSTEM_PROMPT = """你是专业的日本动画编剧与分镜师。把给定小说片段转换为严格结构化的制作数据。
规则：
1. 只使用原文中确实发生的剧情，不续写后续内容。
2. 场景按地点、时间或连续动作变化切分；每个镜头只包含一个主要动作，建议 1～3 秒。
3. characters 必须使用稳定、完整的人名；代词要解析到已有角色。无法确定姓名时使用有区分度的临时名称。
4. age 只在原文明示或能够可靠判断时填写；不得把年龄不明角色描述为未成年人或用于成人内容。
5. source_text 必须保留对应原文的短摘录，不能编造。
6. action、description 和提示词要具体、视觉可生成。positive_prompt 使用简洁英文标签。
7. 返回值只能是一个 JSON 对象，不要 Markdown、解释、注释或代码围栏。
8. 字段必须严格匹配提供的 JSON Schema，不得增加字段。
"""

PROMPT_SYSTEM = """你是 Stable Diffusion/AnimateDiff 的日本动画提示词工程师。
根据 JSON 中已经由人工微调确认的角色、场景、镜头，以及每个镜头的 source_text 原文，为每个镜头生成英文提示词。
要求：
1. 不得改变、补写或重新解释结构化剧情；只生成 positive_prompt 和 negative_prompt。
2. 正向提示词必须包含可视化的角色外貌、服装、动作、情绪、构图、机位、环境、光线和日漫赛璐璐风格。
3. 对同一角色复用完全一致的核心外观词，避免不同镜头漂移。
4. 不要把对白正文绘制为画面文字。
5. 负向提示词包含画质、人体、文字水印和时序一致性问题，并补充该镜头特有风险。
6. scene_index 和 shot_index 使用输入中的零基索引，不得遗漏或增加镜头。
7. 只返回符合 JSON Schema 的 JSON 对象，不要 Markdown 或解释。
"""


class LLMClient:
    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def configured(self) -> bool:
        return bool(self.settings.llm_model)

    async def plan_chunk(
        self,
        novel_text: str,
        *,
        selection_title: str = "",
        known_characters: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if not self.configured:
            raise RuntimeError("LLM_MODEL 未配置")
        schema = PlannedChunk.model_json_schema()
        context = json.dumps(known_characters or [], ensure_ascii=False)
        user_prompt = (
            f"人工选段：{selection_title or '未命名选段'}\n"
            f"已知角色设定（保持姓名一致，可能为空）：{context}\n\n"
            f"必须遵守的 JSON Schema：\n{json.dumps(schema, ensure_ascii=False)}\n\n"
            f"小说原文：\n{novel_text}"
        )
        last_error = ""
        for attempt in range(self.settings.llm_max_retries + 1):
            correction = (
                ""
                if not last_error
                else f"\n上一次输出校验失败：{last_error}\n请修正并重新输出完整 JSON。"
            )
            content = await self._request(user_prompt + correction)
            try:
                raw = self._parse_json(content)
                return PlannedChunk.model_validate(raw).model_dump()
            except (ValueError, ValidationError, json.JSONDecodeError) as exc:
                last_error = str(exc)[:2000]
                if attempt >= self.settings.llm_max_retries:
                    raise ValueError(
                        f"大模型连续返回无效分镜 JSON：{last_error}"
                    ) from exc
        raise RuntimeError("无法生成分镜")

    async def generate_prompts(self, plan: dict[str, Any]) -> dict[str, Any]:
        if not self.configured:
            raise RuntimeError("LLM_MODEL 未配置，无法使用大模型生成提示词")
        validated = PlannedChunk.model_validate(plan).model_dump()
        schema = PromptBatch.model_json_schema()
        for scene_index, scene in enumerate(validated["scenes"]):
            material = {
                "characters": validated["characters"],
                "scene": {
                    "scene_index": scene_index,
                    **scene,
                    "shots": [
                        {"shot_index": shot_index, **shot}
                        for shot_index, shot in enumerate(scene["shots"])
                    ],
                },
            }
            user_prompt = (
                f"必须遵守的 JSON Schema：\n{json.dumps(schema, ensure_ascii=False)}\n\n"
                f"人工确认后的制作 JSON：\n{json.dumps(material, ensure_ascii=False)}"
            )
            expected = {
                (scene_index, shot_index) for shot_index, _ in enumerate(scene["shots"])
            }
            last_error = ""
            for attempt in range(self.settings.llm_max_retries + 1):
                correction = (
                    ""
                    if not last_error
                    else f"\n上一次输出校验失败：{last_error}\n请重新输出完整 JSON。"
                )
                content = await self._request(
                    user_prompt + correction, system_prompt=PROMPT_SYSTEM
                )
                try:
                    batch = PromptBatch.model_validate(self._parse_json(content))
                    received = {
                        (item.scene_index, item.shot_index) for item in batch.items
                    }
                    if received != expected or len(batch.items) != len(expected):
                        raise ValueError(
                            f"镜头索引不完整，expected={sorted(expected)}, received={sorted(received)}"
                        )
                    for item in batch.items:
                        shot = validated["scenes"][item.scene_index]["shots"][
                            item.shot_index
                        ]
                        shot["positive_prompt"] = item.positive_prompt
                        shot["negative_prompt"] = item.negative_prompt
                    break
                except (ValueError, ValidationError, json.JSONDecodeError) as exc:
                    last_error = str(exc)[:2000]
                    if attempt >= self.settings.llm_max_retries:
                        raise ValueError(
                            f"场景 {scene_index + 1} 连续返回无效提示词 JSON：{last_error}"
                        ) from exc
        return validated

    async def _request(
        self, user_prompt: str, *, system_prompt: str = SYSTEM_PROMPT
    ) -> str:
        headers = {"Content-Type": "application/json"}
        if self.settings.llm_api_key:
            headers["Authorization"] = f"Bearer {self.settings.llm_api_key}"
        payload = {
            "model": self.settings.llm_model,
            "temperature": 0.15,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        url = f"{self.settings.llm_base_url.rstrip('/')}/chat/completions"
        async with httpx.AsyncClient(timeout=self.settings.llm_timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code in {400, 422}:
                payload.pop("response_format", None)
                response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    @staticmethod
    def _parse_json(content: str) -> dict[str, Any]:
        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.S)
        data = json.loads(content)
        if not isinstance(data, dict):
            raise ValueError("根节点必须是 JSON 对象")
        return data
