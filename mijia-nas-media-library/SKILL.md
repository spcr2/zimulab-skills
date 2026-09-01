---
name: mijia-nas-media-library
description: 整理小米 NAS（小米智能存储 SmartStorage 客户端，影视库/文件管理）上的影视文件命名，使其能被影视墙刮削器自动识别匹配剧集。当用户提到小米NAS/NAS影视库识别不到/刮削不了/文件名乱/重命名影视文件/整理剧集/按标准命名时使用。通过 CDP 驱动客户端 + mTLS + WebDAV（PROPFIND/MOVE）完成列目录、改名、验证；内置 UA 解码沙箱与 451 诊断探针，可处理任意剧集（中英文名、拼音缩写前缀、多季、多字幕）。
agent_created: true
---

# 小米 NAS 影视库整理

## 适用场景

- 用户说小米影视墙/影视库**识别不到**某文件夹内容、需要手动匹配集数
- 文件被手动改成拼音缩写（如 `SXMR S01E01.mkv` = 蛇蝎美人）或中文描述名
- 需要批量把剧集重命名为标准刮削格式（`{Show} SxxExx.ext` + `Season N` 目录）

## 工作流

1. **确认目标**：问清剧集原名（英文官方名 + 年份）、存放目录。参考 `references/protocol.md` §7 的标准命名。
2. **先探测路径**（如需定位）：用 `mediacenter/media_recently_watched` 或 `filemgr/list_directory`（LuCI，`/home/u1943294/pool0/data/...` 前缀）找到影视库文件完整路径。
3. **预览改名计划**：运行 `nas_rename.py --dry`，确认计划里每行改名都正确、跳过项合理（未下载完的 `.baiduyun.p.downloading` 必须跳过）。
4. **执行改名**：去掉 `--dry` 正式运行。脚本顺序：文件改名 → 外层目录改名 → 季目录改名，失败即中止。
5. **验证 + 收尾**：脚本末尾会 PROPFIND 验证最终结构；告诉用户在小爱同学/小米影视墙重新扫描媒体库。

## 脚本与用法

所有脚本在 `scripts/` 下，自包含（含客户端启动、端口发现、认证），**直接运行即可**，无需手动开客户端。

### 主执行器 `nas_rename.py`（带前缀/结构化命名，最常用）

```bash
python scripts/nas_rename.py --dry \
  --old-dir "/pool0/data/百度网盘/蛇蝎美人 1-2季 1080p（3种字幕：中英文、纯英文、无字幕）" \
  --new-dir "/pool0/data/百度网盘/Femme Fatales (2011)" \
  --show "Femme Fatales" --prefix "SXMR" \
  --seasons "S01:Season 1,S02:Season 2"
```

- 必填：`--old-dir`（WebDAV 路径，`/pool0/data/...` 前缀）、`--new-dir`、`--show`（刮削剧名）、`--prefix`（旧文件名前缀）
- `--seasons` 默认 `S01:Season 1,S02:Season 2`，可扩展
- `--dry` 只预览不执行；**正式执行前必须 dry 一次**
- 字幕规则内置：中文 `{ep}.srt`→`.zh.srt`、英文 `{ep}-EN.srt`→`.en.srt`
- 凭证自动从 LuCI `get_pool_info` 动态获取（不落盘）；如 API 不可用可 `--no-auto-creds` + 环境变量 `NAS_WEBDAV_USER/NAS_WEBDAV_PWD`

### 平铺执行器 `nas_rename_flat.py`（纯数字命名/无前缀）

网盘下载的剧集常是 `01.mp4 / 01.srt ... 45.mp4 / 45.srt` 平铺在单目录（无统一前缀、无季目录），用这个：

```bash
python scripts/nas_rename_flat.py --dry \
  --old-dir "/pool0/data/百度网盘/NAS下载/全45集，粤语外挂" \
  --new-dir "/pool0/data/百度网盘/NAS下载/The Demi-Gods and Semi-Devils 天龙八部 (1997)" \
  --show "The Demi-Gods and Semi-Devils"
```

- 匹配规则：顶层 `NN.ext`（NN=1-2 位集数，mp4/srt/mkv/avi/ts），自动映射 `NN` → `S01E NN`
- 流程：旧目录内建 `Season 1` → 文件改名移入 → 外层目录改名（`--new-dir`）
- 未知目录（如弹幕/）与未匹配文件自动保留，随外层目录一起改名，零删除
- 默认 `--dry` 预览，`--run` 才正式执行（2026-08-31 天龙八部 45 集实战验证 90/90 成功）
- 目录名建议 `{Show} {中文名} ({Year})` 便于识别；文件名用英文官方名保证刮削命中

### 批量规范化执行器 `nas_batch_normalize.py`（全库多剧一次处理）

影视库里有大量下载资源命名混乱（水印前缀、广告尾巴、纯数字、EP 混写、多季目录带资源商前缀），逐部跑单剧脚本太慢，用这个**多任务批量执行器**：

```bash
python scripts/nas_batch_normalize.py          # dry-run 预览全部任务
python scripts/nas_batch_normalize.py --run    # 正式执行
```

