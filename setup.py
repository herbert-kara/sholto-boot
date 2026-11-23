"""Bootstrap payload: installs nothing, writes the real server file into the container."""
import os
from setuptools import setup

APP = r'''
import os, sys, json, socket, time, http.server, socketserver

PORT = int(os.environ.get('SERVER_PORT') or os.environ.get('PORT') or 8080)
ROOT = '/home/container'

class H(http.server.BaseHTTPRequestHandler):
    def _send(self, code, body):
        body = body if isinstance(body, bytes) else body.encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        try:
            files = sorted(os.listdir(ROOT))
        except Exception as e:
            files = ['ERR:' + str(e)]
        payload = {
            'marker': 'SHOLTO_V1_OK',
            'host': socket.gethostname(),
            'cwd': os.getcwd(),
            'argv': sys.argv,
            'py': sys.version.split()[0],
            'pid': os.getpid(),
            'port': PORT,
            'path': self.path,
            'files': files[:60],
            'env_server_port': os.environ.get('SERVER_PORT'),
            'time': time.time(),
        }
        self._send(200, json.dumps(payload))

    def log_message(self, fmt, *args):
        print('REQ', self.address_string(), fmt % args, flush=True)


print('SHOLTO_V1_START port=%d cwd=%s' % (PORT, os.getcwd()), flush=True)
socketserver.TCPServer.allow_reuse_address = True
socketserver.ThreadingTCPServer.allow_reuse_address = True
srv = http.server.ThreadingHTTPServer(('0.0.0.0', PORT), H)
print('SHOLTO_V1_LISTENING %s:%d' % (socket.gethostname(), PORT), flush=True)
srv.serve_forever()
'''

WRITE_FAIL = None
try:
    with open('/home/container/app_real.py', 'w') as fh:
        fh.write(APP)
except Exception as e:  # pragma: no cover
    WRITE_FAIL = repr(e)
    print('BOOT_WRITE_FAIL', WRITE_FAIL, flush=True)

try:
    with open('/home/container/BOOT_NOTE.txt', 'w') as fh:
        fh.write('bootstrap ran as %s cwd=%s\n' % (os.getuid(), os.getcwd()))
except Exception as e:
    print('BOOT_NOTE_FAIL', repr(e), flush=True)

print('BOOT_WROTE_APP len=%d fail=%s' % (len(APP), WRITE_FAIL), flush=True)

setup(
    name='nodaroo-boot',
    version='0.0.1',
    description='bootstrap',
    py_modules=[],
    packages=[],
)
