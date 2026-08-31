# -*- coding: utf-8 -*-
"""小米智能存储（SmartStorage）NAS 客户端自动化公共库

封装完整链路：
  启动客户端(CDP 调试模式) → 等设备连接 → 拿 cgiToken →
  轮询日志拿动态代理端口(urlport/webdavport) → mTLS 双向认证 →
  LuCI API(filemgr/storage/mediacenter) / WebDAV(PROPFIND/MOVE)

关键结论（来之不易，勿改动）：
  * WebDAV 路径用 /pool0/data/...（不带 /home/u1943294 别名前缀，带前缀被 nginx 451）
  * LuCI filemgr 的 parent 用 /home/u1943294/pool0/data/...（带 alias 前缀）
  * 端口每次启动动态分配，localStorage 里的 cgiPort/webdavPort 是旧缓存不可用
  * WebDAV 需要 UA + Basic auth + mTLS 三件套；UA 从客户端真实模块解码（见 nas_ua_decode.js）

用法：
    from nas_common import SmartStorageSession
    s = SmartStorageSession()
    s.start()                  # 启动客户端并连接 CDP
    s.wait_device()            # 等设备连上，拿 cgiToken
    s.wait_ports()             # 轮询日志拿 urlport/webdavport
    s.fetch_webdav_creds()     # LuCI get_pool_info 动态拿 WebDAV 账号密码（不落盘）
    s.propfind(path, depth)    # WebDAV PROPFIND
    s.move(src, dst)           # WebDAV MOVE（同目录内改名）
    s.luci(path, body)         # LuCI API
    s.stop()                   # 关闭
"""
import os, sys, io, time, json, ssl, http.client, glob, re, socket, base64, urllib.parse
import subprocess, urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
# 依赖 websocket-client 包；若用独立 venv 运行，请确保已安装：
#   pip install websocket-client
try:
    import websocket
except ImportError:
    websocket = None

for k in ['ELECTRON_RUN_AS_NODE', 'NODE_OPTIONS']:
    os.environ.pop(k, None)

def _path(env, default):
    """环境变量优先，否则用 ~ 默认值（自动展开用户主目录）"""
    return os.path.expanduser(os.environ.get(env, default))

# ============ 环境常量（SmartStorage 客户端，按你的环境配置）============
# 可用环境变量覆盖：SMARTSTORAGE_EXE / SMARTSTORAGE_LOG_DIR / MINAS_CERT_DIR
EXE = _path("SMARTSTORAGE_EXE", "~/AppData/Local/Programs/SmartStorage/小米智能存储.exe")
ARGS = ["--remote-debugging-port=9223", "--remote-allow-origins=*",
        "--disable-gpu", "--disable-gpu-sandbox", "--use-angle=swiftshader", "--no-sandbox"]
LOG_DIR = _path("SMARTSTORAGE_LOG_DIR", "~/Documents/mijiaNas/log")
CERT_DIR = _path("MINAS_CERT_DIR", "~/AppData/Local/minasCert")
CDP_PORT = 9223
NAS_IP = "192.168.31.136"

# 客户端真实 UA（沙箱解码自客户端混淆模块，见 nas_ua_decode.js）
# 若版本升级/换机导致 451，重新跑 nas_ua_decode.js 解码新 UA
UA = os.environ.get("NAS_WEBDAV_UA", "MiNasClient/1.0.8 (pc app; TBHK-L096; Windows 10/11 10.0.26200 (x64); <DEVICE_UID>)")


def find_cert():
    """从 minasCert 目录找到 uid_did_cert.pem 与 private_key.pem（mTLS 客户端证书）"""
    if not os.path.isdir(CERT_DIR):
        raise FileNotFoundError(f"minasCert 目录不存在: {CERT_DIR}")
    cert = key = None
    for f in os.listdir(CERT_DIR):
        if f.endswith('_cert.pem') and 'ca' not in f.lower():
            cert = os.path.join(CERT_DIR, f)
        if 'private_key' in f.lower() or (f.endswith('.pem') and 'cert' not in f and 'ca' not in f):
            key = os.path.join(CERT_DIR, f)
    if not cert or not key:
        raise FileNotFoundError(f"minasCert 下未找到证书对: {os.listdir(CERT_DIR)}")
    return cert, key


