# -*- coding: utf-8 -*-
"""小米 NAS 影视库重命名执行器（WebDAV 同目录 MOVE，不删除任何文件）

把「拼音缩写/中文描述」命名的剧集文件，改成影视墙刮削器可识别的标准命名：
    {Show} S01E01.mkv / {Show} S01E01.zh.srt / {Show} S01E01.en.srt
    外层目录 → {Show} ({Year})，季目录 → Season N

用法：
    python nas_rename.py --dry \
        --old-dir "/pool0/data/百度网盘/蛇蝎美人 1-2季 1080p（3种字幕：中英文、纯英文、无字幕）" \
        --new-dir "/pool0/data/百度网盘/Femme Fatales (2011)" \
        --show "Femme Fatales" --prefix "SXMR" \
        --seasons "S01:Season 1,S02:Season 2"

参数说明：
    --old-dir    旧目录（WebDAV 路径，/pool0/data/... 前缀）
    --new-dir    改名后的外层目录
    --show       刮削用剧名（如 Femme Fatales）
    --prefix     旧文件名前缀（如 SXMR=蛇蝎美人拼音首字母）
    --seasons    季目录映射，逗号分隔 "旧:新"（默认 S01:Season 1,S02:Season 2）
    --year       剧集年份，仅在 --show 里已含年份时不需要
    --dry        只打印计划不执行（推荐先跑）
    --no-auto-creds  不用 get_pool_info 动态取密码（改用环境变量 NAS_WEBDAV_PWD）

安全设计：
  * 全部为同目录内 MOVE（先文件→再外层目录→再季目录），任何一步失败即中止，不删除
  * 跳过未匹配文件（如 *.baiduyun.p.downloading 未下载完成）
  * 文件改名全部成功后才动目录，避免路径错乱
"""
import os, sys, re, argparse, json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nas_common import SmartStorageSession


def parse_args():
    ap = argparse.ArgumentParser(description="小米 NAS 影视库重命名（WebDAV MOVE）")
    ap.add_argument("--old-dir", required=True)
    ap.add_argument("--new-dir", required=True)
    ap.add_argument("--show", required=True, help="刮削用剧名，如 Femme Fatales")
    ap.add_argument("--prefix", required=True, help="旧文件名前缀，如 SXMR")
    ap.add_argument("--seasons", default="S01:Season 1,S02:Season 2",
                    help='季目录映射 "旧:新,旧:新"')
    ap.add_argument("--year", default="", help="年份（仅当剧名里没带时提示用）")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--no-auto-creds", action="store_true")
    return ap.parse_args()


def build_plan(s, old_base, show, prefix, season_map):
    """生成文件改名计划 (src, dst, new_season)；返回 (plan, skipped)"""
    plan, skipped = [], []
    pat = re.compile(rf'^{re.escape(prefix)} (S\d+E\d+)(-EN)?\.(mkv|srt|mp4|avi|ts)$')
    for season, new_season in season_map.items():
        names, err = s.dav_list(f"{old_base}/{season}")
        if err:
            skipped.append((season, None, f"列目录失败: {err}"))
            continue
        for name in names:
            m = pat.match(name)
            if not m:
                skipped.append((season, name, "未匹配命名规则"))
                continue
            ep, is_en, ext = m.group(1), m.group(2), m.group(3)
            src = f"{old_base}/{season}/{name}"
            if ext in ('mkv', 'mp4', 'avi', 'ts'):
                new_name = f"{show} {ep}.{ext}"
            elif is_en:
                new_name = f"{show} {ep}.en.srt"
            else:
                new_name = f"{show} {ep}.zh.srt"
            plan.append((src, f"{old_base}/{season}/{new_name}", new_season))
    return plan, skipped


def main():
    args = parse_args()
    season_map = {}
    for pair in args.seasons.split(','):
        k, v = pair.split(':')
        season_map[k.strip()] = v.strip()

    with SmartStorageSession() as s:
        s.start()
        s.wait_device()
        s.wait_ports()
        if args.no_auto_creds:
            s.wd_user = os.environ.get("NAS_WEBDAV_USER", "")
            s.wd_pass = os.environ.get("NAS_WEBDAV_PWD", "")
            if not s.wd_pass:
                sys.exit("[X] --no-auto-creds 需要环境变量 NAS_WEBDAV_USER / NAS_WEBDAV_PWD")
            import base64
            s._b64 = base64.b64encode(f"{s.wd_user}:{s.wd_pass}".encode()).decode()
        else:
            s.fetch_webdav_creds()

        # [0] 验证旧目录
        st, v = s.propfind(args.old_dir, '0')
        if st not in (207, 200):
            print(f"[X] 旧目录不可访问 http={st} {v[:200]}", flush=True)
            sys.exit(1)
        print("[3] 旧目录存在，UA/凭证已通过 451 检查", flush=True)

        # [1] 生成计划
        plan, skipped = build_plan(s, args.old_dir, args.show, args.prefix, season_map)
        print(f"\n[4] 文件改名计划: {len(plan)} 个")
        for src, dst, _ns in plan:
            print(f"    {src.split('/')[-1]}  ->  {dst.split('/')[-1]}")
        for season, name, why in skipped:
            print(f"    [SKIP] {season}/{name or ''} （{why}）")

        if args.dry:
            print("\n[DRY] 试运行结束：连通正常，计划如上。去掉 --dry 正式执行。", flush=True)
            return

        # [2] 执行文件改名（同目录内）
        print(f"\n[5] 执行文件改名...")
        ok = fail = 0
        for src, dst, _ns in plan:
            st, v = s.move(src, dst)
            if st in (201, 204, 200):
                ok += 1
            else:
                fail += 1
                print(f"  [FAIL] {src.split('/')[-1]} | http={st} {v[:150]}", flush=True)
        print(f"  文件改名: 成功 {ok} / 失败 {fail}", flush=True)
        if fail:
            sys.exit("[!] 有失败项，停止后续目录改名，避免路径错乱")

        # [3] 外层目录改名
        print("\n[6] 外层目录改名...")
        st, v = s.move(args.old_dir, args.new_dir)
        print(f"  {args.old_dir.split('/')[-1]} -> {args.new_dir.split('/')[-1]} | http={st}", flush=True)
        if st not in (201, 204, 200):
            sys.exit("[X] 外层目录改名失败，中止")

        # [4] 季目录改名
        print("\n[7] 季目录改名...")
        for old_s, new_s in season_map.items():
            st, v = s.move(f"{args.new_dir}/{old_s}", f"{args.new_dir}/{new_s}")
            print(f"  {old_s} -> {new_s} | http={st}", flush=True)

        # [5] 验证最终结构
        print("\n[8] 验证最终结构...")
        for d in [args.new_dir] + [f"{args.new_dir}/{ns}" for ns in season_map.values()]:
            st, v = s.propfind(d, '1')
            hrefs = re.findall(r'<[dD]:href>([^<]+)</[dD]:href>', v)
            print(f"  {d.split('/')[-1]}: http={st} 条目={max(0, len(hrefs)-1)}", flush=True)
            for h in hrefs[:12]:
                print(f"    {urllib.parse.unquote(h)}", flush=True)

    print("\n完成。请在小爱同学/小米影视墙重新扫描媒体库。", flush=True)


if __name__ == '__main__':
    import urllib.parse  # 供上面验证段使用
    main()
