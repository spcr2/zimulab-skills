---
name: bilibili-video-notes
description: B站视频内容沉淀流水线。当用户提供哔哩哔哩/B站视频链接（b23.tv 短链、bilibili.com/video/BV 链接或 BV 号），希望获取文字稿、大纲、总结，或将视频内容整理成笔记长期保存时使用此技能。触发场景：整理B站视频笔记、提取视频文字稿、总结B站视频内容、沉淀好视频。
agent_created: true
---

# B站视频内容沉淀

将一个B站视频链接转化为一份结构化 Markdown 笔记（一句话总结 + 时间轴大纲 + 核心观点 + 文字稿 + 金句），存入固定笔记目录。

## 流程

### 第 1 步：获取视频元信息

```bash
node "~/.workbuddy/skills/bilibili-video-notes/scripts/get_video_info.mjs" "<链接>"
```

脚本支持 b23.tv 短链、完整 URL、纯 BV 号，输出 title/desc/owner/duration/pubdate/aid/cid/pages 等 JSON，无需登录。

### 第 2 步：获取文字稿

按 `references/pipeline.md` 中的四个策略依次尝试（CC 字幕 → 官方 AI 总结 → 搜索公开整理稿 → 本地下载转写），成功即止。全部失败时基于公开信息重构，并在笔记中如实标注可信度。

关键经验：
- 字幕和 AI 总结接口都需要B站登录态，须通过 web-access skill 的 CDP Proxy（localhost:3456）在已登录的浏览器标签页内执行 fetch，静态 curl 拿不到。
- 很多视频没有 CC 字幕，访谈类视频可优先搜索公众号/小宇宙的整理稿。
- 时长超过 30 分钟且无任何字幕时，直接进入策略 3。

### 第 3 步：写入笔记

用 `assets/note-template.md` 的结构，生成笔记文件：

- 笔记目录默认 `~/WorkBuddy/bilibili-notes/`（目录不存在则创建）。
- 若 skill 目录下存在 `config.env` 且含 `NOTES_DIR=...`，则用该目录覆盖默认值。
- 文件名：`{视频标题}.md`，标题中的非法文件名字符（`\/:*?"<>|`）替换为全角或删除。
- 文字稿必须注明来源和可信度（逐字/接近原意/重构），不得把重构稿伪装成逐字稿。

### 第 4 步：交付

用 present_files 打开生成的笔记，并简短告知用户：文字稿来源、可信度、笔记存放路径。

## 资源

- `scripts/get_video_info.mjs` — 解析链接并抓取视频元信息（无需登录）
- `references/pipeline.md` — 文字稿获取四策略的详细操作步骤与 API 调用方式
- `assets/note-template.md` — 笔记模板
