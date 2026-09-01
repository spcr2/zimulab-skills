# -*- coding: utf-8 -*-
"""NAS 影视库批量规范化（2026-09-01 第二轮：刚下载完成的资源）
覆盖：大时代Ⅰ / 灌篮高手TV版 / 棒球英豪 / 浪客剑心TV正片 / 恐龙特急克塞号 / 绝代双骄 / 鹿鼎记 / 绝望的主妇(8季)
跳过：进击的巨人（OAD/第04季仍下载中）、西部世界（S01/S03/S04缺集）、纸牌屋（双版本待确认）、
      Q-请回答1988国语(ts)、豆瓣TOP250合集、珍藏 棒球英豪！！（与棒球英豪重复，待确认）
用法：python nas_batch_round2.py          # dry-run 预览
      python nas_batch_round2.py --run    # 正式执行
"""
import sys, re, os
sys.path.insert(0, "C:/Users/liuzimu/.workbuddy/skills/mijia-nas-media-library/scripts")
from nas_common import SmartStorageSession

RUN = '--run' in sys.argv
NAS = '/pool0/data/百度网盘/NAS下载'
VIDEO_EXT = ('mp4', 'mkv', 'avi', 'ts', 'mov', 'wmv', 'flv', 'rmvb', 'm4v', 'rm')

# ---------- 集数解析函数：返回 (ep, ext) 或 None ----------
def ep_ekaterina(name):
    m = re.search(r'（资源V：\w+）(?:E|EP|第)?\s*[-—]?\s*0*(\d{1,3})\s*(?:\.(\w+))?$', name)
    return (int(m.group(1)), m.group(2) or 'mp4') if m else None

def ep_rm_ads(name):
    """人民的名义 01【更多高清4K尽在4K帝国www.4kdg.cn】.mp4"""
    m = re.search(r'^人民的名义\s*0*(\d{1,3})【.*?】\.(\w+)$', name)
    return (int(m.group(1)), m.group(2)) if m else None

def ep_plain(name):
    """01.mp4 / 01.mkv 纯数字"""
    m = re.search(r'^0*(\d{1,3})\.(\w+)$', name)
    return (int(m.group(1)), m.group(2)) if m else None

def ep_double(name):
    """01.mp4.mp4 双扩展名"""
    m = re.search(r'^0*(\d{1,3})\.mp4\.mp4$', name)
    return (int(m.group(1)), 'mp4') if m else None

def ep_zhen_guan(name):
    """贞观之治.Control.by.Zhen.Guan.2007.E01.2160p...-OurTV.mp4"""
    m = re.search(r'\.E(\d{1,2})\.', name)
    e = re.search(r'\.(\w+)$', name)
    return (int(m.group(1)), e.group(1)) if m and e else None

def ep_sanguo(name):
    """三国演义.The...1994.EP01.4K...-www.4kdg.cn.mp4"""
    m = re.search(r'EP(\d{1,2})\.', name)
    e = re.search(r'\.(\w+)$', name)
    return (int(m.group(1)), e.group(1)) if m and e else None

# ---------- 第二轮解析函数（2026-09-01） ----------
def ep_greed(name):
    """大时代Ⅰ.1992.DVDrip.2audio.EP01.mkv / EP40.END.mkv（杂质版本无法匹配→SKIP）"""
    m = re.search(r'^大时代Ⅰ\.1992\.DVDrip\.2audio\.EP(\d{2})(?:\.END)?\.(\w+)$', name)
    return (int(m.group(1)), m.group(2)) if m else None

def ep_slamdunk(name):
    """【001】天才篮球员诞生？！.mkv"""
    m = re.search(r'^【(\d{3})】.*\.(\w+)$', name)
    return (int(m.group(1)), m.group(2)) if m else None

def ep_touch(name):
    """XTM.DVD-HALFCD2.棒球英豪.Touch.1985.日本.国日双语.EP001.mkv"""
    m = re.search(r'\.EP(\d{2,3})\.(\w+)$', name)
    return (int(m.group(1)), m.group(2)) if m else None

def ep_kenshin_tv(name):
    """浪客剑心 Rurouni Kenshin 01.rmvb（纯数字=TV正片；追忆篇/星霜篇/剧场版等特殊文件→SKIP保留）"""
    m = re.search(r'^浪客剑心 Rurouni Kenshin (\d{2})\.(\w+)$', name)
    return (int(m.group(1)), m.group(2)) if m else None

def ep_koseidon(name):
    """恐龙特急克塞号01：克塞号出击.DVDRip...mkv"""
    m = re.search(r'^恐龙特急克塞号(\d{2})：.*\.(\w+)$', name)
    return (int(m.group(1)), m.group(2)) if m else None

