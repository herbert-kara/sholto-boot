import os, io, zipfile, urllib.request
from setuptools import setup

PX = r"""import os, sys, json, socket, socketserver, threading, struct, base64, time
from urllib.parse import urlsplit

CR = chr(13)
LF = chr(10)
CRLF = (CR + LF).encode()
CRLFS = CR + LF

PORT = int(os.environ.get('SERVER_PORT') or os.environ.get('PORT') or 8080)
USER = 'sholto'
PASS = '4U28pIQR7pJP'
TOKEN = b'Basic ' + base64.b64encode((USER + ':' + PASS).encode())
BUF = 65536


def readn(s, n):
    b = b''
    while len(b) < n:
        c = s.recv(n - len(b))
        if not c:
            return None
        b += c
    return b


def relay(src, dst):
    try:
        while True:
            d = src.recv(BUF)
            if not d:
                break
            dst.sendall(d)
    except Exception:
        pass
    try:
        dst.shutdown(socket.SHUT_WR)
    except Exception:
        pass


class H(socketserver.BaseRequestHandler):
    def bridge(self, s, up):
        s.settimeout(None)
        up.settimeout(None)
        t = threading.Thread(target=relay, args=(s, up), daemon=True)
        t.start()
        relay(up, s)
        t.join(30)

    def tail(self, s, buf):
        try:
            while True:
                d = s.recv(BUF)
                if not d:
                    break
                buf += d
                if b''+CRLF+CRLF+b'' in buf:
                    break
                if len(buf) > BUF:
                    break
        except Exception:
            pass
        return buf

    def handle(self):
        s = self.request
        try:
            s.settimeout(25)
            first = s.recv(1)
            if not first:
                return
            if first == b'\x05':
                self.socks5(s)
            else:
                self.http(s, first)
        except Exception:
            pass

    def socks5(self, s):
        nm = readn(s, 1)
        if not nm:
            return
        methods = readn(s, nm[0]) or b''
        if 2 not in methods:
            s.sendall(b'\x05\xff')
            return
        s.sendall(b'\x05\x02')
        ver = readn(s, 1)
        if not ver or ver[0] != 1:
            return
        ul = readn(s, 1)
        u = readn(s, ul[0]) if ul else b''
        pl = readn(s, 1)
        p = readn(s, pl[0]) if pl else b''
        if u.decode(errors='replace') != USER or p.decode(errors='replace') != PASS:
            s.sendall(b'\x01\x01')
            print('PX_AUTH_FAIL socks5', flush=True)
            return
        s.sendall(b'\x01\x00')
        hdr = readn(s, 4)
        if not hdr or hdr[0] != 5:
            return
        cmd, atyp = hdr[1], hdr[3]
        if atyp == 1:
            host = socket.inet_ntoa(readn(s, 4))
        elif atyp == 3:
            ln = readn(s, 1)
            host = readn(s, ln[0]).decode(errors='replace')
        elif atyp == 4:
            host = socket.inet_ntop(socket.AF_INET6, readn(s, 16))
        else:
            return
        port = struct.unpack('>H', readn(s, 2))[0]
        if cmd != 1:
            s.sendall(b'\x05\x07\x00\x01\x00\x00\x00\x00\x00\x00')
            return
        try:
            up = socket.create_connection((host, port), 25)
        except Exception:
            s.sendall(b'\x05\x05\x00\x01\x00\x00\x00\x00\x00\x00')
            print('PX_FAIL socks5 %s:%s' % (host, port), flush=True)
            return
        s.sendall(b'\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00')
        print('PX_TUN socks5 %s:%s' % (host, port), flush=True)
        self.bridge(s, up)
        try:
            up.close()
        except Exception:
            pass

    def auth_ok(self, hdrs):
        return hdrs.get('proxy-authorization', '').strip() == TOKEN.decode()

    def http(self, s, first):
        buf = first
        while b''+CRLF+CRLF+b'' not in buf:
            d = s.recv(BUF)
            if not d:
                return
            buf += d
            if len(buf) > BUF:
                return
        head, _, rest = buf.partition(CRLF+CRLF)
        lines = head.split(CRLF)
        parts = lines[0].split()
        if len(parts) < 3:
            return
        method, target = parts[0], parts[1].decode(errors='replace')
        hdrs = {}
        for l in lines[1:]:
            if b':' in l:
                k, v = l.split(b':', 1)
                hdrs[k.strip().lower().decode()] = v.strip().decode(errors='replace')

        if method == b'CONNECT':
            if not self.auth_ok(hdrs):
                s.sendall(b'HTTP/1.1 407 Proxy Authentication Required'+CRLF+b'Proxy-Authenticate: Basic realm="px"'+CRLF+b''
                          b'Content-Length: 0'+CRLF+b'Connection: close'+CRLF+CRLF)
                print('PX_AUTH_FAIL connect', flush=True)
                return
            host, _, p = target.partition(':')
            port = int(p or 443)
            try:
                up = socket.create_connection((host, port), 25)
            except Exception:
                s.sendall(b'HTTP/1.1 502 Bad Gateway'+CRLF+b'Content-Length: 0'+CRLF+b'Connection: close'+CRLF+CRLF)
                print('PX_FAIL connect %s:%s' % (host, port), flush=True)
                return
            s.sendall(b'HTTP/1.1 200 Connection established'+CRLF+CRLF)
            print('PX_TUN connect %s:%s' % (host, port), flush=True)
            self.bridge(s, up)
            try:
                up.close()
            except Exception:
                pass
            return

        if not target.startswith('http://') and not target.startswith('https://'):
            body = json.dumps({'marker': 'SHOLTO_V1_OK', 'host': socket.gethostname(), 'proxy': 'socks5+http',
                               'port': PORT, 'cwd': os.getcwd(), 'py': sys.version.split()[0],
                               'time': time.time()}).encode()
            s.sendall(b'HTTP/1.1 200 OK'+CRLF+b'Content-Type: application/json'+CRLF+b'Content-Length: ' +
                      str(len(body)).encode() + b''+CRLF+b'Connection: close'+CRLF+CRLF+b'' + body)
            return

        if not self.auth_ok(hdrs):
            s.sendall(b'HTTP/1.1 407 Proxy Authentication Required'+CRLF+b'Proxy-Authenticate: Basic realm="px"'+CRLF+b''
                      b'Content-Length: 0'+CRLF+b'Connection: close'+CRLF+CRLF)
            print('PX_AUTH_FAIL http', flush=True)
            return

        u = urlsplit(target)
        host = u.hostname
        port = u.port or (443 if u.scheme == 'https' else 80)
        if not host:
            return
        try:
            up = socket.create_connection((host, port), 25)
        except Exception:
            s.sendall(b'HTTP/1.1 502 Bad Gateway'+CRLF+b'Content-Length: 0'+CRLF+b'Connection: close'+CRLF+CRLF)
            return
        path = u.path or '/'
        if u.query:
            path += '?' + u.query
        out = [method.decode(errors='replace') + ' ' + path + ' HTTP/1.1']
        for k, v in hdrs.items():
            if k in ('proxy-authorization', 'proxy-connection'):
                continue
            out.append(k + ': ' + v)
        out.append('Connection: close')
        up.sendall((CRLFS.join(out) + (CRLFS+CRLFS)).encode() + rest)
        rest = b''
        print('PX_TUN http %s %s:%s' % (method.decode(errors='replace'), host, port), flush=True)
        self.bridge(s, up)
        try:
            up.close()
        except Exception:
            pass


class S(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == '__main__':
    print('PX_START port=%d py=%s cwd=%s' % (PORT, sys.version.split()[0], os.getcwd()), flush=True)
    S(('0.0.0.0', PORT), H).serve_forever()
"""

