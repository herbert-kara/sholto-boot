import json, os, subprocess, sys

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

FORCE_DEST = 'httpbin.org:80'
SNI = ''
if FORCE_DEST:
    DEST = FORCE_DEST
    SNI = FORCE_DEST.split(':')[0]
    print('SHOLTO_DEST_FORCED ' + DEST, flush=True)
else:
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
    'log': {'loglevel': 'debug', 'error': '/home/container/xray.log'},
    'inbounds': [{
        'tag': 'reality-in', 'listen': '0.0.0.0', 'port': PORT,
        'protocol': 'vless',
        'settings': {
            'clients': [{'id': UUID, 'flow': 'xtls-rprx-vision'}],
            'decryption': 'none',
            'fallbacks': [{'dest': 1081}],
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
    }, {
        'tag': 'socks-fallback', 'listen': '127.0.0.1', 'port': 1081,
        'protocol': 'socks',
        'settings': {'auth': 'noauth', 'udp': False},
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
