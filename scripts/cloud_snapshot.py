#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""雲端賠率快照（只用標準函式庫，方便喺 GitHub Actions / 任何雲端執行）
用法：python3 cloud_snapshot.py [YYYY/MM/DD] [ST|HV] [場數]
輸出：data/odds_snapshots/<YYYYMMDD>.jsonl（每次 append 一行）
"""
import html as _html, json, os, re, sys, time, datetime, urllib.request

UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36'
BASE = 'https://racing.hkjc.com'

def fetch(url, tries=3, timeout=25):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept-Language': 'zh-HK,zh;q=0.9'})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode('utf-8', 'replace')
        except Exception as e:
            if i == tries - 1:
                print('  fetch 失敗 %s：%s' % (url, e))
                return ''
            time.sleep(1.5 * (i + 1))
    return ''

def strip_tags(html):
    t = re.sub(r'<script.*?</script>', ' ', html, flags=re.S | re.I)
    t = re.sub(r'<style.*?</style>', ' ', t, flags=re.S | re.I)
    t = re.sub(r'<[^>]+>', '|', t)
    t = _html.unescape(t)
    t = re.sub(r'\|+', '|', t)
    return re.sub(r'\s+', ' ', t)

def tokens(html):
    t = strip_tags(html)
    return [x.strip() for x in t.split('|') if x.strip()]

def parse_race(html):
    """由 tips_index 頁解析 {馬名: 獨贏賠率} + {馬名: 貼士指數} + meta（純標準函式庫）"""
    if not html:
        return {}, {}, {}
    toks = tokens(html)
    HEAD = ['馬號', '馬名', '負磅', '練馬師', '騎師', '檔位', '獨贏賠率']
    start = None
    for i in range(len(toks) - len(HEAD)):
        if toks[i:i + len(HEAD)] == HEAD:
            start = i + len(HEAD)
            break
    odds, tips = {}, {}
    if start is not None:
        # 表頭之後每個馬：馬號 馬名 負磅 練馬師 騎師 檔位 賠率 [貼士1] [貼士2]
        i = start
        while i < len(toks):
            if not re.fullmatch(r'\d{1,2}', toks[i]):
                i += 1
                continue
            if i + 6 >= len(toks):
                break
            name = toks[i + 1]
            try:
                od = float(toks[i + 6])
            except Exception:
                i += 1
                continue
            if od > 0 and not re.fullmatch(r'\d{1,2}', name):
                odds[name] = od
                if i + 7 < len(toks):
                    try:
                        tips[name] = float(toks[i + 7])
                    except Exception:
                        pass
                i += 9
            else:
                i += 1
    t = strip_tags(html)
    meta = {}
    mm = re.search(r'(\d{1,2}/\d{1,2}/\d{4})\s*([^,|]+),\s*([\d:]+\s*[AP]M)', t)
    if mm:
        meta = {'date': mm.group(1), 'venue': mm.group(2).strip(), 'time': mm.group(3).strip()}
    return odds, tips, meta

def main():
    date = sys.argv[1] if len(sys.argv) > 1 else ''
    if date in ('', 'auto', 'AUTO'):
        date = None   # 由頁面自動偵測
    venue = sys.argv[2] if len(sys.argv) > 2 else ''
    nrace = int(sys.argv[3]) if len(sys.argv) > 3 else 11
    compact = (date[6:10]+date[3:5]+date[0:2]) if date else ''   # 07/10/2026 → 20261007
    os.makedirs('data/odds_snapshots', exist_ok=True)   # 先建立資料夾（即使冇賠率都唔會令 git add 失敗）
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))  # 香港時間
    allodds, alltips, races, metas = {}, {}, {}, {}
    if date is None:
        probe, _, pmeta = parse_race(fetch('%s/racing/Chinese/tipsindex/tips_index.asp?RaceNo=1' % BASE))
        if not pmeta.get('date'):
            print('未取得任何賠率（未公佈／已完賽）')
            return 0
        date = pmeta['date']
        compact = date.replace('/', '')
        print('自動偵測賽日：%s' % date)
    for n in range(1, nrace + 1):
        html = fetch('%s/racing/Chinese/tipsindex/tips_index.asp?RaceNo=%d' % (BASE, n))
        od, tp, meta = parse_race(html)
        if not od:
            continue
        races[str(n)] = len(od)
        if meta: metas[str(n)] = meta
        for k, v in od.items(): allodds['%d|%s' % (n, k)] = v
        for k, v in tp.items(): alltips['%d|%s' % (n, k)] = v
    if not allodds:
        print('[%s] 未取得任何賠率（未公佈／已完賽）' % now.strftime('%H:%M'))
        return 0
    # 賽日核對：避免抓到舊賽事嘅殘留頁面
    want = '%02d/%02d/%04d' % (int(date.split('/')[2]), int(date.split('/')[1]), int(date.split('/')[0]))
    page_date = (metas.get('1') or {}).get('date') or ''
    if page_date and page_date != want:
        print('[%s] 頁面賽日為 %s，非指定 %s → 跳過' % (now.strftime('%H:%M'), page_date, want))
        return 0
    rec = {'ts': now.isoformat(timespec='seconds'), 'hhmm': now.strftime('%H%M'),
           'date': date, 'venue': venue, 'odds': allodds, 'tips': alltips, 'races': races}
    os.makedirs('data/odds_snapshots', exist_ok=True)
    path = 'data/odds_snapshots/%s.jsonl' % compact
    prev = None
    if os.path.exists(path):
        for line in open(path, encoding='utf-8'):
            try: prev = json.loads(line)
            except Exception: pass
    if prev and prev.get('odds') == allodds:
        print('[%s] 賠率無變（%d 匹），略過' % (now.strftime('%H:%M'), len(allodds)))
    else:
        with open(path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
        print('[%s] 已記錄 %d 匹／%d 場' % (now.strftime('%H:%M'), len(allodds), len(races)))
    # ── 警示偵測：短時間內大幅變動 ──
    try:
        if prev and prev.get('odds'):
            import datetime as _dt
            def _mins(a, b):
                return (int(b[:2])*60+int(b[2:])) - (int(a[:2])*60+int(a[2:]))
            dt = _mins(prev.get('hhmm','0000'), rec['hhmm'])
            if 0 < dt <= 15:
                ov, nv = prev['odds'], allodds
                keys = [k for k in nv if k in ov and ov[k] > 1]
                if keys:
                    def share(d, k):
                        tot = sum(1/v for v in d.values() if v > 1)
                        return (1/d[k])/tot if tot else 0
                    tot0 = sum(1/ov[k] for k in keys); tot1 = sum(1/nv[k] for k in keys)
                    al = []
                    for k in keys:
                        d0 = (1/ov[k])/tot0 if tot0 else 0
                        d1 = (1/nv[k])/tot1 if tot1 else 0
                        pay = d1 - d0                      # 彩池佔比變化
                        if abs(pay) >= 0.03:               # 3% 彩池 = 大幅
                            al.append({'race': int(k.split('|')[0]), 'horse': k.split('|')[1],
                                       'from': ov[k], 'to': nv[k], 'pool_pct': round(100*pay, 2),
                                       'mins': dt, 'hhmm': rec['hhmm']})
                    if al:
                        al.sort(key=lambda z: -abs(z['pool_pct']))
                        os.makedirs('data/alerts', exist_ok=True)
                        ap = 'data/alerts/%s.jsonl' % compact
                        with open(ap, 'a', encoding='utf-8') as f:
                            for a in al:
                                f.write(json.dumps({**a, 'ts': rec['ts']}, ensure_ascii=False) + '\n')
                        print('  ⚠️ 警示 %d 條：%s' % (len(al), ', '.join(
                            'R%d %s %+.1f%%彩池' % (a['race'], a['horse'], a['pool_pct']) for a in al[:3])))
    except Exception as e:
        print('  警示偵測失敗：%s' % e)
    if prev and prev.get('odds'):
        mv = []
        for k, v in allodds.items():
            p = prev['odds'].get(k)
            if p and v and p > 0: mv.append((v / p, k, p, v))
        if mv:
            mv.sort()
            print('  最大落飛：', ['%s %.1f→%.1f' % (m[1].split('|')[1], m[2], m[3]) for m in mv[:3]])
            print('  最大退飛：', ['%s %.1f→%.1f' % (m[1].split('|')[1], m[2], m[3]) for m in mv[-3:][::-1]])
    return 0

if __name__ == '__main__':
    sys.exit(main())
