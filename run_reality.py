import json, os, subprocess, sys

PORT = int(os.environ.get('SERVER_PORT') or os.environ.get('PORT') or 8080)
USER = 'sholto'
PASS = '4U28pIQR7pJP'
UUID = 'bb2af336-0603-48dc-af5b-7f3c373a6045'
PRIV = 'qLUQneeQN6Tgov7gbvclvSAEscdCetsklGwyrmaYhEU'
PUB = 'Z6i5Vd5mrs_TfL347gCkDXCNlUtda8Q3XK_GfBXkmXE'
SID = '13ade039'
DEST = 'www.apple.com:443'
SNI = 'www.apple.com'
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
