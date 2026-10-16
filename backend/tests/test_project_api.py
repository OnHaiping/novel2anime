from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
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
            f"/api/projects/{project['id']}/plan",
            json={"use_llm": False, "selection_ids": [first_selection["id"]]},
        )
        assert first.status_code == 200
        second = client.post(
            f"/api/projects/{project['id']}/plan",
            json={
                "use_llm": False,
                "append_to_timeline": True,
                "selection_ids": [second_selection["id"]],
            },
        )
        assert second.status_code == 200
        shots = client.get(f"/api/projects/{project['id']}/shots").json()
        assert [shot["code"] for shot in shots] == ["S0001", "S0002"]
        selections = client.get(f"/api/projects/{project['id']}/selections").json()
        assert [item["process_count"] for item in selections] == [1, 1]
        assert all(item["last_processed_at"] for item in selections)
    finally:
        client.close()
        app.dependency_overrides.clear()
