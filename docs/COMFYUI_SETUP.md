# ComfyUI 节点与模型复现清单

本文档对应仓库自带的 02/03/04 三套 API 工作流。执行命令前，先确认 `/work/comfyui/main` 是实际 ComfyUI 根目录，Conda 环境名是 `comfyui`。

如果 Conda 只在交互式 shell 中可用，脚本会自动检查常见的 Miniconda、Anaconda 和 `/opt/conda` 路径。非标准安装位置可显式指定：

```bash
export COMFYUI_CONDA_BIN="$(which conda)"
```

## 1. 自定义节点

一键安装缺失节点：

```bash
cd /work/novel2anime
chmod +x scripts/*.sh
./scripts/install-custom-nodes.sh
```

脚本安装以下上游仓库：

- [AnimateDiff Evolved](https://github.com/Kosinkadink/ComfyUI-AnimateDiff-Evolved)
- [Video Helper Suite](https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite)
- [ComfyUI IPAdapter Plus](https://github.com/cubiq/ComfyUI_IPAdapter_plus)
- [ControlNet Auxiliary Preprocessors](https://github.com/Fannovel16/comfyui_controlnet_aux)

已存在的仓库不会被自动更新，因为自定义节点升级可能改变 API 输入字段。先备份并导出能运行的 API 工作流，再决定是否更新。

## 2. 开放模型

```bash
./scripts/download-open-models.sh
```

脚本会断点续传并跳过已有文件：

| 模型 | 来源 | 目标位置 |
|---|---|---|
| `mm_sd_v15_v2.ckpt` | [guoyww/animatediff](https://huggingface.co/guoyww/animatediff/blob/main/mm_sd_v15_v2.ckpt) | `models/animatediff_models/` |
| `ip-adapter-plus_sd15.safetensors` | [h94/IP-Adapter](https://huggingface.co/h94/IP-Adapter/blob/main/models/ip-adapter-plus_sd15.safetensors) | `models/ipadapter/` |
| CLIP Vision H | [h94/IP-Adapter](https://huggingface.co/h94/IP-Adapter/blob/main/models/image_encoder/model.safetensors) | `models/clip_vision/CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors` |
| OpenPose ControlNet | [lllyasviel/ControlNet-v1-1](https://huggingface.co/lllyasviel/ControlNet-v1-1/tree/main) | `models/controlnet/` |

`mm_sd_v15_v2.ckpt` 的 `.ckpt` 后缀可以正常使用；AnimateDiff Evolved 官方明确支持 v1/v2/v3 motion modules，并把 `models/animatediff_models` 列为标准目录。

## 3. 基础 Checkpoint

工作流默认文件名：

```text
/work/comfyui/main/models/checkpoints/meinamix_meinaV11.safetensors
```

MeinaMix 的下载和再分发许可应在模型发布页自行确认，因此自动脚本不下载它。若你的文件名不同，有两种做法：

1. 将文件改名为 `meinamix_meinaV11.safetensors`；
2. 修改三个 `workflows/api/*.json` 中 `CheckpointLoaderSimple.inputs.ckpt_name`。

不要把模型文件提交进 Git。

## 4. 启动与检查

```bash
./scripts/start-comfyui.sh dual
curl -fsS http://127.0.0.1:8188/system_stats
curl -fsS http://127.0.0.1:8189/system_stats
./scripts/doctor.sh
```

Web 的“系统诊断”还会读取 `/object_info`，检查实际注册的节点类型。只看到目录存在不代表节点加载成功；若某个依赖导入失败，应查看：

```text
/work/comfyui/main/logs/gpu0.log
/work/comfyui/main/logs/gpu1.log
```

## 5. 工作流兼容性

仓库内 JSON 是 ComfyUI `/prompt` API 格式，不是前端画布格式。自定义节点存在版本漂移，因此目标服务器上的最终标准是：

1. 用 ComfyUI 前端打开并运行你的画布工作流；
2. 确认视频确实保存成功；
3. 使用 `Save (API Format)` 导出；
4. 对照 `workflows/api/` 和 `backend/app/services/workflow.py` 的节点 ID；
5. 调用 `/api/system/diagnostics`，确保 `missing_nodes` 为空。

后端不会静默忽略缺失节点。ComfyUI 返回校验错误时，渲染任务会进入 `failed`，完整错误会保存在任务记录并显示在渲染队列。