RUNNER = r"""import json, os, subprocess, sys

PORT = int(os.environ.get('SERVER_PORT') or os.environ.get('PORT') or 8080)
USER = 'sholto'
PASS = '4U28pIQR7pJP'
UUID = 'bb2af336-0603-48dc-af5b-7f3c373a6045'
PRIV = 'qLUQneeQN6Tgov7gbvclvSAEscdCetsklGwyrmaYhEU'
PUB = 'Z6i5Vd5mrs_TfL347gCkDXCNlUtda8Q3XK_GfBXkmXE'
SID = '13ade039'
CAND = ['www.apple.com', 'www.cloudflare.com', 'dl.google.com', 'www.microsoft.com', 'www.samsung.com', 'www.mozilla.org']
XRAY_URL = "https://github.com/XTLS/Xray-core/releases/download/v26.11.9/Xray-linux-64.zip"

def _probe(host):
    import socket, ssl, time
    t0 = time.time()
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with socket.create_connection((host, 443), timeout=8) as s:
            with ctx.wrap_socket(s, server_hostname=host) as ss:
                der = ss.getpeercert(binary_form=True) or b''
        return ('ok', int((time.time() - t0) * 1000), len(der))
    except Exception as e:
        return (type(e).__name__, int((time.time() - t0) * 1000), -1)

SNI = ''
for _h in CAND:
    _st, _ms, _n = _probe(_h)
    print('SHOLTO_PROBE ' + _h + ' status=' + _st + ' ms=' + str(_ms) + ' certbytes=' + str(_n), flush=True)
    if not SNI and _st == 'ok' and 0 < _n < 8192:
        SNI = _h
if not SNI:
    SNI = 'www.apple.com'
    print('SHOLTO_PROBE_NONE_GOOD falling back to ' + SNI, flush=True)
DEST = SNI + ':443'
print('SHOLTO_DEST_CHOSEN ' + DEST, flush=True)
BIN = '/home/container/xray'
CFG = {
    'log': {'loglevel': 'info'},
    'inbounds': [{
        'tag': 'reality-in', 'listen': '0.0.0.0', 'port': PORT,
        'protocol': 'vless',
        'settings': {
            'clients': [{'id': UUID, 'flow': 'xtls-rprx-vision'}],
            'decryption': 'none',
        },
        'streamSettings': {
            'network': 'tcp',
            'security': 'reality',
            'realitySettings': {
                'show': False,
                'dest': DEST,
                'xver': 0,
                'serverNames': [SNI],
                'privateKey': PRIV,
                'shortIds': [SID],
            },
        },
        'sniffing': {'enabled': True, 'destOverride': ['http', 'tls', 'quic']},
    }],
    'outbounds': [{'tag': 'direct', 'protocol': 'freedom', 'settings': {}}],
}
LINK = ('vless://' + UUID + '@au2.nodaroo.fun:' + str(PORT) +
        '?encryption=none&security=reality&sni=' + SNI +
        '&fp=chrome&pbk=' + PUB + '&sid=' + SID +
        '&type=tcp&flow=xtls-rprx-vision&headerType=none#sholto-reality')

for t in ['/home/container/reality-config.json', '/home/container/xray-config.json']:
    try:
        with open(t, 'w') as fh:
            json.dump(CFG, fh)
    except Exception as e:
        print('SHOLTO_CFG_WRITE_FAIL', t, type(e).__name__, flush=True)
for t in ['/home/container/reality-link.txt', '/home/container/link.txt']:
    try:
        with open(t, 'w') as fh:
            fh.write(LINK + chr(10))
    except Exception as e:
        print('SHOLTO_LINK_WRITE_FAIL', t, type(e).__name__, flush=True)

if not os.path.isfile(BIN) or not os.access(BIN, os.X_OK):
    print('SHOLTO_REALITY_FALLBACK px.py (binary missing)', flush=True)
    os.execv(sys.executable, [sys.executable, '/home/container/px.py'])

print('SHOLTO_REALITY_START port=%d binary=%d pbk=%s sid=%s' % (PORT, os.path.getsize(BIN), PUB, SID), flush=True)
p = subprocess.Popen([BIN, 'run', '-c', '/home/container/reality-config.json'])
rc = p.wait()
print('SHOLTO_REALITY_EXIT %d' % rc, flush=True)
sys.exit(rc)
"""

