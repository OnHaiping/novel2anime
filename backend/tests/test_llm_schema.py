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
