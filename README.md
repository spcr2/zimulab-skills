# 子沐研究室 · Agent Skills 工具箱

> Zimu Lab · Agent Skills Collection
>
> 在真实工作流里反复打磨出来的 5 个可复用 Agent 技能，覆盖影视库整理、电子书检索、行业规律研究、视频笔记沉淀与战略分析。

## Skills 一览

| Skill | 一句话说明 | 典型应用场景 | 实现 |
|---|---|---|---|
| [mijia-nas-media-library](mijia-nas-media-library/) | 小米 NAS 影视库批量重命名，让影视墙自动刮削识别 | 影视墙识别不到剧集、文件被手动改成拼音缩写/中文长名、需要批量规范命名与字幕 | Python · WebDAV + mTLS |
| [ebook-finder](ebook-finder/) | 2.4 万本中文电子书本地秒级检索 | 找书、下书、书单推荐、Kindle 资源查询 | Python |
| [industry-pattern-research](industry-pattern-research/) | 用 AI 批量跑行业长周期历史数据，总结可复用规律 | "券商 30 年搬迁史""律所选址规律"等行业研究 | 方法论文档 |
| [bilibili-video-notes](bilibili-video-notes/) | B站视频一键沉淀为结构化笔记 | 视频文字稿、大纲、核心观点、金句整理与长期保存 | Node.js · B站 API |
| [strategic-conflict-analysis](strategic-conflict-analysis/) | 现代管理学版战略研判与矛盾分析法 | 商业战略研判、破局思路、关键瓶颈识别、决策复盘 | 方法论文档 |

## 快速安装

把对应 skill 目录复制到 Agent 的 skills 目录（例如 `~/.workbuddy/skills/` 或项目 `.workbuddy/skills/`），Agent 即可自动发现并按其 SKILL.md 执行。

每个 skill 的依赖与用法详见各自目录内的 `SKILL.md`。

## 各 Skill 详情

### 1. mijia-nas-media-library — 小米 NAS 影视库整理

**做什么**：通过 CDP 驱动「小米智能存储」PC 客户端，经 mTLS + WebDAV 对 NAS 影视文件批量重命名为标准刮削格式（`{Show} SxxExx.ext` + `Season N` 目录 + `.zh.srt/.en.srt` 字幕），让小米影视墙自动识别并匹配剧集信息。

**应用场景**：
- 影视墙「识别不到」某文件夹内容、需要手动匹配集数
- 文件被手动改成拼音缩写（如 `SXMR S01E01.mkv`）或中文描述长名
- 需要整理多季、多字幕（中/英）的剧集
- 多剧批量规范化：平铺纯数字/EP 命名（`01.mp4` → `S01E01.mp4`）、带水印前缀的季目录（`（资源V：xxx）S01` → `Season 1`）、合集拆剧（`Q-请回答1988` 拆为三部）

**特点**：全自动（客户端启动 → 端口发现 → 认证 → 列目录 → 改名 → 验证），`--dry` 预览先行，同目录 MOVE 零删除、自动跳过未下载完成的文件（`.baiduyun.p.downloading` 标记）。内置三模式批量执行器 `nas_batch_normalize.py`（flat / season_dirs / reply），曾一次跑通 7 剧 370 集 OK=382 FAIL=0；另含 UA 解码沙箱与 451 诊断探针。

**注意**：协议知识库 `references/protocol.md` 记录了 WebDAV 路径前缀、mTLS 认证、UA 格式等逆向结论；UA 中的设备标识需自行解码（见脚本注释）。

### 2. ebook-finder — 中文电子书本地检索

**做什么**：本地检索「电子书下载宝库」索引（约 24,071 本中文书、1,000 分类，epub/mobi/azw3 三种格式网盘直链），秒级响应、无需登录。

**应用场景**：找某本书的电子版、问某主题有什么书、找某作者的作品、要 Kindle 可用的 mobi/azw3 资源、做书单推荐。

**用法**：

```bash
python scripts/search.py "书名 作者"     # 关键词搜索
python scripts/search.py --cat 文学 --limit 30   # 按分类列出
python scripts/search.py --stats        # 库统计
python scripts/search.py --refresh      # 刷新索引（7MB，内置校验重试）
```

**数据来源**：[jbiaojerry/ebook-treasure-chest](https://github.com/jbiaojerry/ebook-treasure-chest)（MIT），见 `references/data-source.md`。

### 3. industry-pattern-research — 行业规律研究

**做什么**：把「某行业企业长周期历史数据」交给 AI 批量梳理，从时间线、流向、频次、性质、底层逻辑五个维度切分，总结出可复用规律并产出结构化研究笔记。

**应用场景**：券商/律所搬迁史、企业选址史、扩张收缩史等「用 AI 跑数据总结规律」的研究；把一篇行业报道提炼成方法论；一个行业接一个行业的系列研究。

**参考案例**：用 Kimi 跑 20 家券商 30 年搬迁史，得出北京券商选址规律（CBD→金融街→多中心演变、只扩租不缩租、锚定对手方等）。

### 4. bilibili-video-notes — B站视频笔记沉淀

**做什么**：将一个 B站视频链接转化为结构化 Markdown 笔记（一句话总结 + 时间轴大纲 + 核心观点 + 文字稿 + 金句），存入固定笔记目录。

**应用场景**：整理视频学习笔记、提取视频文字稿、总结长视频内容（访谈/讲座/纪录片）、沉淀值得收藏的优质视频。

**流程**：脚本取元信息（无需登录）→ 按四个策略依次获取文字稿（CC 字幕 → 官方 AI 总结 → 搜索公开整理稿 → 本地转写）→ 套用笔记模板落盘。

### 5. strategic-conflict-analysis — 战略矛盾分析法（现代管理学版）

**做什么**：一套通用的逻辑分析与战略决策方法。核心思想：**复杂局面中必存在少数关键制约因素，识别并集中资源突破它，是改变全局的最短路径**。基于系统思考、约束理论（TOC）、根因分析、情景规划与复盘方法论（AAR/PDCA）。

**应用场景**：商业战略研判、复杂问题剖析、逆境突破方案、团队动员与组织建设、竞争策略制定、决策复盘。

**框架**：六步走——事实核查 → 问题定性 → 关键瓶颈识别 → 阶段策略制定 → 行动方案 → 决策复盘（简单问题可压缩为三步）。

## 致谢

- `ebook-finder` 的书籍索引数据来自 [ebook-treasure-chest](https://github.com/jbiaojerry/ebook-treasure-chest)（MIT License）。
- `mijia-nas-media-library` 是作者对自有小米智能存储设备的协议研究，仅用于个人设备维护，与小米公司无关。

## 许可证

MIT © 2026 子沐研究室（Zimu Lab）。详见 [LICENSE](LICENSE)。
