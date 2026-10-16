from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from ..config import get_settings
from ..models import Shot


def _run(command: list[str]) -> None:
    result = subprocess.run(
        command, capture_output=True, text=True, timeout=3600, check=False
    )
    if result.returncode != 0:
        message = (result.stderr or result.stdout)[-4000:]
        raise RuntimeError(f"FFmpeg 执行失败（exit={result.returncode}）：{message}")


def _concat_line(path: Path) -> str:
    escaped = str(path).replace("'", "'\\''")
    return f"file '{escaped}'\n"


def resolve_shot_output(shot: Shot) -> Path:
    if not shot.output_file:
        raise ValueError(f"镜头 {shot.code} 没有输出文件")
    candidate = Path(shot.output_file)
    if not candidate.is_absolute():
        candidate = get_settings().comfyui_root / "output" / candidate
    candidate = candidate.resolve()
    output_root = (get_settings().comfyui_root / "output").resolve()
    if output_root not in candidate.parents and candidate != output_root:
        raise ValueError(f"镜头 {shot.code} 的输出路径不在 ComfyUI output 中")
    if not candidate.is_file():
        raise FileNotFoundError(f"镜头 {shot.code} 输出不存在：{candidate}")
    return candidate


def assemble_project(
    project_id: str,
    shots: list[Shot],
    *,
    width: int = 1024,
    height: int = 576,
    fps: int = 24,
    crf: int = 18,
) -> Path:
    if not shots:
        raise ValueError("项目没有可合成的镜头")

    settings = get_settings()
    final_dir = settings.data_root / "projects" / project_id / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    final_path = final_dir / "final.mp4"

    with tempfile.TemporaryDirectory(prefix="novel2anime-") as temp_name:
        temp_dir = Path(temp_name)
        normalized: list[Path] = []
        for index, shot in enumerate(shots):
            source = resolve_shot_output(shot)
            target = temp_dir / f"{index:05d}.mp4"
            # 保持比例，空余处填黑边；所有镜头统一编码、尺寸、帧率和时基后再拼接。
            vf = (
                f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps}"
            )
            _run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(source),
                    "-an",
                    "-vf",
                    vf,
                    "-c:v",
                    "libx264",
                    "-preset",
                    "medium",
                    "-crf",
                    str(crf),
                    "-pix_fmt",
                    "yuv420p",
                    "-movflags",
                    "+faststart",
                    str(target),
                ]
            )
            normalized.append(target)

        concat_file = temp_dir / "concat.txt"
        concat_file.write_text(
            "".join(_concat_line(path) for path in normalized), encoding="utf-8"
        )
        staged = temp_dir / "final.mp4"
        _run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file),
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                str(staged),
            ]
        )
        shutil.copy2(staged, final_path)

    return final_path