def ep_handsome(name):
    """绝代双骄.1999.EP01.DVDRip.X264.2Audio.AAC.INT.mkv"""
    m = re.search(r'^绝代双骄\.1999\.EP(\d{2})\..*\.(\w+)$', name)
    return (int(m.group(1)), m.group(2)) if m else None

def ep_duke(name):
    """鹿鼎记.1998.DVDrip.2audio.EP01.mkv（杂质 01 【www.pantb.com】 .mkv→SKIP）"""
    m = re.search(r'^鹿鼎记\.1998\.DVDrip\.2audio\.EP(\d{2})\.(\w+)$', name)
    return (int(m.group(1)), m.group(2)) if m else None

def ep_dh(name):
    """（资源V：zlwc18）S01E01.mp4（绝望的主妇季内文件）"""
    m = re.search(r'^（资源V：\w+）S\d{2}E(\d{2})\.(\w+)$', name)
    return (int(m.group(1)), m.group(2)) if m else None

# ---------- 任务定义 ----------
JOBS = [
    # 大时代Ⅰ：40 集 EP 命名 + 5 个杂质版本（无法解析→保留）
    dict(mode='flat',
         old=f'{NAS}/大时代Ⅰ.1992.DVDrip.2audio（40集）',
         new=f'{NAS}/The Greed of Man 大时代 (1992)',
         show='The Greed of Man', parse=ep_greed),
    # 灌篮高手 TV版：101 集【NNN】命名，从灌篮高手目录提升到 NAS下载 同级
    dict(mode='flat',
         old=f'{NAS}/灌篮高手/[灌篮高手TV版][101集全][国日粤三语][简繁字幕][720P][DVDRip][Hi10p][[MKV][49.6G]',
         new=f'{NAS}/Slam Dunk 灌篮高手 (1993)',
         show='Slam Dunk', parse=ep_slamdunk),
    # 棒球英豪：EP074 仍在下载（.downloading 标记）+ EP043repack 待确认 → 跳过（等下载完）
    # dict(mode='flat',
    #      old=f'{NAS}/棒球英豪 日语中字（mkv）共101集',
    #      new=f'{NAS}/Touch 棒球英豪 (1985)',
    #      show='Touch', parse=ep_touch),
    # 浪客剑心：TV 正片 95 集；追忆篇/星霜篇/剧场版/密藏篇/完结篇 保留在新目录根下
    dict(mode='flat',
         old=f'{NAS}/浪客剑心[完] 完结篇+追忆篇+剧场版+星霜篇+密藏篇',
         new=f'{NAS}/Rurouni Kenshin 浪客剑心 (1996)',
         show='Rurouni Kenshin', parse=ep_kenshin_tv),
    # 恐龙特急克塞号：35 集
    dict(mode='flat',
         old=f'{NAS}/恐龙特急克塞号(70,80的回忆)',
         new=f'{NAS}/Dinosaur Corps Koseidon 恐龙特急克塞号 (1978)',
         show='Dinosaur Corps Koseidon', parse=ep_koseidon),
    # 绝代双骄：40 集
    dict(mode='flat',
         old=f'{NAS}/绝代双骄.1999.DVDRip.X264.2Audio.AAC.INT（40集，林志颖、苏有朋）',
         new=f'{NAS}/The Handsome Siblings 绝代双骄 (1999)',
         show='The Handsome Siblings', parse=ep_handsome),
    # 鹿鼎记：45 集 + 2 杂质（保留）
    dict(mode='flat',
         old=f'{NAS}/鹿鼎记.1998.DVDrip.2audio（45集）',
         new=f'{NAS}/The Duke of Mount Deer 鹿鼎记 (1998)',
         show='The Duke of Mount Deer', parse=ep_duke),
    # 绝望的主妇：8 季，季目录（资源V：rong88044666）1-8 → Season 1-8
    dict(mode='season_dirs',
         old=f'{NAS}/绝望的主妇1-8（1080p）',
         new=f'{NAS}/Desperate Housewives 绝望的主妇 (2004)',
         show='Desperate Housewives', parse=ep_dh,
         seasons=[(f'（资源V：rong88044666）{i}', f'Season {i}', i) for i in range(1, 9)]),
]

def mkcol(s, path):
    st, v = s.dav('MKCOL', path)
    return st in (201, 204, 200, 405)

