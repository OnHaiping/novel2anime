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

    async def _request(self, user_prompt: str) -> str:
        headers = {"Content-Type": "application/json"}
        if self.settings.llm_api_key:
            headers["Authorization"] = f"Bearer {self.settings.llm_api_key}"
        payload = {
            "model": self.settings.llm_model,
            "temperature": 0.15,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        }
        url = f"{self.settings.llm_base_url.rstrip('/')}/chat/completions"
        async with httpx.AsyncClient(timeout=self.settings.llm_timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code == 400:
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
