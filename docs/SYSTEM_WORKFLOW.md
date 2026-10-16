# 小说到动漫的系统使用与数据流

本文档描述当前系统已经实现的长篇小说、角色、动作库、ComfyUI 和成片流程。

## 1. 小说应该上传多少

上传时必须选择“长篇小说”或“短篇小说”。这个类型会记录在项目设置中，用来说明素材性质；系统不会根据类型自动识别章节、截断、改写或建立文本段。

上传新文件会替换当前项目的原文，并清除旧文件对应的人工选段记录。原始文件保存在：

```text
data/projects/<project_id>/source/
```

Web 会按原文显示全部内容。用户在只读原文框中拖动划线，填写选段标题并点击“记录当前选区”。系统保存起止字符位置、原文快照、标题、顺序、是否启用、处理次数和最近处理时间。重新打开项目后记录仍然存在，可以停用或删除。

## 2. 长篇如何交给大模型

后端不会自动决定哪些内容应交给模型。流程是：

```text
整本小说
  → 原样显示
  → 用户手工划线并保存选段记录
  → 勾选本次要处理的选段
  → 每条选段原样调用 OpenAI-compatible /chat/completions
  → Pydantic 严格校验 JSON
  → 合并角色表、场景和镜头
  → 保存为可编辑 JSON 草案
  → 人工修改并校验保存
  → 大模型根据原文与最终草案生成每镜头提示词
  → 人工复核提示词
  → 应用到镜头时间线
```

配置：

```dotenv
LLM_BASE_URL=http://host.docker.internal:11434/v1
LLM_MODEL=
LLM_API_KEY=
LLM_TIMEOUT=120
LLM_MAX_SELECTION_CHARS=12000
LLM_MAX_RETRIES=2
```

`LLM_BASE_URL` 和密钥用于连接服务，`LLM_MODEL` 只是可选的默认模型。每个项目的“大模型连接”可以自行填写地址、模型名和令牌：DeepSeek、智谱、OpenAI、Kimi、Grok、兼容网关及本地 Ollama/vLLM 选择 `OpenAI-compatible`；Claude 原生地址选择 `Anthropic Messages`。地址、模型名和协议保存到项目；令牌只保留在当前浏览器会话并随请求发送，不写入项目数据库。点击“刷新该地址的模型列表”会调用该地址的 `/models` 接口；不支持该接口的服务也可以直接手动填写模型名。

系统提示词位于 `backend/app/services/llm.py`。它要求模型：只使用原文剧情、解析代词、保持角色姓名稳定、保存对应原文短摘录、使用可生成的视觉描述，并且只返回满足 JSON Schema 的对象。结构固定为：

```json
{
  "characters": [
    {
      "name": "角色名",
      "age": 25,
      "description": "外貌与服装",
      "positive_prompt": "English visual tags"
    }
  ],
  "scenes": [
    {
      "title": "场景名",
      "location": "地点",
      "time_of_day": "时间",
      "weather": "天气",
      "summary": "摘要",
      "source_text": "对应原文",
      "shots": [
        {
          "shot_type": "medium shot",
          "camera": "static",
          "action": "单一主要动作",
          "emotion": "情绪",
          "dialogue": null,
          "characters": ["角色名"],
          "location": "地点",
          "source_text": "对应原文",
          "positive_prompt": "",
          "negative_prompt": ""
        }
      ]
    }
  ]
}
```

模型输出包含额外字段、缺字段、根节点不是对象或不是合法 JSON 时都会失败并带校验错误重试。多条人工选段按记录顺序处理，并共享已知角色表，最终按角色名合并。系统不会在背后继续切分选段；单条超过 `LLM_MAX_SELECTION_CHARS` 时会在保存阶段明确拒绝，由用户缩小选区。

草案保存在 `data/projects/<project_id>/plans/plan_draft.json`，可在 Web 中直接编辑、校验、保存或下载。点击“大模型生成镜头提示词”时，后端按场景把角色设定、原文摘录和人工最终修改后的镜头结构再次交给大模型，只允许模型填写每个镜头的 `positive_prompt` 和 `negative_prompt`，不会重新拆分或改写场景。确认后点击“应用并替换到镜头时间线”；只有这一步才会创建 `S0001` 等镜头。需要保留已有镜头时才选择追加。

勾选“使用大模型”但当前项目和默认配置都没有选择模型时，接口会明确报错，不再静默退化成按标点拆句。只有主动关闭“使用大模型”时才会使用句子级启发式规划；这个模式只用于验证流水线，不适合作为最终脚本质量方案。

