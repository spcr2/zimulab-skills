# 数据源与索引说明

## 项目背景

- 项目：ebook-treasure-chest（电子书下载宝库）
- 地址：https://github.com/jbiaojerry/ebook-treasure-chest
- 在线搜索页：https://jbiaojerry.github.io/ebook-treasure-chest/（页面加载 all-books.json 做客户端实时搜索）
- 覆盖：帆书（原樊登读书）、微信读书、京东读书、喜马拉雅等平台的大部分中文电子书，约 24,071 本、1,000 分类

## all-books.json 结构

```json
[
  {
    "title": "极度成功",
    "author": "丹尼尔・科伊尔",
    "link": "https://url89.ctfile.com/f/31084289-1375510375-05242f?p=8866",
    "category": "企业",
    "language": "ZH",
    "level": "Unknown",
    "formats": ["epub", "mobi", "azw3"]
  }
]
```

- link 为城通网盘（ctfile）直链，URL 中 `p=` 后面的值即提取码
- 同一本书可能出现在多个分类下（如《底层逻辑》同时在"逻辑"和"商业"），汇报时去重

## 已知坑

1. **下载易截断**：all-books.json 约 7MB，curl 下载偶发不完整（JSON 解析失败）。`--refresh` 已内置"下载→校验→失败重试"逻辑；手动下载时务必校验 `python -c "import json; json.load(open(...))"`。
2. **作者名分隔符**：数据中用全角中点「・」，搜索脚本已做归一化（同时兼容「·」和空串）。
3. **6.7→6.8 类似的下线问题**：无。本索引是纯静态数据，数据源更新后旧链接可能失效，遇到失效链接建议跑 `--refresh` 更新索引。

## 刷新命令

```bash
python "~/.workbuddy/skills/ebook-finder/scripts/search.py" --refresh
```
