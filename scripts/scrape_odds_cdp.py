#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用 Chrome DevTools Protocol 抓取 HKJC 多個彩池賠率（獨贏/位置/連贏/位置Q）
只用標準函式庫 + 系統 Chrome
用法：python3 scrape_odds_cdp.py 2026-10-07 HV [場數]
"""
import base64, json, os, socket, struct, subprocess, sys, time, urllib.request, importlib.util, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('w', os.path.join(HERE, 'hkjc_ws.py'))
W = importlib.util.module_from_spec(spec); spec.loader.exec_module(W)

def find_chrome():
    cands = [os.environ.get('CHROME_PATH'),
             "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
             "/Applications/Chromium.app/Contents/MacOS/Chromium",
             "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable",
             "/usr/bin/chromium", "/usr/bin/chromium-browser",
             "/snap/bin/chromium", "/opt/google/chrome/chrome"]
    for c in cands:
        if c and os.path.exists(c): return c
    import shutil
    for n in ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser', 'chrome'):
        f = shutil.which(n)
        if f: return f
    return "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
CHROME = find_chrome()
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36'

def plain_ws(host, port, path):
    raw = socket.create_connection((host, port), timeout=20)
    key = base64.b64encode(os.urandom(16)).decode()
    hdr = ['GET %s HTTP/1.1' % path, 'Host: %s:%d' % (host, port), 'Upgrade: websocket',
           'Connection: Upgrade', 'Sec-WebSocket-Key: %s' % key, 'Sec-WebSocket-Version: 13']
    raw.sendall(('\r\n'.join(hdr) + '\r\n\r\n').encode())
    buf = b''
    while b'\r\n\r\n' not in buf:
        c = raw.recv(4096)
        if not c: raise IOError('CDP 握手失敗')
        buf += c
    if b'101' not in buf.split(b'\r\n')[0]: raise IOError('CDP 握手失敗：%s' % buf[:80])
    return raw

class CDP:
    def __init__(self, port=9333):
        flags = [CHROME, '--headless=new', '--disable-gpu', '--no-sandbox', '--disable-dev-shm-usage',
                 '--disable-software-rasterizer', '--no-first-run', '--no-default-browser-check',
                 '--disable-extensions', '--mute-audio',
                 '--remote-debugging-port=%d' % port, '--remote-allow-origins=*',
                 '--user-data-dir=%s' % tempfile.mkdtemp(), 'about:blank']
        self.proc = subprocess.Popen(flags,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(20):
            time.sleep(1)
            try:
                tabs = json.load(urllib.request.urlopen('http://localhost:%d/json/list' % port, timeout=4))
                page = [t for t in tabs if t['type'] == 'page'][0]
                rest = page['webSocketDebuggerUrl'].replace('ws://', '')
                hostport, path = rest.split('/', 1)
                host, p = hostport.split(':')
                self.ws = plain_ws(host, int(p), '/' + path)
                self.id = 0
                self.send('Page.enable'); self.send('Network.enable')
                return
            except Exception:
                continue
        raise IOError('無法連接 Chrome CDP')
    def send(self, method, **params):
        self.id += 1
        W.ws_send(self.ws, json.dumps({'id': self.id, 'method': method, 'params': params}))
        return self.id
    def call(self, method, timeout=30, **params):
        i = self.send(method, **params)
        t0 = time.time(); self.ws.settimeout(2)
        while time.time() - t0 < timeout:
            try: op, d = W.ws_recv(self.ws)
            except socket.timeout: continue
            except Exception: return None
            if op != 1: continue
            try: m = json.loads(d)
            except Exception: continue
            if m.get('id') == i: return m.get('result')
        return None
    def goto(self, url, wait=4.0):
        self.call('Page.navigate', url=url, timeout=25)
        time.sleep(wait)
    def js(self, expr, timeout=25):
        r = self.call('Runtime.evaluate', timeout=timeout, expression=expr, returnByValue=True, awaitPromise=True)
        try: return r['result']['value']
        except Exception: return None
    def close(self):
        try: self.proc.terminate()
        except Exception: pass

# 喺頁面內抽取獨贏/位置表
JS_WP = r"""
(() => {
  const out=[];
  document.querySelectorAll('table').forEach(tb=>{
    const rows=[...tb.querySelectorAll('tr')];
    if(!rows.length) return;
    const head=[...rows[0].querySelectorAll('th,td')].map(c=>c.textContent.trim());
    if(!(head.includes('馬名') && head.includes('獨贏'))) return;
    const iNo=head.indexOf('馬號'), iNm=head.indexOf('馬名'), iW=head.indexOf('獨贏'), iP=head.indexOf('位置');
    rows.slice(1).forEach(r=>{
      const c=[...r.querySelectorAll('td,th')].map(x=>x.textContent.trim());
      if(c.length<=iNm) return;
      const num=(c[iNo]||'').match(/\d+/); if(!num) return;
      const f=v=>{const m=(v||'').match(/\d+(\.\d+)?/); return m?parseFloat(m[0]):null};
      out.push({no:parseInt(num[0]), name:c[iNm], win:f(c[iW]), place:f(c[iP])});
    });
  });
  return JSON.stringify(out);
})()
"""
# 連贏 / 位置Q 矩陣
JS_WPQ = r"""
(() => {
  const res={qin:{},qpl:{}};
  document.querySelectorAll('table').forEach(tb=>{
    const txt=(tb.textContent||'').replace(/\s+/g,' ').trim();
    let key=null;
    if(txt.startsWith('賠率連贏')||txt.startsWith('連贏')) key='qin';
    else if(txt.startsWith('位置Q')) key='qpl';
    if(!key) return;
    const rows=[...tb.querySelectorAll('tr')];
    const head=[...rows[0].querySelectorAll('th,td')].map(c=>c.textContent.trim());
    rows.slice(1).forEach(r=>{
      const c=[...r.querySelectorAll('td,th')].map(x=>x.textContent.trim());
      const rn=parseInt(c[0]||''); if(!rn) return;
      for(let j=1;j<head.length;j++){
        const o=parseFloat(c[j]||''); const cn=parseInt(head[j]||'');
        if(o>0 && cn) res[key][rn+'-'+cn]=o;
      }
    });
  });
  return JSON.stringify(res);
})()
"""

def main():
    date = sys.argv[1] if len(sys.argv) > 1 else '2026-10-07'
    venue = sys.argv[2] if len(sys.argv) > 2 else 'HV'
    nrace = int(sys.argv[3]) if len(sys.argv) > 3 else 11
    c = CDP()
    try:
        allruns = {}
        for n in range(1, nrace + 1):
            c.goto('https://bet.hkjc.com/ch/racing/wp/%s/%s/%d' % (date, venue, n))
            wp = c.js(JS_WP)
            rows = json.loads(wp) if wp else []
            if not rows or all(r['win'] is None for r in rows):
                print('  R%-2d 未公佈（或仍載入中）' % n); continue
            c.goto('https://bet.hkjc.com/ch/racing/wpq/%s/%s/%d' % (date, venue, n))
            m = c.js(JS_WPQ)
            mat = json.loads(m) if m else {}
            allruns[str(n)] = {'runners': rows, 'qin': mat.get('qin', {}), 'qpl': mat.get('qpl', {})}
            print('  R%-2d %2d 匹｜獨贏/位置 ✓｜連贏 %d 組、位置Q %d 組' %
                  (n, len(rows), len(mat.get('qin', {})), len(mat.get('qpl', {}))))
        if not allruns:
            print('未取得任何賠率（可能未公佈）'); return
        import datetime
        now = datetime.datetime.now()
        rec = {'ts': now.isoformat(timespec='seconds'), 'hhmm': now.strftime('%H%M'),
               'date': date, 'venue': venue, 'runs': allruns}
        # 同時產生獨贏 odds（兼容現有 viewer）
        rec['odds'] = {'%s|%s' % (rn, r['name']): r['win']
                       for rn, d in allruns.items() for r in d['runners'] if r['win']}
        os.makedirs('data/odds_snapshots', exist_ok=True)
        key = date.replace('-', '')
        path = 'data/odds_snapshots/%s.jsonl' % key
        with open(path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        print('已寫入 %s（%d 匹馬）' % (path, len(rec['odds'])))
    finally:
        c.close()

if __name__ == '__main__':
    main()
