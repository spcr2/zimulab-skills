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
