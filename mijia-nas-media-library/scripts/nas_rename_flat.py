# -*- coding: utf-8 -*-
"""小米 NAS 影视库重命名（纯数字平铺版）

适用于网盘下载的「01.mp4 / 01.srt ... 45.mp4 / 45.srt」平铺在单目录、
无统一前缀的资源（如港剧粤语版、老剧合集），转成影视墙刮削标准：

    {Show} ({Year})/
        Season 1/
            {Show} S01E01.mp4 / {Show} S01E01.zh.srt ...

用法：
    python nas_rename_flat.py --dry \
        --old-dir "/pool0/data/百度网盘/NAS下载/全45集，粤语外挂" \
        --new-dir "/pool0/data/百度网盘/NAS下载/The Demi-Gods and Semi-Devils 天龙八部 (1997)" \
        --show "The Demi-Gods and Semi-Devils"

参数说明：
    --old-dir    旧目录（WebDAV 路径，/pool0/data/... 前缀）
    --new-dir    改名后的外层目录（建议含年份与中文名辅助识别）
    --show       刮削用剧名（英文优先，TMDB/TVDB 通用）
    --dry        只打印计划不执行（默认）
    --run        正式执行
    --no-auto-creds  不用 get_pool_info 动态取密码（改用环境变量 NAS_WEBDAV_PWD）

命名匹配：顶层文件 `NN.mp4|srt|mkv|avi|ts`（NN 为 1-2 位集数，01-99）
非视频/字幕文件与未知目录（如弹幕/）自动保留，随外层目录一起改名。

安全设计：同盘 WebDAV MOVE 零删除；先文件移动、全部成功后再改外层目录名；
任何失败即中止，避免路径错乱。
"""
import os, sys, re, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nas_common import SmartStorageSession

EP_PAT = re.compile(r'^(\d{1,2})\.(mp4|srt|mkv|avi|ts)$')
SEASON_DIR = "Season 1"


def parse_args():
    import argparse
    ap = argparse.ArgumentParser(description="小米 NAS 影视库重命名（纯数字平铺版）")
    ap.add_argument("--old-dir", required=True)
    ap.add_argument("--new-dir", required=True)
    ap.add_argument("--show", required=True, help="刮削用剧名，如 The Demi-Gods and Semi-Devils")
    ap.add_argument("--dry", action="store_true", default=False)
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--no-auto-creds", action="store_true")
    return ap.parse_args()


def dav_mkcol(s, path):
    """创建目录，已存在返回 405 也 OK"""
    st, v = s.dav('MKCOL', path)
    return st in (201, 204, 200, 405), st, v


