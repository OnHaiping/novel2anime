from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.models import JobStatus, RenderJob, Shot, ShotStatus
from app.main import app
from app.config import get_settings


def test_manual_text_selection_and_append_timeline(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'api.db'}", connect_args={"check_same_thread": False}
    )
    testing_session = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)

    def override_db():
        with testing_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(get_settings(), "data_root", tmp_path / "data")
    monkeypatch.setattr(get_settings(), "comfyui_root", tmp_path / "comfyui")
    client = TestClient(app)
    try:
        project = client.post("/api/projects", json={"name": "长篇测试"}).json()
        novel_text = "第一章 雨夜\n她走进站台。\n\n第二章 清晨\n列车到站。"
        response = client.post(
            f"/api/projects/{project['id']}/novel",
            data={"novel_type": "long"},
            files={
                "file": (
                    "novel.txt",
                    novel_text,
                    "text/plain",
                )
            },
        )
        assert response.status_code == 200

        content = client.get(f"/api/projects/{project['id']}/novel-content").json()
        assert content["text"] == novel_text
        assert content["novel_type"] == "long"
        assert client.get(f"/api/projects/{project['id']}/selections").json() == []

        response = client.post(
            f"/api/projects/{project['id']}/plan",
            json={"use_llm": False, "selection_ids": []},
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "至少选择一条已记录选段"

        first_text = "她走进站台。"
        second_text = "列车到站。"
        first_start = novel_text.index(first_text)
        second_start = novel_text.index(second_text)
        first_selection = client.post(
            f"/api/projects/{project['id']}/selections",
            json={
                "title": "雨夜站台",
                "char_start": first_start,
                "char_end": first_start + len(first_text),
            },
        ).json()
        second_selection = client.post(
            f"/api/projects/{project['id']}/selections",
            json={
                "title": "清晨列车",
                "char_start": second_start,
                "char_end": second_start + len(second_text),
            },
        ).json()
        assert first_selection["source_text"] == first_text
        assert second_selection["source_text"] == second_text

        first = client.post(
            f"/api/projects/{project['id']}/plan-draft",
            json={"use_llm": False, "selection_ids": [first_selection["id"]]},
        )
        assert first.status_code == 200
        draft = first.json()["draft"]
        draft["scenes"][0]["shots"][0]["positive_prompt"] = "cinematic test prompt"
        saved = client.put(
            f"/api/projects/{project['id']}/plan-draft", json={"draft": draft}
        )
        assert saved.status_code == 200
        applied = client.post(
            f"/api/projects/{project['id']}/plan-draft/apply",
            json={"append_to_timeline": False, "max_shots": 30},
        )
        assert applied.status_code == 200

        second = client.post(
            f"/api/projects/{project['id']}/plan-draft",
            json={
                "use_llm": False,
                "selection_ids": [second_selection["id"]],
            },
        )
        assert second.status_code == 200
        appended = client.post(
            f"/api/projects/{project['id']}/plan-draft/apply",
            json={"append_to_timeline": True, "max_shots": 30},
        )
        assert appended.status_code == 200
        shots = client.get(f"/api/projects/{project['id']}/shots").json()
        assert [shot["code"] for shot in shots] == ["S0001", "S0002"]
        assert "cinematic test prompt" in shots[0]["positive_prompt"]
        selections = client.get(f"/api/projects/{project['id']}/selections").json()
        assert [item["process_count"] for item in selections] == [1, 1]
        assert all(item["last_processed_at"] for item in selections)

        output_path = tmp_path / "comfyui" / "output" / "project" / "clip.mp4"
        output_path.parent.mkdir(parents=True)
        output_path.write_bytes(b"fake-mp4")
        with testing_session() as session:
            shot = session.get(Shot, shots[0]["id"])
            shot.status = ShotStatus.completed
            shot.output_file = "project/clip.mp4"
            session.add(
                RenderJob(
                    shot_id=shot.id,
                    worker_name="gpu0",
                    comfy_prompt_id="prompt-1",
                    status=JobStatus.completed,
                    output_metadata={"files": [{"filename": "clip.mp4"}]},
                )
            )
            session.commit()

        result = client.get(f"/api/renders/shots/{shots[0]['id']}/result")
        assert result.status_code == 200
        assert result.json()["worker_name"] == "gpu0"
        output = client.get(f"/api/renders/shots/{shots[0]['id']}/output")
        assert output.status_code == 200
        assert output.content == b"fake-mp4"
    finally:
        client.close()
        app.dependency_overrides.clear()
