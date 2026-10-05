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
    compact = date.replace('/', '') if date else ''
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
