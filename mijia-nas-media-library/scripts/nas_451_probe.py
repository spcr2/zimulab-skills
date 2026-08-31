# -*- coding: utf-8 -*-
"""WebDAV 451 全因子诊断探针（Host / 路径前缀 / 方法 / UA / auth 批量测试）

当重命名/列目录遇到 http=451（nginx 拦截）时，跑本脚本定位触发因素。
历史结论（本机已验证）：
  * 路径前缀是主因：WebDAV 用 /pool0/data/...（207）；带 /home/u1943294 别名前缀 → 451
  * UA 是次要件：缺客户端 UA 也会拦（451/403）
  * Host 头、OPTIONS、GET 等方法与 451 无关
"""
import os, sys, json, re, base64, http.client, urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nas_common import SmartStorageSession, NAS_IP


def test(s, label, method, path, host=None, use_ua=True, use_auth=True, headers=None, timeout=15):
    """完整请求，返回 (status, resp_headers, body)"""
    if not s.ctx:
        s._init_ssl()
    conn = http.client.HTTPSConnection(
        '127.0.0.1', int(s.wdport), timeout=timeout, context=s.ctx)
    hdrs = {}
    if use_auth:
        hdrs['Authorization'] = 'Basic ' + s._b64
    if use_ua:
        hdrs['User-Agent'] = s.ua
    if host:
        hdrs['Host'] = host
    hdrs['Content-Type'] = 'application/octet-stream'
    if headers:
        hdrs.update(headers)
    try:
        conn.request(method, urllib.parse.quote(path, safe="/"), headers=hdrs)
        resp = conn.getresponse()
        hdrs_out = {k.lower(): v for k, v in resp.getheaders()}
        body = resp.read().decode('utf-8', errors='replace')[:300]
        conn.close()
        print(f"  [{label}] {method} {path[:60]}... -> {resp.status} | body={body[:80]!r}", flush=True)
        return resp.status, hdrs_out, body
    except Exception as e:
        print(f"  [{label}] {method} {path[:60]}... -> EXC {str(e)[:100]}", flush=True)
        return None, {}, str(e)[:100]


def main():
    with SmartStorageSession() as s:
        s.start()
        s.wait_device()
        s.wait_ports()
        s.fetch_webdav_creds()

        OLD_BASE = "/home/u1943294/pool0/data/百度网盘"
        POOL_BASE = "/pool0/data/百度网盘"

        print("\n[A] 基线：UA+auth+默认Host（alias 前缀）", flush=True)
        test(s, "A1", "PROPFIND", OLD_BASE, headers={'Depth': '0'})

        print("\n[B] Host 头变体", flush=True)
        for h in [f"127.0.0.1:{s.wdport}", NAS_IP, f"{NAS_IP}:{s.wdport}", f"{NAS_IP}:5000",
                  "localhost", f"localhost:{s.wdport}"]:
            test(s, "B-" + h.replace(':', '_'), "PROPFIND", OLD_BASE, host=h, headers={'Depth': '0'})

        print("\n[C] 路径前缀变体（关键！/pool0/... vs /home/u.../pool0/...）", flush=True)
        for p in [OLD_BASE, POOL_BASE, "/百度网盘", "/home/u1943294/pool0/data/",
                  "/home/u1943294/", "/", "/pool0/data/"]:
            test(s, "C-" + (p.split('/')[-1][:18] or "root"), "PROPFIND", p, headers={'Depth': '0'})

        print("\n[D] OPTIONS 探测", flush=True)
        for p in ["/", "/home/u1943294/", OLD_BASE]:
            test(s, "D-" + (p.split('/')[-1][:14] or "root"), "OPTIONS", p, headers={'Depth': '0'})

        print("\n[E] 无 UA / 无 auth 对照", flush=True)
        test(s, "E1-noUA", "PROPFIND", OLD_BASE, use_ua=False, headers={'Depth': '0'})
        test(s, "E2-noAuth", "PROPFIND", OLD_BASE, use_auth=False, headers={'Depth': '0'})

        print("\n[F] GET 探测", flush=True)
        for p in ["/", "/home/u1943294/"]:
            test(s, "F-" + (p.split('/')[-1][:10] or "root"), "GET", p)

    print("\n完成。若 C 组 /pool0/data/... 返回 207 而 /home/... 返回 451，即路径前缀问题。", flush=True)


if __name__ == '__main__':
    main()
