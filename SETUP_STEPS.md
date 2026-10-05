# 部署步驟明細（GitHub + Vercel）
**跟住做，大約 10 分鐘**

---

## STEP 0 · 開終端機

```bash
cd /Users/kit/Documents/deepseek-harness/default-workspace/hkjc_cloud
ls -a          # 應該見到 .github  scripts  public  README.md
```

---

## STEP 1 · 喺 GitHub 建立 repo（網頁）

1. 去 https://github.com/new
2. **Repository name**：`hkjc-odds`
3. **Public** ← ⚠️ 一定要揀 Public（否則 Vercel 讀唔到快照）
4. ❌ **唔好**勾 "Add a README file"、唔好加 .gitignore、唔好揀 license
5. 撳 **Create repository**

建立後會見到一個空 repo 頁面（記住嗰個 URL，例如 `https://github.com/你的帳號/hkjc-odds.git`）

---

## STEP 2 · 上傳檔案（終端機）

```bash
cd /Users/kit/Documents/deepseek-harness/default-workspace/hkjc_cloud

# 如果之前未設定過 git 身份（只需做一次）
git config --global user.name "你的名字"
git config --global user.email "你的email"

git init
git add -A
git commit -m "init: HKJC odds capture"
git branch -M main
git remote add origin https://github.com/你的帳號/hkjc-odds.git
git push -u origin main
```

**預期結果**：
```
 * [new branch]      main -> main
branch 'main' set up to track 'origin/main'.
```

> 如果彈出要登入：用 GitHub 帳號 + **Personal Access Token**（Settings → Developer settings →
> Personal access tokens → Fine-grained → repo 權限: Contents = Read and write）

---

## STEP 3 · 開啟 Actions 寫入權限 ⚠️ 最重要

1. 去你嘅 repo → **Settings**
2. 左邊 → **Actions** → **General**
3. 拉到最底 **Workflow permissions**
4. 揀 **Read and write permissions** ← 一定要
5. **Save**

（唔做呢步 → workflow 抓到賠率但推唔返 repo）

---

## STEP 4 · 手動測試一次

1. 去 repo → **Actions** 分頁
2. 如果彈「I understand my workflows, go ahead and enable them」→ 撳佢
3. 左邊揀 **HKJC 賠率快照** → 右邊 **Run workflow** → **Run workflow**
4. 等 30 秒 → 撳入去睇 log

**預期結果（10/07 賠率未公佈時）**：
```
[15:21] 未取得任何賠率（未公佈／已完賽）
無新快照
```
→ ✅ 代表系統正常，只係賠率未出

**10/07 早上再睇**，應該變成：
```
自動偵測賽日：07/10/2026
[09:02] 已記錄 108 匹／9 場
```

---

## STEP 5 · 部署 Viewer 到 Vercel

### 方法 A（網頁，推薦）
1. 去 https://vercel.com/new
2. **Import Git Repository** → 揀 `hkjc-odds`
3. 設定：
   | 欄位 | 值 |
   |---|---|
   | Framework Preset | **Other** |
   | Root Directory | **public** ← 撳 Edit 改 |
   | Build Command | 留空 |
   | Output Directory | 留空 |
   | Install Command | 留空 |
4. 撳 **Deploy** → 等 20 秒 → 完成

### 方法 B（終端機）
```bash
cd /Users/kit/Documents/deepseek-harness/default-workspace/hkjc_cloud
npx vercel --prod
# Root Directory 揀 public
```

**部署後測試**：
開 Vercel 畀你嘅 URL → 填：
- GitHub 快照來源：`你的帳號/hkjc-odds`
- 賽日：`20261007`
→ 撳「載入雲端快照」
（未開賽前會顯示「冇快照資料」= 正常）

---

## STEP 6 · 10/07 當日運作

| 時間 | 會發生咩 | 你要做咩 |
|---|---|---|
| 08:30+ | Actions 每 5 分鐘自動跑 | ❌ 唔需要做 |
| 賠率公佈後 | 開始 commit `data/odds_snapshots/20261007.jsonl` | 可以去 repo 睇 commits |
| 每場開跑前 | 快照持續記錄 | — |
| 23:30 | `odds-analysis.yml` 出分析報告 | 去 `data/analysis_report.txt` 睇 |
| 任何時間 | Vercel 頁面睇走勢 | 輸入 repo + 日期 |

**唔需要手動改賽日** —— 腳本會由 HKJC 頁面自動偵測 ✓

---

## STEP 7 · 之後每個賽日

**唔需要做任何事** ✓
- 有賽事 → 頁面有賠率 → 自動記錄
- 冇賽事 → 自動跳過（唔會污染資料）

---

## 常見問題

| 問題 | 原因 / 解決 |
|---|---|
| Actions 冇自動跑 | Settings → Actions → General → 確認 Actions 已啟用 |
| push 被拒 | 檢查 remote URL 同 token 權限（Contents: Read and write） |
| Actions 跑但冇 commit | STEP 3 嘅 workflow permissions 未設 |
| Vercel 載入失敗 | ① repo 要 **Public** ② 分支係 **main** ③ 賽日要有資料 |
| Cron 冇準時 | GitHub 免費版 cron 繁忙時會延遲 5-20 分鐘（正常） |
| 想要 1 分鐘解析度 | 用 `cloudflare-worker.js`（免費）→ 同我講，我幫你設定 |

---

## 成本

| 服務 | 費用 |
|---|---|
| GitHub repo (public) | **免費** |
| GitHub Actions | **免費**（public repo 無限分鐘） |
| Vercel (Hobby) | **免費** |
| **總計** | **$0** |
