# -*- coding: utf-8 -*-
"""电子书下载宝库本地搜索脚本。

用法：
  python search.py "关键词1 关键词2"        # 多关键词 AND 匹配（书名/作者/分类）
  python search.py --cat "文学"             # 按分类列出书籍
  python search.py --cat "文学" --limit 50  # 控制输出条数
  python search.py --stats                  # 显示库统计并提示刷新
  python search.py --refresh                # 重新下载最新索引（需网络）

输出：JSON 数组，每条含 title / author / category / link / formats。
"""
import json
import sys
import os
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(HERE, "..", "all-books.json")
URL = "https://jbiaojerry.github.io/ebook-treasure-chest/all-books.json"


def load():
    with open(INDEX, encoding="utf-8") as f:
        return json.load(f)


def refresh():
    print(json.dumps({"status": "refreshing", "url": URL}, ensure_ascii=False))
    for cmd in (["curl", "-sL", "--max-time", "120", URL, "-o", INDEX + ".tmp"],):
        subprocess.run(cmd, check=False)
    try:
        with open(INDEX + ".tmp", encoding="utf-8") as f:
            data = json.load(f)
        os.replace(INDEX + ".tmp", INDEX)
        print(json.dumps({"status": "refreshed", "books": len(data)}, ensure_ascii=False))
        return data
    except Exception as e:
        print(json.dumps({"status": "refresh-failed", "error": str(e)}, ensure_ascii=False))
        return load()


def norm(s):
    return (s or "").lower().replace(" ", "").replace("・", "·").replace("·", "")


def search(books, query):
    kws = [norm(k) for k in query.split() if k.strip()]
    hits = []
    for b in books:
        hay = norm(b.get("title", "")) + "|" + norm(b.get("author", "")) + "|" + norm(b.get("category", ""))
        if all(k in hay for k in kws):
            hits.append(b)
    return hits


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return

    if args[0] == "--stats":
        books = load()
        print(json.dumps({"books": len(books), "categories": len(set(b.get("category", "") for b in books))}, ensure_ascii=False))
        return

    if args[0] == "--refresh":
        refresh()
        return

    books = load()
    limit = 20
    if "--limit" in args:
        i = args.index("--limit")
        limit = int(args[i + 1])
        args = args[:i] + args[i + 2:]

    if args[0] == "--cat":
        cat = " ".join(args[1:])
        hits = [b for b in books if norm(cat) in norm(b.get("category", ""))]
    else:
        hits = search(books, " ".join(args))

    hits.sort(key=lambda b: b.get("title", ""))
    print(json.dumps({"total": len(hits), "returned": min(len(hits), limit), "results": hits[:limit]}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
