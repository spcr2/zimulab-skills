# -*- coding: utf-8 -*-
"""NAS 影视库批量规范化（2026-08-31 全库整理）
覆盖：叶卡捷琳娜大帝(3季) / 人民的名义 / 大宅门 / 大明王朝1566 / 贞观之治 / 三国演义 / 请回答1988·1994·1997
跳过：下载中目录（大时代Ⅰ、进击的巨人、绝望的主妇、西部世界、纸牌屋、灌篮高手 等）
用法：python nas_batch_normalize.py          # dry-run 预览
      python nas_batch_normalize.py --run    # 正式执行
"""
import sys, re, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
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

# ---------- 任务定义 ----------
JOBS = [
    # 模式 season_dirs：季目录改名 + 文件原地改名 + 外层改名
    dict(mode='season_dirs',
         old=f'{NAS}/叶卡捷琳娜大帝1-3',
         new=f'{NAS}/Ekaterina 叶卡捷琳娜大帝 (2014)',
         show='Ekaterina', parse=ep_ekaterina,
         seasons=[('（资源V：rong88044666）S01', 'Season 1', 1),
                  ('（资源V：rong88044666）S02', 'Season 2', 2),
                  ('（资源V：rong88044666）s03', 'Season 3', 3)]),
    # 模式 flat：建 Season 1 + 文件改名移入 + 外层改名
    dict(mode='flat',
         old=f'{NAS}/人民的名义DVD版.全55集.4K.60FPS高码珍藏版.WEB-DL.H265.10BIT.AAC-AIU',
         new=f'{NAS}/In the Name of People 人民的名义 (2017)',
         show='In the Name of People', parse=ep_rm_ads),
    dict(mode='flat',
         old=f'{NAS}/大宅门第一部',
         new=f'{NAS}/The Grand Mansion Gate 大宅门 (2001)',
         show='The Grand Mansion Gate', parse=ep_plain),
    dict(mode='flat',
         old=f'{NAS}/D 2007大明王朝1566',
         new=f'{NAS}/Ming Dynasty 1566 大明王朝1566 (2007)',
         show='Ming Dynasty 1566', parse=ep_plain),
    dict(mode='flat',
         old=f'{NAS}/【国产剧】贞观之治                           （9.2分）   [2006-2007]   2160P x265       全50集',
         new=f'{NAS}/Zhen Guan Zhi Zhi 贞观之治 (2007)',
         show='Zhen Guan Zhi Zhi', parse=ep_zhen_guan),
    dict(mode='flat',
         old=f'{NAS}/三国演义.The.Romance.Of.Three.Kingdoms.1994.4K.2160p.WEPB-DL.H265.AAC-www.4kdg.cn',
         new=f'{NAS}/The Romance of the Three Kingdoms 三国演义 (1994)',
         show='The Romance of the Three Kingdoms', parse=ep_sanguo),
    # 模式 reply：子目录各自建 Season 1 + 提升到 NAS下载 同级（1988国语 保留原目录）
    dict(mode='reply',
         old=f'{NAS}/Q-请回答1988',
         subs=[('1988', 'Reply 1988 请回答1988 (2015)', 'Reply 1988', ep_double),
               ('1994', 'Reply 1994 请回答1994 (2013)', 'Reply 1994', ep_plain),
               ('1997', 'Reply 1997 请回答1997 (2012)', 'Reply 1997', ep_plain)]),
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
                for src, dst, kind in plan:
                    if kind == 'mkdir':
                        print(f'    [MKCOL] {src}')
                    elif kind == 'dir':
                        print(f'    [DIR ] {src}\n           -> {dst}')
                    else:
                        print(f'    [FILE] {src}\n           -> {dst}')
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
