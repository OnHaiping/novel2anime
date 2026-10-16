from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Novel2Anime"
    app_origin: str = "http://localhost:3000"
    secret_key: str = "development-only-change-me"
    database_url: str = "sqlite:///./data/novel2anime.db"
    redis_url: str = "redis://localhost:6379/0"
    data_root: Path = Path("/app/data")
    workflow_root: Path = Path("/app/workflows")
    comfyui_root: Path = Path("/comfyui")
    comfyui_workers: str = (
        "gpu0=http://host.docker.internal:8188,gpu1=http://host.docker.internal:8189"
    )
    comfyui_log_files: str = "/comfyui/logs/gpu0.log,/comfyui/logs/gpu1.log"
    comfyui_process_control: bool = False
    llm_base_url: str = "http://host.docker.internal:11434/v1"
    llm_api_key: str = ""
    llm_model: str = ""
    llm_timeout: int = 120
    render_timeout: int = 1800
    required_custom_nodes: list[str] = Field(
        default_factory=lambda: [
            "ComfyUI-AnimateDiff-Evolved",
            "ComfyUI-VideoHelperSuite",
            "ComfyUI_IPAdapter_plus",
            "comfyui_controlnet_aux",
        ]
    )

    @property
    def worker_map(self) -> dict[str, str]:
        workers: dict[str, str] = {}
        for item in self.comfyui_workers.split(","):
            if not item.strip() or "=" not in item:
                continue
            name, url = item.split("=", 1)
            workers[name.strip()] = url.strip().rstrip("/")
        return workers

    @property
    def log_paths(self) -> list[Path]:
        return [
            Path(item.strip())
            for item in self.comfyui_log_files.split(",")
            if item.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
