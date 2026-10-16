# Roadmap

## M0：基础闭环

- [x] Compose、API、Web、PostgreSQL、Redis、Celery
- [x] ComfyUI 双 Worker 调度
- [x] 模型、节点、日志诊断
- [x] 长篇/短篇导入、原文展示与人工划线选段记录
- [x] 固定 JSON Schema、校验和自动重试
- [x] 可编辑角色设定、参考图和 AI 立绘生成
- [x] 动作库上传与 AI 动作草稿生成
- [x] Web 模型下载器（白名单 + curl 断点续传）
- [x] 工作流 02/03/04 API 调用
- [ ] 在目标服务器逐一验证三份 API workflow
- [ ] 生成第一个三镜头样片

## M1：自动动作补库

- [x] 05 粗略动作工作流
- [ ] 每个动作生成多个 seed
- [ ] OpenPose 非黑像素与人体覆盖率检查
- [ ] 动作候选人工选择页
- [x] 自动写入动作库

## M2：后期

- [ ] RIFE 插帧
- [ ] AnimeSharp 放大
- [x] FFmpeg 时间线拼接
- [ ] 配音、字幕、背景音乐和音效

## M3：制作稳定性

- [ ] Character LoRA
- [ ] 场景参考库
- [ ] 镜头连续性状态
- [ ] 多角色遮罩与分区 IPAdapter
- [ ] 自动质量评分
- [ ] 审核与版本回滚

