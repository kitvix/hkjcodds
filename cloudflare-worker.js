// Cloudflare Worker：每分鐘抓一次（免費方案支援）
// 部署：Workers → Create → 貼上 → 設定 KV binding（ODDS）→ Cron Triggers: */1 * * * *
export default {
  async scheduled(event, env, ctx) {
    const date = env.RACE_DATE || '2026/10/07';
    const venue = env.VENUE || 'HV';
    const out = {};
    for (let n = 1; n <= 11; n++) {
      const u = `https://racing.hkjc.com/racing/Chinese/tipsindex/tips_index.asp?RaceNo=${n}`;
      const r = await fetch(u, { headers: { 'User-Agent': 'Mozilla/5.0 (compatible; odds-bot)' } });
      if (!r.ok) continue;
      const t = (await r.text()).replace(/<[^>]+>/g, '|').replace(/\|+/g, '|');
      const toks = t.split('|').map(s => s.trim()).filter(Boolean);
      const HEAD = ['馬號', '馬名', '負磅', '練馬師', '騎師', '檔位', '獨贏賠率'];
      let start = -1;
      for (let i = 0; i < toks.length - HEAD.length; i++) {
        if (HEAD.every((h, j) => toks[i + j] === h)) { start = i + HEAD.length; break; }
      }
      if (start < 0) continue;
      let i = start;
      while (i < toks.length) {
        if (!/^\d{1,2}$/.test(toks[i])) { i++; continue; }
        const nm = toks[i + 1], od = parseFloat(toks[i + 6]);
        if (od > 0 && !/^\d{1,2}$/.test(nm)) { out[`${n}|${nm}`] = od; i += 9; } else i++;
      }
    }
    if (!Object.keys(out).length) return;
    const hh = new Date(Date.now() + 8 * 3600e3).toISOString().slice(11, 16).replace(':', '');
    const key = date.replace(/\//g, '');
    const prev = await env.ODDS.get(key + ':last');
    if (prev && JSON.stringify(JSON.parse(prev).odds) === JSON.stringify(out)) return;
    const rec = { hhmm: hh, date, venue, odds: out };
    const cur = await env.ODDS.get(key);
    await env.ODDS.put(key, (cur ? cur + '\n' : '') + JSON.stringify(rec));
    await env.ODDS.put(key + ':last', JSON.stringify(rec));
  }
};