def main():
    args = parse_args()
    dry = not args.run  # 默认 dry，--run 才执行
    old_dir, new_dir, show = args.old_dir.rstrip('/'), args.new_dir.rstrip('/'), args.show

    with SmartStorageSession() as s:
        s.start()
        s.wait_device()
        s.wait_ports()
        if args.no_auto_creds:
            import os as _os, base64
            s.wd_user = _os.environ.get("NAS_WEBDAV_USER", "")
            s.wd_pass = _os.environ.get("NAS_WEBDAV_PWD", "")
            if not s.wd_pass:
                sys.exit("[X] --no-auto-creds 需要环境变量 NAS_WEBDAV_USER / NAS_WEBDAV_PWD")
            s._b64 = base64.b64encode(f"{s.wd_user}:{s.wd_pass}".encode()).decode()
        else:
            s.fetch_webdav_creds()

        # [0] 验证旧目录
        st, v = s.propfind(old_dir, '0')
        if st not in (207, 200):
            print(f"[X] 旧目录不可访问 http={st} {v[:200]}", flush=True)
            sys.exit(1)
        print(f"[OK] 旧目录存在: {old_dir}", flush=True)

        # [1] 列出旧目录
        st, v = s.propfind(old_dir, '1')
        hrefs = re.findall(r'<[dD]:href>([^<]+)</[dD]:href>', v)
        plan, skips = [], []
        for h in hrefs[1:]:
            raw = urllib.parse.unquote(h.rstrip('/'))
            name = raw.rstrip('/').split('/')[-1]
            is_dir = h.endswith('/')
            if is_dir:
                skips.append((name, "目录（保留，随外层目录改名）"))
                continue
            m = EP_PAT.match(name)
            if not m:
                skips.append((name, "未匹配纯数字命名，保留"))
                continue
            ep_num, ext = int(m.group(1)), m.group(2)
            ep = f"S01E{ep_num:02d}"
            if ext in ('mp4', 'mkv', 'avi', 'ts'):
                new_name = f"{show} {ep}.{ext}"
            else:
                new_name = f"{show} {ep}.zh.srt"
            plan.append((raw, f"{old_dir}/{SEASON_DIR}/{new_name}", f"{name} -> Season 1/{new_name}"))

        print(f"\n[计划] 需要移动/改名 {len(plan)} 项，保留 {len(skips)} 项", flush=True)
        for src, dst, desc in plan[:12]:
            print(f"    {desc}")
        if len(plan) > 12:
            print(f"    ... 共 {len(plan)} 项")
        for name, why in skips[:5]:
            print(f"    [保留] {name}（{why}）")

        if dry:
            print("\n[DRY] 试运行结束：连通正常，计划如上。加 --run 正式执行。", flush=True)
            return

        # [2] 创建季目录
        print("\n[执行] 创建季目录...", flush=True)
        season_path = f"{old_dir}/{SEASON_DIR}"
        ok, st, v = dav_mkcol(s, season_path)
        if not ok:
            print(f"[X] 创建 {SEASON_DIR} 失败 http={st}: {v[:200]}", flush=True)
            sys.exit(1)
        print(f"  {SEASON_DIR} ok/已存在", flush=True)

        # [3] 移动/改名文件
        print("\n[执行] 移动/改名文件...", flush=True)
        ok_n = fail_n = 0
        for src, dst, desc in plan:
            st, v = s.move(src, dst)
            if st in (201, 204, 200):
                ok_n += 1
            else:
                fail_n += 1
                print(f"  [FAIL] {desc} | http={st} {v[:150]}", flush=True)
        print(f"  结果: 成功 {ok_n} / 失败 {fail_n}", flush=True)
        if fail_n:
            sys.exit("[!] 有失败项，停止外层目录改名，避免路径错乱")

        # [4] 外层目录改名
        print("\n[执行] 外层目录改名...", flush=True)
        st, v = s.move(old_dir, new_dir)
        print(f"  {old_dir.split('/')[-1]} -> {new_dir.split('/')[-1]} | http={st}", flush=True)
        if st not in (201, 204, 200):
            sys.exit("[X] 外层目录改名失败，中止")

        # [5] 验证
        print("\n[验证] 最终结构...", flush=True)
        st, v = s.propfind(new_dir, '1')
        hrefs = re.findall(r'<[dD]:href>([^<]+)</[dD]:href>', v)
        print(f"  {new_dir.split('/')[-1]}: http={st} 条目={max(0, len(hrefs)-1)}", flush=True)
        for h in hrefs[1:]:
            name = urllib.parse.unquote(h.rstrip('/').split('/')[-1])
            print(f"    {'[DIR]' if h.endswith('/') else '[FILE]'} {name}", flush=True)
            if name == SEASON_DIR:
                st2, v2 = s.propfind(urllib.parse.unquote(h.rstrip('/')), '1')
                sub = re.findall(r'<[dD]:href>([^<]+)</[dD]:href>', v2)
                print(f"      -> 子条目 {max(0, len(sub)-1)} 个", flush=True)

        print("\n完成。请在小爱同学/小米影视墙重新扫描媒体库。", flush=True)


if __name__ == '__main__':
    main()
