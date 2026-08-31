---
name: ebook-finder
description: 中文电子书本地检索（电子书下载宝库，24071本书/1000分类，epub/mobi/azw3）。当用户想找书、下载电子书、查某本书有没有资源、问"有没有关于XX的书"、找某作者的作品时使用此技能。触发场景：找书、搜书、下电子书、要书单推荐、Kindle找书。
agent_created: true
---

# 电子书下载宝库检索（ebook-finder）

本地检索 GitHub 开源项目「ebook-treasure-chest」的书籍索引（约 24,071 本中文书、1,000 个分类，每本有 epub/mobi/azw3 三种格式的城通网盘下载链接），秒级响应、无需登录。

## 何时使用

用户表达以下意图之一时：
- 找/搜/下载某本书的电子版（"帮我找一下《底层逻辑》"）
- 询问某主题有什么书（"有没有讲谈判的书"）
- 找某作者的作品
- 要 Kindle 可用的 mobi/azw3 资源

## 搜索方式

```bash
# 关键词搜索（多关键词空格分隔，AND 关系，匹配书名/作者/分类）
python "~/.workbuddy/skills/ebook-finder/scripts/search.py" "书名 作者"

# 按分类列出
python "~/.workbuddy/skills/ebook-finder/scripts/search.py" --cat "文学" --limit 30

# 库统计
python "~/.workbuddy/skills/ebook-finder/scripts/search.py" --stats

# 刷新索引（数据源更新时，需网络，偶尔下载不完整会自动校验失败重试）
python "~/.workbuddy/skills/ebook-finder/scripts/search.py" --refresh
```

## 输出处理

- 脚本输出 JSON：total（命中总数）、returned、results（title/author/category/link/formats）
- 向用户汇报时：列出书名、作者、分类、可用格式，并附下载链接（ctfile 城通网盘，提取码通常为链接中的 p= 参数或页面上直接显示）
- 同一本书可能因分类重复出现多条，去重后再展示
- 没找到时如实告知，可建议：换关键词、按分类浏览（--cat）、或用 web 搜索其他来源

## 注意事项

- 链接来自第三方（城通网盘），下载速度一般，版权情况复杂——定位为"试读/找书"工具
- 索引快照存于 `all-books.json`（2026-08-29 下载，24071 本）；数据源不定期更新，若用户反馈某新书找不到，先跑一次 `--refresh` 再搜
- 下载的 JSON 偶尔截断导致解析失败，重试下载即可（已内置在 --refresh）

## 数据来源

- 项目主页：https://github.com/jbiaojerry/ebook-treasure-chest
- 在线搜索页：https://jbiaojerry.github.io/ebook-treasure-chest/
- 索引数据：all-books.json（源自该站，仅供个人学习使用）