## 3. 分批制作与最后合并

人工选段解决“只做一部分”的问题；`max_shots` 控制一次生成多少镜头。应用草案时默认替换项目的旧场景/镜头。需要分批制作时，勾选“追加到现有时间线”：系统从现有最大场景和镜头序号继续添加，最后按同一时间线合成。因此生产上建议：

- 一个项目对应一个集、一个章节或一个连续片段；
- 长篇创建多个项目，例如 `第01集`、`第02集`；
- 同一集分批规划时，避免重复启用已经追加过的选段记录；
- 每个项目内部镜头完成后由 FFmpeg 按统一序号合成为一个 MP4；
- 多集应作为多个成片保存，不要把整部长篇强行做成单个渲染任务。

系统内单个项目的合成顺序严格使用镜头 `sequence`，先把各镜头标准化为目标分辨率、帧率和编码，再按时间线拼接。

## 4. 没有立绘时

规划完成后会创建角色。角色页支持编辑：

- 姓名和成人年龄；
- 中文外貌、发型、服装、性格说明；
- 英文正向提示词；
- 上传参考图；
- AI 生成立绘。

AI 立绘使用 `workflows/api/01_character_portrait_api.json`。它生成单人、全身、正面、简单背景的动漫角色设定图。任务完成后自动把文件写入：

```text
data/projects/<project_id>/characters/<character_id>/generated.<ext>
```

并更新角色的 `reference_image`。后续 03/04 视频工作流会上传该图到 ComfyUI，并通过 IPAdapter 保持角色外观。角色的名称、年龄、描述和提示词也会进入每个关联镜头的正向提示词。

角色卡会直接预览已绑定参考图，支持放大预览、上传替换和重新生成。每次生成结束后最新图片会自动重新绑定到对应角色，不会成为脱离角色的普通输出文件。

任何立绘、动作、模型下载或镜头渲染任务提交后都会弹出确认窗口。右下角“任务”悬浮球在所有页面可用，显示进行中数量；打开后可查看队列、运行状态、Worker 与错误信息。

## 5. 没有动作库时

动作库有两种来源：

1. 上传真实或自制动作指导视频。系统用 FFmpeg 转换成 8 FPS、16 帧、512×512、H.264。
2. 输入 `motion_id`、动作分类和提示词，使用 `workflows/api/05_motion_draft_api.json` 生成 AnimateDiff 动作草稿。

AI 动作任务完成后自动保存到：

```text
data/motion_library/<action>/<motion_id>/source.mp4
```

并建立 `MotionAsset` 数据库记录。动作草稿适合低成本建立候选库，但它不等于可靠的骨骼指导。复杂打斗、准确手势或指定舞蹈仍建议上传动作视频，再由 04 工作流提取 OpenPose。

镜头路由规则：无角色使用 02；轻微动作使用 03；常见或复杂动作且匹配到动作资产时使用 04；需要动作但库中没有匹配时降级为 03 自由动画。

## 6. 模型下载器

Web“模型下载”页显示后端白名单中的开放模型及其安装状态。当前包括：

- AnimateDiff SD1.5 v2；
- IP-Adapter Plus SD1.5；
- CLIP Vision ViT-H；
- ControlNet SD1.5 OpenPose 及配置。

点击下载后，Celery Worker 使用：

```bash
curl --fail --location --retry 3 --continue-at - --output <file>.part <url>
```

下载成功才把 `.part` 改为最终文件名。URL 和目标路径由 `backend/app/services/model_catalog.py` 固定，前端不能提交任意下载地址。基础动漫 Checkpoint 因来源和许可不同，仍需手工放到 `models/checkpoints/`。

## 7. 启动升级后的系统

拉取代码后需要重建镜像，因为后端和前端都发生了变化：

```bash
cd /work/novel2anime
git pull origin main
docker compose up -d --build
docker compose logs -f --tail=200 backend worker
```

SQLAlchemy 启动时会创建新增的 `novel_selections` 和 `asset_jobs` 表。此次升级没有修改原有表字段，不需要清空 PostgreSQL 数据卷。

访问：

```text
Web: http://服务器IP:3300
API: http://服务器IP:3301/docs
```

先进入“模型下载”和“系统诊断”，再开始立绘或动作任务。新增工作流仍必须在目标服务器的 ComfyUI 版本上实际运行验证；自定义节点升级会导致节点字段变化。
