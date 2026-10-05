# HKJC 賠率走勢監察（雲端版）

## 架構（重要：Vercel 唔適合做抓取）
| 工作 | 應該用 | 原因 |
|---|---|---|
| **抓取賠率** | **GitHub Actions**（每 5 分鐘） | Vercel Serverless 冇常駐進程；Hobby Cron 只可以**每日一次** |
| 顯示／分析 | **Vercel**（靜態） | 靜態頁讀取 GitHub 上嘅快照 JSONL |
| 資料儲存 | **Git repo**（自動 commit） | 免費、有版本紀錄、可審計 |

## 一、部署步驟（3 步）

### 1. 建立 GitHub repo 並上傳
```bash
cd hkjc_cloud
git init && git add -A && git commit -m "init"
git remote add origin https://github.com/<你嘅帳號>/hkjc-odds.git
git push -u origin main
```

### 2. 開啟 Actions 寫入權限
repo → Settings → Actions → General → Workflow permissions →
**Read and write permissions** → Save

### 3. 設定賽日（每次賽日前改）
`.github/workflows/odds-capture.yml` 內：
```yaml
env:
  RACE_DATE: '2026/10/07'   # ← 改呢一行
  VENUE: 'HV'               # ← ST 或 HV
```
改完 push → GitHub Actions 就會每 5 分鐘自動抓，直到頁面冇賠率為止。

## 二、動作流程
```
每 5 分鐘：GitHub Actions → 抓 11 場賠率 → commit data/odds_snapshots/20261007.jsonl
每日 23:30：分析 → commit data/analysis_report.txt
Vercel：靜態頁讀取 JSONL → 顯示走勢
```

## 三、本機測試（唔需要等雲端）
```bash
python3 scripts/cloud_snapshot.py 2026/10/07 HV 11
python3 scripts/analyse_snapshots.py
```

## 四、部署 Viewer 到 Vercel
```bash
cd hkjc_cloud
npx vercel --prod       # 或喺 Vercel 網頁 Import 呢個 repo
```
部署後，喺頁面輸入：
- GitHub repo（例如 `你的帳號/hkjc-odds`）
- 賽日（例如 `20261007`）
→ 就會顯示快照數目、完整性、最大落飛／退飛、每場落飛王

## 五、⚠️ 完整性說明（「確保抓取完整」）
| 風險 | 影響 | 緩解 |
|---|---|---|
| GitHub Cron 最密 5 分鐘，繁忙時可延遲 5-20 分鐘 | 時間解析度下降 | 分析腳本會**自動偵測缺漏**並報告 |
| repo 60 日冇活動 → 停用 scheduled workflow | 任務停止 | 每次 commit 都係活動 ✓ 唔會停 |
| 賠率頁未更新 | 重複快照 | 腳本自動去重（賠率無變唔寫入） |
| 抓錯賽日 | 資料污染 | 腳本核對頁面賽日，唔符即跳過 |

**如需 1 分鐘解析度**：改用 **Cloudflare Workers Cron**（免費、每分鐘）→ 見 `cloudflare-worker.js`

## 六、檔案
```
hkjc_cloud/
├── .github/workflows/odds-capture.yml    每 5 分鐘抓取
├── .github/workflows/odds-analysis.yml   每日分析
├── scripts/cloud_snapshot.py             抓取（只用標準函式庫）
├── scripts/analyse_snapshots.py          分析 + 完整性檢查
├── data/odds_snapshots/*.jsonl           快照資料（自動累積）
└── public/index.html                     Vercel viewer
```
