#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""極簡 WebSocket (RFC6455) + STOMP 客戶端 —— 只靠標準函式庫
用途：連接 HKJC 賠率推送服務 wss://ueb.hkjc.com:52443/ 並訂閱彩池
"""
import base64, json, os, socket, ssl, struct, sys, time, threading

def ws_connect(host, port, path='/', origin=None, timeout=15, extra=None):
    raw = socket.create_connection((host, port), timeout=timeout)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    s = ctx.wrap_socket(raw, server_hostname=host)
    key = base64.b64encode(os.urandom(16)).decode()
    hdr = ['GET %s HTTP/1.1' % path, 'Host: %s:%d' % (host, port), 'Upgrade: websocket',
           'Connection: Upgrade', 'Sec-WebSocket-Key: %s' % key, 'Sec-WebSocket-Version: 13']
    if origin: hdr.append('Origin: %s' % origin)
    hdr.append('User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36')
    if extra: hdr += extra
    s.sendall(('\r\n'.join(hdr) + '\r\n\r\n').encode())
    resp = b''
    while b'\r\n\r\n' not in resp:
        c = s.recv(4096)
        if not c: raise IOError('握手失敗（連線關閉）')
        resp += c
    line = resp.split(b'\r\n')[0].decode('utf-8', 'replace')
    if '101' not in line: raise IOError('握手失敗：%s' % line)
    return s, resp.split(b'\r\n\r\n', 1)[1]

def ws_send(s, data, opcode=1):
    if isinstance(data, str): data = data.encode('utf-8')
    hdr = bytes([0x80 | opcode]); n = len(data); mask = os.urandom(4)
    if n < 126: hdr += bytes([0x80 | n])
    elif n < 65536: hdr += bytes([0x80 | 126]) + struct.pack('>H', n)
    else: hdr += bytes([0x80 | 127]) + struct.pack('>Q', n)
    s.sendall(hdr + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

def _read(s, n):
    buf = b''
    while len(buf) < n:
        c = s.recv(n - len(buf))
        if not c: raise IOError('連線關閉')
        buf += c
    return buf

def ws_recv(s):
    b1, b2 = _read(s, 2)
    op = b1 & 0x0F; n = b2 & 0x7F
    if n == 126: n = struct.unpack('>H', _read(s, 2))[0]
    elif n == 127: n = struct.unpack('>Q', _read(s, 8))[0]
    mask = _read(s, 4) if (b2 & 0x80) else None
    d = _read(s, n) if n else b''
    if mask: d = bytes(b ^ mask[i % 4] for i, b in enumerate(d))
    return op, d

def stomp_connect(s, host='ueb.hkjc.com', login=None, passcode=None):
    lines = ['CONNECT', 'accept-version:1.0,1.1,1.2', 'heart-beat:0,0', 'host:%s' % host]
    if login:
        lines += ['login:%s' % login, 'passcode:%s' % passcode]
    ws_send(s, '\n'.join(lines) + '\n\n\0')
    for _ in range(12):
        op, d = ws_recv(s)
        txt = d.decode('utf-8', 'replace').replace('\0', '')
        if txt.startswith('CONNECTED'): return True, txt
        if txt.startswith('ERROR'): return False, txt
    return False, '冇回應'

def stomp_sub(s, dest, subid='sub-0'):
    ws_send(s, 'SUBSCRIBE\nid:%s\ndestination:%s\n\n\0' % (subid, dest))

if __name__ == '__main__':
    host = 'ueb.hkjc.com'
    for port, path, origin in [(52443, '/', 'https://bet.hkjc.com'),
                               (52443, '/', None),
                               (443, '/', 'https://bet.hkjc.com')]:
        print('══ 測試 port=%s path=%s origin=%s' % (port, path, origin))
        try:
            s, leftover = ws_connect(host, port, path, origin=origin)
            print('   ✅ WebSocket 握手成功')
            ok, msg = stomp_connect(s)
            print('   STOMP：%s' % msg.replace('\n', ' | ')[:150])
            if ok:
                for pool in ['win', 'pla', 'qin', 'qpl']:
                    stomp_sub(s, 'hk/d/prdt/wager/evt/01/upd/racing/20261007/HV/1/%s/odds/full' % pool, 'sub-%s' % pool)
                    print('   已訂閱 %s' % pool)
                s.settimeout(8)
                try:
                    for i in range(5):
                        op, d = ws_recv(s)
                        print('   ← [%d] %s' % (i, d.decode('utf-8', 'replace').replace('\0', '').replace('\n', ' | ')[:200]))
                except socket.timeout:
                    print('   （8 秒內冇推送訊息 —— 賠率未公佈時正常）')
                s.close()
                sys.exit(0)
            s.close()
        except Exception as e:
            print('   ❌ %s' % e)