def build_plan(s, job):
    """生成 (src, dst, kind) 计划；kind: file / dir / mkdir"""
    plan = []
    mode = job['mode']
    if mode == 'season_dirs':
        for old_season, new_season, no in job['seasons']:
            plan.append((job['old'] + '/' + old_season, job['old'] + '/' + new_season, 'dir'))
            items, err = s.dav_list(job['old'] + '/' + old_season)
            if err:
                print(f'  [ERR] {job["old"]}/{old_season}: {err}'); continue
            for n in sorted(items):
                p = job['parse'](n)
                if not p:
                    print(f'  [SKIP 无法解析] {old_season}/{n}'); continue
                ep, ext = p
                new_name = f'{job["show"]} S{no:02d}E{ep:02d}.{ext}'
                plan.append((f'{job["old"]}/{new_season}/{n}', f'{job["old"]}/{new_season}/{new_name}', 'file'))
        plan.append((job['old'], job['new'], 'dir'))
    elif mode == 'flat':
        plan.append((job['old'] + '/Season 1', None, 'mkdir'))
        items, err = s.dav_list(job['old'])
        if err:
            print(f'  [ERR] {job["old"]}: {err}')
        else:
            for n in sorted(items):
                if n == 'Season 1':
                    continue
                if not n.lower().endswith(VIDEO_EXT):
                    print(f'  [SKIP 非视频] {n}'); continue
                p = job['parse'](n)
                if not p:
                    print(f'  [SKIP 无法解析] {n}'); continue
                ep, ext = p
                new_name = f'{job["show"]} S01E{ep:02d}.{ext}'
                plan.append((f'{job["old"]}/{n}', f'{job["old"]}/Season 1/{new_name}', 'file'))
        plan.append((job['old'], job['new'], 'dir'))
    elif mode == 'reply':
        for sub, new_name, show, parse in job['subs']:
            subdir = job['old'] + '/' + sub
            plan.append((subdir + '/Season 1', None, 'mkdir'))
            items, err = s.dav_list(subdir)
            if err:
                print(f'  [ERR] {subdir}: {err}'); continue
            for n in sorted(items):
                if n == 'Season 1':
                    continue
                p = parse(n)
                if not p:
                    print(f'  [SKIP 无法解析] {sub}/{n}'); continue
                ep, ext = p
                plan.append((f'{subdir}/{n}', f'{subdir}/Season 1/{show} S01E{ep:02d}.{ext}', 'file'))
            plan.append((subdir, f'{NAS}/{new_name}', 'dir'))
    return plan

def main():
    with SmartStorageSession() as s:
        s.start(); s.wait_device(); s.wait_ports(); s.fetch_webdav_creds()
        print(f'===== 批量规范化（{"EXECUTE" if RUN else "DRY-RUN"}）=====\n')
        all_plans = {}
        for job in JOBS:
            new_tail = job.get('new', job['old']).split('/')[-1]
            print(f'### {job["old"].split("/")[-1]}  ->  {new_tail}')
            plan = build_plan(s, job)
            all_plans[job['old']] = plan
            print(f'    计划 {len(plan)} 步')
            if not RUN:
                skips = [p for p in plan if False]
                # 摘要模式：只打印 SKIP 和按类型统计
                n_file = sum(1 for p in plan if p[2] == 'file')
                n_dir = sum(1 for p in plan if p[2] == 'dir')
                n_mk = sum(1 for p in plan if p[2] == 'mkdir')
                print(f'    [摘要] 文件 {n_file} | 目录改名 {n_dir} | 新建目录 {n_mk}')
                # 校验集数连续性
                eps = []
                for src, dst, kind in plan:
                    if kind == 'file':
                        m = re.search(r'S\d{2}E(\d{2,3})\.', dst)
                        if m: eps.append(int(m.group(1)))
                if eps:
                    missing = sorted(set(range(min(eps), max(eps)+1)) - set(eps))
                    print(f'    [集数] {min(eps)}~{max(eps)} 共{len(eps)}集 缺失: {missing if missing else "无"}')
            print()
        if not RUN:
            print('[DRY-RUN] 未执行。加 --run 正式执行。')
            return
        # ---- 执行 ----
        print('===== 执行中 =====')
        ok = fail = 0
        for job in JOBS:
            print(f'--- {job["old"].split("/")[-1]} ---')
            for src, dst, kind in all_plans[job['old']]:
                if kind == 'mkdir':
                    mkcol(s, src); print(f'  [MKCOL] {src}'); continue
                st, v = s.move(src, dst)
                if st in (201, 204, 200):
                    ok += 1; print(f'  [OK] {src}\n        -> {dst}')
                else:
                    fail += 1; print(f'  [FAIL {st}] {src}')
        print(f'\n完成: OK={ok} FAIL={fail}')

if __name__ == '__main__':
    main()
