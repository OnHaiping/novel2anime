# Novel2Anime

把小说文本拆成结构化分镜，自动选择 ComfyUI 工作流，并在两张 GPU 上排队生成动漫镜头的本地系统。

完整的数据流、人工选段、固定 LLM JSON、立绘和动作库说明见 [`docs/SYSTEM_WORKFLOW.md`](docs/SYSTEM_WORKFLOW.md)。

当前版本是可运行的 MVP，包含：

- FastAPI 后端与 OpenAPI 文档；
- React 管理界面；
- PostgreSQL 项目数据库；
- Redis + Celery 渲染队列；
- ComfyUI API 客户端；
- 双 ComfyUI Worker 调度；
- 长篇/短篇类型选择、原文展示、人工划线选段记录与严格 LLM JSON 校验；
- 可编辑角色设定、参考图上传、AI 立绘生成与 IPAdapter；
- 动作库上传、AI 动作草稿生成、动作匹配与 FFmpeg 标准化；
- Web 模型目录与基于 `curl` 的断点续传下载器；
- FFmpeg 镜头规格统一与最终 MP4 拼接；
- AnimateDiff / IPAdapter / OpenPose 三套 API 工作流；
- ComfyUI 节点、模型、队列、日志诊断；
- Docker Compose 部署。

## 架构

```text
Browser :3300
    │
    ▼
React / Nginx
    │ /api
    ▼
FastAPI :3301（容器内 :8000） ───── PostgreSQL
    │                    │
    └──── Redis/Celery ──┘
              │
              ├── ComfyUI GPU0 :8188
              └── ComfyUI GPU1 :8189
```

ComfyUI 使用宿主机现有 Conda 环境运行。Web、API、数据库和任务队列由 Docker Compose 管理。这样可以直接复用 `/work/comfyui/main` 中已经安装的 CUDA、模型和自定义节点。

## 前提

- Linux GPU 服务器；
- Docker Engine 与 Compose v2；
- NVIDIA 驱动；
- Conda 环境名为 `comfyui`；
- ComfyUI 位于 `/work/comfyui/main`；
- 在该环境中能运行 `python main.py --enable-manager`；
- FFmpeg；
- 模型和自定义节点已经按下方清单安装。

## 1. 克隆与配置

```bash
cd /work
git clone https://github.com/OnHaiping/novel2anime.git
cd novel2anime
cp .env.example .env
```

必须修改 `.env`：

```dotenv
POSTGRES_PASSWORD=使用强密码
SECRET_KEY=使用长随机字符串
FRONTEND_PORT=3300
BACKEND_PORT=3301
APP_ORIGIN=http://服务器IP:3300
```

如使用本地 Ollama/vLLM/OpenAI-compatible 服务：

```dotenv
LLM_BASE_URL=http://host.docker.internal:11434/v1
LLM_MODEL=
LLM_API_KEY=
LLM_MAX_SELECTION_CHARS=12000
LLM_MAX_RETRIES=2
```

`LLM_BASE_URL` 和 `LLM_API_KEY` 是服务器级连接配置；`LLM_MODEL` 仅作为可选默认值，不再写死实际使用的模型。项目工作台会调用兼容接口的 `GET /v1/models` 显示可用模型，允许刷新、选择或手动输入模型 ID，并把选择保存在当前项目。分镜规划和提示词生成都会使用该项目模型。没有选择模型时会明确报错；只有主动关闭“使用大模型”才会启用仅供测试的启发式分镜。

## 2. 启动 ComfyUI

脚本会使用现有 Conda 环境，并把日志写入 `/work/comfyui/main/logs/`：

```bash
chmod +x scripts/*.sh
./scripts/start-comfyui.sh dual
```

等价命令：

```bash
cd /work/comfyui/main

CUDA_VISIBLE_DEVICES=0 conda run -n comfyui --no-capture-output \
  python main.py --enable-manager --listen 0.0.0.0 --port 8188

CUDA_VISIBLE_DEVICES=1 conda run -n comfyui --no-capture-output \
  python main.py --enable-manager --listen 0.0.0.0 --port 8189
```

