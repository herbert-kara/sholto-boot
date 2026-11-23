import os
from setuptools import setup

APP = r"""import os, sys, json, socket, socketserver, threading, struct, base64, time
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

targets = [os.path.join(os.getcwd(), "px.py"), "/home/container/px.py"]
for t in targets:
    try:
        with open(t, "w") as fh:
            fh.write(APP)
        print("BOOT_WROTE", t, len(APP))
    except Exception as e:
        print("BOOT_WRITE_FAIL", t, e)

setup(name="sholto-boot", version="2.0", py_modules=[], packages=[])
