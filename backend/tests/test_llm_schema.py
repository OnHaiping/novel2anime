import asyncio
import json

import pytest
from pydantic import ValidationError

from app.services.llm import LLMClient, PlannedChunk


def test_fixed_llm_schema_accepts_expected_shape():
    result = PlannedChunk.model_validate(
        {
            "characters": [
                {
                    "name": "林澪",
                    "age": 25,
                    "description": "黑色长发",
                    "positive_prompt": "adult woman, long black hair",
                }
            ],
            "scenes": [
                {
                    "title": "雨夜站台",
                    "location": "车站",
                    "time_of_day": "night",
                    "weather": "rain",
                    "summary": "等待列车",
                    "source_text": "她站在雨中的站台。",
                    "shots": [
                        {
                            "shot_type": "medium shot",
                            "camera": "static",
                            "action": "她抬头看向列车",
                            "emotion": "alert",
                            "dialogue": None,
                            "characters": ["林澪"],
                            "location": "车站",
                            "source_text": "她抬起头。",
                        }
                    ],
                }
            ],
        }
    )

    assert result.scenes[0].shots[0].characters == ["林澪"]


def test_fixed_llm_schema_rejects_extra_fields():
    with pytest.raises(ValidationError):
        PlannedChunk.model_validate(
            {"characters": [], "scenes": [], "explanation": "x"}
        )


def test_llm_parser_accepts_json_code_fence():
    assert (
        LLMClient._parse_json('```json\n{"characters": [], "scenes": []}\n```')[
            "scenes"
        ]
        == []
    )


def test_llm_client_allows_request_scoped_connection_override():
    client = LLMClient(
        "cloud-model",
        base_url="https://provider.example/v1/",
        api_key="session-token",
    )
    assert client.model == "cloud-model"
    assert client.base_url == "https://provider.example/v1"
    assert client.api_key == "session-token"


def test_prompt_generation_uses_edited_plan(monkeypatch):
    client = LLMClient("test-model")
    captured_prompts: list[str] = []

    async def fake_request(user_prompt: str, *, system_prompt: str) -> str:
        captured_prompts.append(user_prompt)
        return json.dumps(
            {
                "items": [
                    {
                        "scene_index": 0,
                        "shot_index": 0,
                        "positive_prompt": "anime screencap, backlit cultivator",
                        "negative_prompt": "text, watermark, bad anatomy",
                    }
                ]
            }
        )

    monkeypatch.setattr(client, "_request", fake_request)
    edited_plan = {
        "characters": [],
        "scenes": [
            {
                "title": "人工修改后的审判场景",
                "location": "宗门大殿",
                "time_of_day": "day",
                "weather": "clear",
                "summary": "师尊背光质问主角",
                "source_text": "曾经的师尊背着光，高高在上地站在我身前。",
                "shots": [
                    {
                        "shot_type": "low angle wide shot",
                        "camera": "slow push in",
                        "action": "师尊背光站立并俯视主角",
                        "emotion": "oppressive",
                        "dialogue": "可知罪？",
                        "characters": ["师尊"],
                        "location": "宗门大殿",
                        "source_text": "曾经的师尊背着光，高高在上地站在我身前。",
                    }
                ],
            }
        ],
    }

    result = asyncio.run(client.generate_prompts(edited_plan))

    assert "人工修改后的审判场景" in captured_prompts[0]
    assert "low angle wide shot" in captured_prompts[0]
    assert result["scenes"][0]["shots"][0]["positive_prompt"].startswith(
        "anime screencap"
    )