注意：每个进程只看到一张 GPU。两张 8GB 显卡不会合并为 16GB，但能并行生成两个镜头。

如果只运行一个实例：

```bash
./scripts/start-comfyui.sh single
```

并将 `.env` 改成：

```dotenv
COMFYUI_WORKERS=gpu0=http://host.docker.internal:8188
COMFYUI_LOG_FILES=/comfyui/logs/gpu0.log
```

## 3. 启动系统

```bash
./scripts/bootstrap.sh
docker compose up -d
docker compose logs -f --tail=200
```

如果 Web 显示 `502 Bad Gateway`，它表示前端 Nginx 无法连接后端，不表示 ComfyUI 模型缺失。先执行：

```bash
docker compose ps
curl -i http://127.0.0.1:3301/api/system/health
docker compose logs --tail=200 backend
```

后端健康但 Web 仍为 502 时执行 `docker compose restart frontend`。当前 Compose 已为 backend 增加健康检查，前端也会动态重新解析被重建后的 backend 容器地址。

访问：

- Web：<http://服务器地址:3300>
- API 文档：<http://服务器地址:3301/docs>
- 健康检查：<http://服务器地址:3301/api/system/health>
- 系统诊断：<http://服务器地址:3301/api/system/diagnostics>

## 4. 必需模型

完整下载来源、自动安装脚本以及 `.ckpt` 兼容说明见 [`docs/COMFYUI_SETUP.md`](docs/COMFYUI_SETUP.md)。

```text
/work/comfyui/main/models/checkpoints/meinamix_meinaV11.safetensors
/work/comfyui/main/models/animatediff_models/mm_sd_v15_v2.ckpt
/work/comfyui/main/models/ipadapter/ip-adapter-plus_sd15.safetensors
/work/comfyui/main/models/clip_vision/CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors
/work/comfyui/main/models/controlnet/control_v11p_sd15_openpose.pth
/work/comfyui/main/models/controlnet/control_v11p_sd15_openpose.yaml
```

必需节点：

```text
ComfyUI-AnimateDiff-Evolved
ComfyUI-VideoHelperSuite
ComfyUI_IPAdapter_plus
comfyui_controlnet_aux
```

运行诊断：

```bash
./scripts/doctor.sh
```

诊断会检查：

- 两个 ComfyUI 实例是否在线；
- `/system_stats` 和 `/queue`；
- 必需模型是否存在及大小；
- `/object_info` 是否包含必需节点；
- 自定义节点目录；
- ComfyUI 日志尾部；
- 缺失模型和离线 Worker 汇总。

## 5. 使用流程

1. 在 Web 中新建项目，选择“长篇小说”或“短篇小说”，上传 UTF-8 `.txt`/`.md`。
2. 系统原样显示小说，不自动识别章节或切块。在原文中拖动划线，保存一个或多个有标题的选段记录。
3. 勾选本次处理的选段，并设置最大镜头数。单条选段不能超过 `LLM_MAX_SELECTION_CHARS`。
4. 在项目的“大模型选择”中刷新服务模型列表，选择模型（也可手动输入模型 ID）并保存，然后启用大模型并点击“生成可编辑 JSON 草案”。后端把每条选段原样提交给该项目选择的模型，并使用固定 JSON Schema 校验；无效结果会自动重试。
5. 在页面中人工修改场景、镜头、动作、对白等 JSON，点击“校验并保存 JSON”。草案同时持久化到 `data/projects/<项目ID>/plans/plan_draft.json`，也可以下载备份。
6. 点击“大模型生成镜头提示词”。模型只根据小说原文、角色设定和最终人工结构填写每个镜头的正负提示词，不再改动分镜结构；提示词仍可人工修改并保存。
7. 点击“应用并替换到镜头时间线”。只有此时才创建 `S0001` 等镜头；分批制作且确实需要保留旧镜头时才勾选追加。
8. 编辑角色名称、年龄、外貌和提示词。没有参考图时点击“AI 生成立绘”，完成后会自动成为后续视频的 IPAdapter 参考图。
9. 在动作库上传动作指导视频，或点击“AI 生成动作草稿”。生成结果会写入动作库。
10. 在“模型下载”页一键下载 AnimateDiff、IPAdapter、CLIP Vision 和 OpenPose 模型；任务使用 `curl --continue-at -` 断点续传。
11. 点击“渲染全部待办”，在任务队列查看 GPU 分配、下载/生成状态和完整报错。
12. 镜头完成后，在镜头行点击“预览”：视频可直接播放，图片可直接查看，同时可检查 Worker、ComfyUI Prompt ID、文件大小并下载原始输出。
13. 全部镜头完成后点击“合成成片”，结果保存在 `data/projects/<项目ID>/final/final.mp4`。

