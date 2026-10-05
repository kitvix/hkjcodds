#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分析已收集嘅快照：落飛／退飛幅度 → 勝出率、平注回報（需賽果）
   賽果可放 data/results/<YYYYMMDD>.json（{馬名: 名次}）或留空只出賠率走勢統計
"""
import json, os, glob, sys, collections

def load_snaps(path):
    out = []
    for line in open(path, encoding='utf-8'):
        try: out.append(json.loads(line))
        except Exception: pass
    return out

def main():
    files = sorted(glob.glob('data/odds_snapshots/*.jsonl'))
    if not files:
        print('未有快照資料'); return
    for f in files:
        s = load_snaps(f)
        if len(s) < 2:
            print('%s：只有 %d 張快照，未足以分析' % (os.path.basename(f), len(s)))
            continue
        first, last = s[0], s[-1]
        print('══ %s ══' % os.path.basename(f))
        print('快照 %d 張：%s → %s' % (len(s), first['hhmm'], last['hhmm']))
        # 時間間隔檢查（完整性）
        gaps = []
        for a, b in zip(s, s[1:]):
            h1, h2 = int(a['hhmm']), int(b['hhmm'])
            d = (h2 // 100 * 60 + h2 % 100) - (h1 // 100 * 60 + h1 % 100)
            if d > 8: gaps.append('%s→%s (%d分)' % (a['hhmm'], b['hhmm'], d))
        print('完整性：%s' % ('✅ 無明顯缺漏' if not gaps else '⚠️ 缺漏 ' + '、'.join(gaps)))
        # 落飛／退飛幅度
        buckets = [('大幅落飛 ≥30%', lambda r: r <= 0.70), ('落飛 15-30%', lambda r: 0.70 < r <= 0.85),
                   ('平穩 0.85-1.15', lambda r: 0.85 < r <= 1.15), ('退飛 15-40%', lambda r: 1.15 < r <= 1.40),
                   ('大幅退飛 >40%', lambda r: r > 1.40)]
        rows = []
        for k, v in first['odds'].items():
            f2 = last['odds'].get(k)
            if v and f2: rows.append((k, v, f2, f2 / v))
        print('%-18s %6s %10s' % ('類別', '匹數', '平均變幅'))
        for lab, fn in buckets:
            sel = [r for r in rows if fn(r[3])]
            if not sel: continue
            print('%-18s %6d %9.1f%%' % (lab, len(sel), 100 * (sum(r[3] for r in sel) / len(sel) - 1)))
        # 每場落飛王
        byrace = collections.defaultdict(list)
        for k, v, f2, r in rows:
            rn, nm = (k.split('|', 1) if '|' in k else ('-', k))
            byrace[rn].append((r, nm, v, f2))
        print('\n每場落飛王：')
        for rn in sorted(byrace, key=lambda z: (int(z) if z.isdigit() else 99)):
            r, nm, v, f2 = sorted(byrace[rn])[0]
            print('  R%-3s %-10s %.1f → %.1f（%+.0f%%）' % (rn, nm, v, f2, 100 * (r - 1)))
        # 若果有賽果
        rc = 'data/results/%s.json' % os.path.basename(f)[:8]
        if os.path.exists(rc):
            res = json.load(open(rc, encoding='utf-8'))
            print('\n配合賽果嘅回報分析：')
            for lab, fn in buckets:
                sel = [x for x in rows if fn(x[3])]
                nw = sum(1 for x in sel if res.get((x[0].split('|', 1) if '|' in x[0] else ('-', x[0]))[1]) == 1)
                if not sel: continue
                print('  %-18s %4d 匹｜勝出 %.1f%%' % (lab, len(sel), 100 * nw / len(sel)))
        print()

if __name__ == '__main__':
    main()