- 核心：脚本顶部 `JOBS` 数组声明每个剧集任务，**三种模式**：
  - `flat`（平铺单季）：建 `Season 1` → 文件改名移入 → 外层目录改名。解析器可选 `ep_rm_ads`（剥 `【广告】` 尾巴）、`ep_plain`（纯数字）、`ep_zhen_guan`（`E01.2160p...` 长尾巴）、`ep_sanguo`（`EP01.4K...` 长尾巴）
  - `season_dirs`（旧季目录带水印前缀）：旧季目录改名 `Season N` → 文件原地改名 → 外层目录改名（`ep_ekaterina` 支持 `E01/04/EP10/- 01` 混合集数写法）
  - `reply`（合集拆多剧）：各子目录建 `Season 1` 改名移入 → 子目录提升到 NAS下载 同级；未处理子目录（如国语版待确认）保留原目录
- **先探测再配 JOBS**：用 `dav_list` 递归看清每部剧真实结构（目录名可能与预期不同，如 `036 进击的巨人`、`Q-请回答1988`）
- **下载中的目录一律跳过**：存在 `.baiduyun.p.downloading` 的目录（或整目录为空/在下载）不加入 JOBS，改名会中断下载任务
- 内置约定：目标目录名 `{Show} {中文名} ({Year})`，文件名 `{Show} SxxExx.ext`；同目录 MOVE 不落盘、失败即中止、先 dry
- 2026-08-31 全库实战验证：7 个剧集单元 370 文件（叶卡捷琳娜38 + 人民的名义55 + 大宅门40 + 大明王朝46 + 贞观之治50 + 三国演义84 + 请回答57）一次执行 OK=382 FAIL=0，集数全部连续

### 批量规范化执行器·第二轮 `nas_batch_round2_20260901.py`（下载完成后整理）

第一轮跳过（下载中）的资源下完后，用同一套框架做第二轮。存档脚本 `nas_batch_round2_20260901.py`（用法同 round1：dry-run 预览 / `--run` 执行）。

- 本轮新增解析器（flat 模式）：`ep_greed`（`EP01.mkv` / `EP40.END.mkv` 带 END 标记）、`ep_slamdunk`（`【001】标题.mkv`）、`ep_touch`（`...EP001.mkv`，需前置检查 `.downloading`）、`ep_kenshin_tv`（`浪客剑心 Rurouni Kenshin NN.rmvb`，仅纯数字=TV正片，追忆篇/星霜篇等特殊文件自动 SKIP 保留）、`ep_koseidon`（`恐龙特急克塞号NN：标题...mkv`）、`ep_handsome`（`绝代双骄.1999.EP01....mkv`）、`ep_duke`（`鹿鼎记.1998.DVDrip.2audio.EP01.mkv`）、`ep_dh`（`（资源V：xx）S01E01.mp4`，绝望的主妇季内文件）
- 2026-09-01 实战验证：8 个剧集单元 533 文件（大时代40 + 灌篮高手101 + 浪客剑心95 + 恐龙特急克塞号35 + 绝代双骄40 + 鹿鼎记44 + 绝望的主妇178 + 蛇蝎美人78含字幕）一次执行 OK=548 FAIL=0
- 关键判断：**即使目录看起来「下完了」，也要先探测有没有漏网 `.downloading` 标记**（棒球英豪 EP074 就是平铺文件带 `.downloading` 后缀，差点误处理）；杂质文件（多片源混杂）无法匹配解析器 → 自动 SKIP 保留原地，零删除

### 诊断探针 `nas_451_probe.py`

PROPFIND/MOVE 遇到 451（nginx 拦截）时跑它，批量测试 Host/路径前缀/方法/UA/auth 各因素，定位拦截点。

### UA 解码沙箱 `nas_ua_decode.js`

客户端 webdav 需要特定 UA。版本升级后重跑：
```bash
node scripts/nas_ua_decode.js [提取目录] [.device.uid路径] [版本号]
```
解码出的 UA 写入 `nas_common.py` 的 `UA` 常量（或环境变量 `NAS_WEBDAV_UA`）。

### 公共库 `nas_common.py`

`SmartStorageSession` 类封装全链路：`start()` → `wait_device()` → `wait_ports()` → `fetch_webdav_creds()` → `propfind()/move()/luci()`。需要更复杂操作（下载、上传、读影视墙）时 `from nas_common import SmartStorageSession` 扩展。

## 关键陷阱（详见 references/protocol.md）

- **WebDAV 路径用 `/pool0/data/...`，不带 `/home/u1943294` 别名前缀**（带前缀 → 451）；LuCI filemgr 则反过来必须带前缀
- 端口每次启动动态分配，从日志 `app-*.log` 轮询 `webdavport=`/`urlport=`；localStorage 的端口是旧缓存
- 需 mTLS 证书（`minasCert/`）+ Basic auth + 客户端 UA 三件套
- PROPFIND 的 XML 是 `<D:href>`（大写 D）
- `.baiduyun.p.downloading` = 百度网盘未下载完，**跳过不动**
- 永远同目录 MOVE、不删除文件、失败即中止、先 dry

## 完成后

- 请用户在小爱同学 / 小米影视墙重新扫描媒体库触发刮削
- 若有多季/多剧集，用同一脚本改参数即可批量处理
