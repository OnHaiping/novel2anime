from __future__ import annotations

import json
import re
from typing import Any

import httpx

from ..config import get_settings


SYSTEM_PROMPT = """你是动漫分镜规划器。把小说内容拆为可生成的短镜头。
严格输出 JSON，不要 Markdown。角色必须明确区分成年人；无法判断年龄时不要生成成人内容。
每个镜头只描述一个主要动作，时长优先 2 秒。复杂动作拆成多个镜头。
输出结构：
{
  "characters": [{"name":"", "age":25, "description":"", "positive_prompt":""}],
  "scenes": [{
    "title":"", "location":"", "time_of_day":"", "weather":"", "summary":"", "source_text":"",
    "shots":[{
      "shot_type":"medium shot", "camera":"static", "action":"", "emotion":"neutral",
      "dialogue":null, "characters":[], "location":"", "source_text":""
    }]
  }]
}
只输出有效 JSON。"""


class LLMClient:
    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def configured(self) -> bool:
        return bool(self.settings.llm_model)

    async def plan(self, novel_text: str) -> dict[str, Any]:
        if not self.configured:
            raise RuntimeError("LLM_MODEL 未配置")
        headers = {"Content-Type": "application/json"}
        if self.settings.llm_api_key:
            headers["Authorization"] = f"Bearer {self.settings.llm_api_key}"
        payload = {
            "model": self.settings.llm_model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": novel_text},
            ],
        }
        async with httpx.AsyncClient(timeout=self.settings.llm_timeout) as client:
            response = await client.post(
                f"{self.settings.llm_base_url.rstrip('/')}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        return self._parse_json(content)

    @staticmethod
    def _parse_json(content: str) -> dict[str, Any]:
        content = content.strip()
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content, flags=re.S)
        data = json.loads(content)
        if not isinstance(data, dict) or "scenes" not in data:
            raise ValueError("LLM 返回结果缺少 scenes")
        return data