def read_log_tail():
    """读最新 app-*.log 尾部（用于轮询动态端口）"""
    logs = glob.glob(os.path.join(LOG_DIR, 'app-*.log'))
    if not logs:
        return ''
    latest = max(logs, key=os.path.getmtime)
    with open(latest, 'rb') as f:
        return f.read()[-500000:].decode('utf-8', errors='replace')


class SmartStorageSession:
    def __init__(self, ua=UA):
        self.ua = ua
        self.proc = None
        self.ws = None
        self.msg_id = 0
        self.token = None
        self.urlport = None
        self.wdport = None
        self.ctx = None
        self.wd_user = None
        self.wd_pass = None
        self._b64 = None

    # ---------- 启动与连接 ----------
    def start(self, timeout_cdp=60):
        print("[1] 启动客户端...", flush=True)
        self.proc = subprocess.Popen([EXE] + ARGS, cwd=os.path.dirname(EXE))
        targets = self._wait_cdp(timeout_cdp)
        if not targets:
            raise RuntimeError("CDP 未就绪")
        page = next((t for t in targets if t.get('type') == 'page'), None)
        if not page:
            raise RuntimeError("未找到 page target")
        self.ws = websocket.create_connection(page['webSocketDebuggerUrl'], timeout=20,
            sslopt={"cert_reqs": ssl.CERT_NONE}, origin=f"http://127.0.0.1:{CDP_PORT}")
        print(f"[2] CDP OK pid={self.proc.pid}", flush=True)

    def _wait_cdp(self, timeout=60):
        for i in range(timeout):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json/list", timeout=2) as r:
                    return json.loads(r.read())
            except Exception:
                time.sleep(1)
        return None

    def _cmd(self, method, params=None, timeout=25):
        self.msg_id += 1
        self.ws.settimeout(timeout)
        self.ws.send(json.dumps({"id": self.msg_id, "method": method, "params": params or {}}))
        while True:
            resp = json.loads(self.ws.recv())
            if resp.get('id') == self.msg_id:
                return resp

    def js_eval(self, expr):
        r = self._cmd("Runtime.evaluate", {"expression": expr, "returnByValue": True})
        try:
            return r.get('result', {}).get('result', {}).get('value')
        except Exception:
            return None

    def wait_device(self, timeout_s=180):
        t0 = time.time()
        while time.time() - t0 < timeout_s:
            time.sleep(2)
            v = self.js_eval("(JSON.parse(localStorage.getItem('deviceInfo')||'{}')).cgiToken")
            if v:
                self.token = v
                print(f"[3] 设备已连 ({(time.time()-t0):.0f}s) token={v[:8]}...", flush=True)
                return v
        raise TimeoutError("等不到设备连接（检查 NAS 是否在线 / 客户端是否已登录）")

    # ---------- 动态端口 ----------
    def wait_ports(self, timeout_s=150):
        seen_w, seen_u = set(), set()
        t1 = time.time()
        while time.time() - t1 < timeout_s:
            data = read_log_tail()
            for m in re.findall(r'webdavport["=:](\d+)', data):
                if m not in seen_w: seen_w.add(m)
            for m in re.findall(r'urlport=(\d+)', data):
                if m not in seen_u: seen_u.add(m)
            for c in list(seen_w):
                if self._tcp_ok(c):
                    self.wdport = c; break
            if self.wdport:
                for c in list(seen_u):
                    if self._tcp_ok(c):
                        self.urlport = c; break
                if self.urlport:
                    break
            time.sleep(2)
        if not self.wdport:
            raise TimeoutError("WebDAV 端口不可用（日志: " + data[:200] + "）")
        print(f"[4] WebDAV端口={self.wdport} LuCI端口={self.urlport} ({time.time()-t1:.0f}s)", flush=True)
        self._init_ssl()
        return self.wdport, self.urlport

    def _tcp_ok(self, port, timeout=1.5):
        try:
            s = socket.create_connection(('127.0.0.1', int(port)), timeout=timeout)
            s.close()
            return True
        except Exception:
            return False

    def _init_ssl(self):
        cert, key = find_cert()
        self.ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE
        self.ctx.load_cert_chain(cert, key)

    # ---------- LuCI API ----------
    def luci(self, path, body=None, method='POST', timeout=20):
        """LuCI API：/cgi-bin/luci/{path}?accessToken={token}（mTLS，无需 UA 特判）"""
        if not self.urlport:
            raise RuntimeError("先 wait_ports()")
        conn = http.client.HTTPSConnection('127.0.0.1', int(self.urlport), timeout=timeout, context=self.ctx)
        url = f"/cgi-bin/luci/{path}?accessToken={self.token}"
        try:
            conn.request(method, url, body=json.dumps(body) if body is not None else None,
                         headers={'Content-Type': 'application/json', 'User-Agent': self.ua})
            resp = conn.getresponse()
            data = resp.read().decode('utf-8', errors='replace')
            conn.close()
            return resp.status, data
        except Exception as e:
            return None, 'EXC:' + str(e)[:200]

    def fetch_webdav_creds(self):
        """从 get_pool_info 动态获取 WebDAV 账号密码（不写盘、不进 skill）"""
        st, v = self.luci('filemgr/get_pool_info', {})
        if st != 200:
            raise RuntimeError(f"get_pool_info 失败 http={st}: {v[:200]}")
        info = json.loads(v)
        if info.get('code') != 0:
            raise RuntimeError(f"get_pool_info code={info.get('code')}: {v[:300]}")
        wd = info['data'].get('webDAV', {})
        self.wd_user = wd.get('username') or 'u' + str(info['data']['internal_pool'][0].get('uid', ''))
        self.wd_pass = wd.get('password')
        if not self.wd_pass:
            raise RuntimeError("get_pool_info 未返回 webDAV.password")
        self._b64 = base64.b64encode(f"{self.wd_user}:{self.wd_pass}".encode()).decode()
        print(f"[5] WebDAV 凭证已获取 user={self.wd_user}", flush=True)
        return self.wd_user, self.wd_pass

    # ---------- WebDAV ----------
    def dav(self, method, path, headers=None, body=None, timeout=40):
        if not self.wdport or not self.ctx:
            raise RuntimeError("先 wait_ports()")
        if not self._b64:
            raise RuntimeError("先 fetch_webdav_creds()")
        conn = http.client.HTTPSConnection('127.0.0.1', int(self.wdport), timeout=timeout, context=self.ctx)
        hdrs = {'Authorization': 'Basic ' + self._b64, 'User-Agent': self.ua,
                'Content-Type': 'application/octet-stream'}
        if headers: hdrs.update(headers)
        try:
            conn.request(method, urllib.parse.quote(path, safe="/"), body=body, headers=hdrs)
            resp = conn.getresponse()
            data = resp.read().decode('utf-8', errors='replace')
            conn.close()
            return resp.status, data
        except Exception as e:
            return None, 'EXC:' + str(e)[:200]

    def propfind(self, path, depth='1'):
        return self.dav("PROPFIND", path, {'Depth': depth})

    def dav_list(self, parent):
        """PROPFIND Depth=1 列目录，返回子项名列表。注意 XML 里是 <D:href>（大写 D）"""
        st, v = self.propfind(parent, '1')
        if st not in (207, 200):
            return None, f"http={st} {v[:120]}"
        base = parent.rstrip('/') + '/'
        parent_seg = parent.rstrip('/').split('/')[-1]
        names = []
        for h in re.findall(r'<[dD]:href>([^<]+)</[dD]:href>', v):
            u = urllib.parse.unquote(h).rstrip('/')
            if u == parent.rstrip('/'):
                continue
            if u.startswith(base):
                names.append(u[len(base):])
            else:
                seg = u.split('/')[-1] if u else ''
                if seg and seg != parent_seg:
                    names.append(seg)
        return names, None

    def move(self, src, dst):
        """WebDAV MOVE：同目录内改名（Dest 头必须是完整 URL）"""
        dest_url = f"https://127.0.0.1:{self.wdport}{urllib.parse.quote(dst, safe='/')}"
        return self.dav("MOVE", src, {'Destination': dest_url, 'Overwrite': 'T'})

    def stop(self):
        try:
            if self.ws:
                self.ws.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.stop()


if __name__ == '__main__':
    # 自测：启动→连上→拿凭证→列根目录
    with SmartStorageSession() as s:
        s.start()
        s.wait_device()
        s.wait_ports()
        s.fetch_webdav_creds()
        st, v = s.propfind("/pool0/data/", '1')
        print(f"\n根目录 PROPFIND: http={st}")
        names, err = s.dav_list("/pool0/data/")
        print("子目录:", names)
        print("OK 链路全通" if st in (207, 200) else f"FAIL: {err}")