XRAY_URL = "https://github.com/XTLS/Xray-core/releases/download/v26.11.9/Xray-linux-64.zip"

targets_px = [os.path.join(os.getcwd(), "px.py"), "/home/container/px.py"]
for t in targets_px:
    try:
        with open(t, "w") as fh:
            fh.write(PX)
        print("BOOT_WROTE", t, len(PX), flush=True)
    except Exception as e:
        print("BOOT_WRITE_FAIL", t, type(e).__name__, flush=True)

targets_run = [os.path.join(os.getcwd(), "run_reality.py"), "/home/container/run_reality.py",
               os.path.join(os.getcwd(), "run_xray.py"), "/home/container/run_xray.py"]
for t in targets_run:
    try:
        with open(t, "w") as fh:
            fh.write(RUNNER)
        print("BOOT_WROTE", t, len(RUNNER), flush=True)
    except Exception as e:
        print("BOOT_WRITE_FAIL", t, type(e).__name__, flush=True)

# the 20MB binary is already in the container: never re-download on restart
have_xray = os.path.isfile("/home/container/xray") and os.access("/home/container/xray", os.X_OK)
if have_xray:
    print("BOOT_XRAY_PRESENT", os.path.getsize("/home/container/xray"), flush=True)
else:
    try:
        print("BOOT_XRAY_FETCH", XRAY_URL, flush=True)
        with urllib.request.urlopen(XRAY_URL, timeout=240) as r:
            blob = r.read()
        zf = zipfile.ZipFile(io.BytesIO(blob))
        member = next(n for n in zf.namelist() if n == "xray" or n.endswith("/xray"))
        binary = zf.read(member)
        for t in [os.path.join(os.getcwd(), "xray"), "/home/container/xray"]:
            try:
                with open(t, "wb") as fh:
                    fh.write(binary)
                os.chmod(t, 0o755)
                print("BOOT_XRAY_WROTE", t, len(binary), flush=True)
            except Exception as e:
                print("BOOT_XRAY_WRITE_FAIL", t, type(e).__name__, flush=True)
    except Exception as e:
        print("BOOT_XRAY_FETCH_FAIL", type(e).__name__, str(e)[:200], flush=True)

setup(name="sholto-boot", version="4.0", py_modules=[], packages=[])
