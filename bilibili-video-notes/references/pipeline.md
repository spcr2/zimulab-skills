# 文字稿获取策略（按优先级依次尝试）

获取视频元信息用 `scripts/get_video_info.mjs`（无需登录）。拿到文字稿按以下顺序尝试，成功即止：

## 策略 1：CC 字幕（最准确，需浏览器登录态）

前提：用户浏览器已开启远程调试（chrome://inspect/#remote-debugging 勾选 Allow remote debugging），且 web-access skill 的 CDP Proxy 已运行（`http://localhost:3456`）。若未运行，先执行 `node ~/.workbuddy/skills/web-access/scripts/check-deps.mjs`。

步骤（全部通过 Bash curl 调 CDP Proxy 完成）：

1. 新标签页打开视频页：
   ```bash
   curl -s -X POST --data-raw 'https://www.bilibili.com/video/{BV号}/' http://localhost:3456/new
   ```
   返回 JSON 里的 `target` 是标签页 ID。

2. 检查B站登录态（必须在 bilibili.com 页面上下文内执行 fetch 才带 cookie）：
   ```bash
   curl -s -X POST "http://localhost:3456/eval?target={targetId}" -d 'fetch("https://api.bilibili.com/x/web-interface/nav",{credentials:"include"}).then(r=>r.json()).then(d=>JSON.stringify({isLogin:d.data&&d.data.isLogin}))'
   ```
   未登录则提示用户扫码登录后重试。

3. 请求字幕列表：
   ```bash
   curl -s -X POST "http://localhost:3456/eval?target={targetId}" -d 'fetch("https://api.bilibili.com/x/player/wbi/v2?aid={aid}&cid={cid}&bvid={BV号}",{credentials:"include"}).then(r=>r.json()).then(d=>JSON.stringify(d.data&&d.data.subtitle||{}))'
   ```
   `subtitles` 数组非空时，取 `subtitle_url`（通常是 `//aisubtitle.hdslb.com/...`，需补 `https:` 前缀），用 curl 直接下载（json 格式，`body` 数组里每项有 `from/to/content`）。

4. 多分P视频：对每个 cid 重复步骤 3。

5. 完成后关闭标签页：`curl -s -X POST "http://localhost:3456/close?target={targetId}"`。

## 策略 2：B站官方 AI 视频总结

```bash
curl -s -X POST "http://localhost:3456/eval?target={targetId}" -d 'fetch("https://api.bilibili.com/x/web-interface/view/conclusion/get?bvid={BV号}&cid={cid}&up_mid={owner_mid}",{credentials:"include"}).then(r=>r.json()).then(d=>JSON.stringify(d).slice(0,3000))'
```

`model_result.summary` 是分段摘要，`outline` 是章节大纲。很多视频没生成，返回空就换策略 3。

## 策略 3：搜索公开整理稿

很多热门访谈/知识类视频有公众号、播客（小宇宙）、知乎、第三方网站的整理稿。用 WebSearch 搜：
- `"{视频标题}" {UP主} 文字稿`
- `"{视频标题}" {UP主} 时间轴 OR 总结 OR 笔记`

找到后用 WebFetch 抓全文，交叉比对标题/简介确认是同一期内容。

## 策略 4：本地下载转写（最后手段）

需 BBDown（`dotnet tool install --global BBDown`）+ 本地 ASR（faster-whisper 等）。只取音频减小体积：

```bash
BBDown --audio-only "https://www.bilibili.com/video/{BV号}/"
```

再交给本地转写工具。没有工具链时跳过此策略。

## 重构兜底

以上全部失败时，基于简介、分P标题、热门评论、相关报道重构大纲和总结，并在笔记"来源与可信度"里明确标注"非逐字稿，结构保留"。