默认工作流路由：

| 条件 | 工作流 |
|---|---|
| 无固定角色 | 02 环境/自由动画 |
| 角色 + 静态/微动作 | 03 IPAdapter + AnimateDiff |
| 角色 + 常见/复杂动作且动作库匹配 | 04 IPAdapter + OpenPose + AnimateDiff |
| 要求动作但动作库没有素材 | 自动降级到 03，并标记 `free_fallback` |

## 6. 动作库

Web 上传动作视频时，后端会自动转换为：

```text
8 FPS
16 帧
512×512
H.264
yuv420p
无音频
```

命令行也可以使用：

```bash
./scripts/normalize-motion.sh input.mp4 output.mp4
```

动作文件保存于 Docker 数据目录：

```text
data/motion_library/<action>/<motion_id>/source.mp4
```

## 7. ComfyUI API 工作流

后端使用：

```text
workflows/api/01_character_portrait_api.json
workflows/api/02_environment_api.json
workflows/api/03_character_free_motion_api.json
workflows/api/04_character_openpose_api.json
workflows/api/05_motion_draft_api.json
```

这些是 API 格式，不是前端画布格式。生产部署前，应当在目标 ComfyUI 版本中运行对应画布工作流，然后通过 `Save (API Format)` 导出并对比节点输入。自定义节点升级可能改变字段。

关键节点 ID 在：

```text
backend/app/services/workflow.py
```

修改工作流节点 ID 时必须同步修改这里。

## 8. 数据和备份

持久化内容：

```text
postgres_data Docker volume
redis_data Docker volume
./data 项目、角色参考图和动作库
/work/comfyui/main/output ComfyUI 输出
```

备份：

```bash
docker compose exec postgres pg_dump -U novel2anime novel2anime > novel2anime.sql
tar -czf novel2anime-data.tar.gz data
```

## 9. 开发和测试

```bash
docker compose run --rm backend pytest -q
docker compose run --rm backend ruff check app tests
docker compose build frontend
```

本地前端开发：

```bash
cd frontend
npm install
npm run dev
```

## 10. 当前边界

当前 MVP 已实现单角色、动作库和批量镜头调度，但以下能力仍需继续迭代：

- 多角色在同一画面的身份隔离；
- 自动动作草稿生成及 OpenPose 质量评分；
- 自动 RIFE 插帧和 AnimeSharp 放大（基础 FFmpeg 时间线拼接已经实现）；
- 配音、口型、字幕和音效；
- Alembic 正式数据库迁移；
- 用户认证和多租户；
- 生产环境 TLS、备份、配额与权限管理。

第一版应先完成一段 30～60 秒、单主角、一个场景的无声样片，再扩大范围。

## 11. 成人内容边界

系统本身不内置成人模型。若部署方扩展成人内容，必须确保所有人物明确为成年人，不得使用未成年人、年龄模糊角色或未经许可的真实人物参考图，并应对输出目录和 Web 访问增加权限控制。

