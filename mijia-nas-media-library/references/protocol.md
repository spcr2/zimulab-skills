# 小米智能存储（SmartStorage）协议知识库

本文件记录通过逆向客户端（Electron asar 反混淆 + CDP + 日志）验证过的所有关键协议细节。
**这些结论来之不易，改动前务必先跑 `nas_451_probe.py` 验证。**

## 1. 整体架构

```
SmartStorage.exe (Electron) ──CDP 9223──> 本地代理(动态端口) ──mTLS+LuCI/WebDAV──> NAS 192.168.31.136
```

- 客户端是 Electron 应用，渲染进程开 CDP（`--remote-debugging-port=9223`）
- 本地代理端口**每次启动动态分配**（urlport / webdavport），localStorage 里的 `cgiPort`/`webdavPort` 是旧缓存**不可用**
- 直连代理必须带 mTLS 客户端证书（`minasCert/` 目录），否则端口拒绝或 400/451
- 网络层面还有固件拦截：直连 NAS:5000 或代理端口都需要特定 UA + Basic auth

## 2. 路径体系（最容易踩坑）

| 接口 | 路径前缀 | 示例 | 结果 |
|---|---|---|---|
| **WebDAV** | `/pool0/data/...` | `PROPFIND /pool0/data/百度网盘/` | 207 ✅ |
| **WebDAV** | `/home/u1943294/pool0/data/...`（alias 前缀） | 同路径带前缀 | **451 ❌**（nginx 按 location 拦） |
| **LuCI filemgr** | `/home/u1943294/pool0/data/...`（alias 前缀） | `list_directory parent=/home/u1943294/pool0/data` | code=0 ✅ |
| **LuCI filemgr** | `/pool0/data/...` | 同上不带前缀 | code=1114 ❌（父目录不存在） |

> 一句话：**WebDAV 去前缀，LuCI 加前缀**。前缀来自 `get_pool_info` 返回的 `webDAV.alias_root`（如 `/home/u1943294`）。

alias_root 结构：`{alias_root}/{internal_pool[i].data_dir}`，其中 `data_dir=/pool0/data`。

## 3. 认证三件套

WebDAV 请求必须同时满足，缺一即 451/403/401：

1. **mTLS 客户端证书**：`~/AppData/Local/minasCert/{uid}_{did}_cert.pem` + `{uid}_{did}_private_key.pem`（可选 CA）
2. **Basic Auth**：`u{uid}:{password}`，password 从 LuCI `filemgr/get_pool_info` 返回的 `webDAV.password` 动态获取（**每次可刷新**，勿硬编码）
3. **User-Agent**：客户端真实 UA（见第 5 节），格式 `MiNasClient/{ver} (pc app; {model}; {os}; {uuid})`

## 4. LuCI API

- 端点：`/cgi-bin/luci/{path}?accessToken={cgiToken}`（URL query 传 token）
- 方法：POST，body 为 JSON
- cgiToken 获取：CDP `Runtime.evaluate` 读 `localStorage.deviceInfo.cgiToken`（设备连接后出现）
- 常用接口：
  - `filemgr/get_pool_info` → 存储池 + **webDAV 凭证**（username/password/alias_root/port）
  - `filemgr/list_directory` → body `{"page":{"size":100,"token":""},"order":{"basis":"name","desc":false},"path":{"parent":"...","recursion":false}}`
  - `storage/get_storage_info` → 存储信息
  - `mediacenter/media_recently_watched` → **影视墙已识别媒体路径**（定位影视库文件的关键通道，返回 `/home/u1943294/pool0/data/...` 完整路径）
- 返回格式：`{"code":0, "data":{...}}`；code=1114 表示父目录不存在（多半是路径前缀问题）

## 5. User-Agent 生成

`MiNasClient/{version} (pc app; {device_model}; {os_info}; {uuid})`

- **version**：app.asar 里 package.json 的 version（当前 1.0.8）
- **device_model**：如 `TBHK-L096`（设备型号，客户端写死的）
- **os_info**：`os.type() + getOSInfo()` → `Windows 10/11 10.0.26200 (x64)`
- **uuid**：`AppData/Roaming/SmartStorage/.device.uid` 里的 16 位大写字母数字（稳定值）

解码方法：`scripts/nas_ua_decode.js`（Node 沙箱加载真实混淆模块自解码）。
当前已知有效 UA：
```
MiNasClient/1.0.8 (pc app; TBHK-L096; Windows 10/11 10.0.26200 (x64); <DEVICE_UID>)
```
版本升级后需重跑解码。

## 6. WebDAV 细节

- PROPFIND 响应 XML 命名空间前缀是 **`<D:href>`（大写 D）**，正则要写 `[dD]:href`
- MOVE 的 `Destination` 头必须是完整 URL：`https://127.0.0.1:{port}{quote(path, safe='/')}`
- MOVE 成功后返回 201（Created）或 204/200
- Depth 头：列目录用 `1`，验证单资源用 `0`

## 7. 标准影视刮削命名（目标）

```
{Folder}/Femme Fatales (2011)/
├── Season 1/
│   ├── Femme Fatales S01E01.mkv
│   ├── Femme Fatales S01E01.zh.srt      (中文字幕)
│   └── Femme Fatales S01E01.en.srt      (英文字幕)
└── Season 2/
```

- 剧集：`{Show} S{NN}E{NN}.{ext}`（show 含年份时如 `Femme Fatales (2011)`）
- 季目录：`Season N`（N 从 1 起）
- 外层目录：`{Show} ({Year})`
- 字幕后缀：`.zh.srt` / `.en.srt`（不要用 `-EN.srt`）
- 百度网盘未下载完的文件是 `.baiduyun.p.downloading` 后缀，**必须跳过**，改名/删除都会破坏下载任务

## 8. 安全原则（重命名类操作）

1. **永远同目录内 MOVE**，不要跨目录 move + delete（MOVE 失败会连带删残留）
2. 顺序：文件改名 → 外层目录改名 → 季目录改名；文件失败就中止，避免路径错乱
3. 不删除任何文件（包括未匹配的、下载中的）
4. 正式执行前必跑 `--dry` 预览
5. 凭证动态获取，不写死在脚本/文档里

## 9. 常见问题速查

| 症状 | 原因 | 解法 |
|---|---|---|
| 连接 127.0.0.1:{port} 拒绝 | 客户端没起来 / 端口已失效（会话结束被清） | 重新跑脚本（脚本内含启动逻辑） |
| PROPFIND 451 | 路径带了 `/home/u1943294` 前缀 / 缺 UA | 改 `/pool0/data/...` 前缀；补 UA |
| 401 | Basic auth 错（密码过期） | 重新 `fetch_webdav_creds()` |
| code=1114 | LuCI parent 没带 alias 前缀 | 补 `/home/u1943294` 前缀 |
| `<D:href>` 匹配 0 个 | 正则大小写 | 用 `[dD]:href` |
| 端口每次变 | 动态分配机制 | 日志轮询 `webdavport=`/`urlport=` |
| 会话结束进程被清 | WorkBuddy 工具会话清理子进程树 | 单脚本内完成全流程，勿跨脚本依赖端口 |
