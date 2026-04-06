# AI News Auto-Poster @AI_builderkun

## 概要
海外AIニュースRSS → Claude Haiku（1回/実行）→ 図解画像生成 → X自動投稿

**1日3回（9時・15時・21時）自動実行**

## コスト試算
- Gemini Flash: **無料**（1日1,500リクエストまで）
- GitHub Actions: **無料**
- X API: **無料**（月1,500ツイートまで）
- **合計：完全無料**

---

## セットアップ手順

### 1. X Developer Account の取得
1. [developer.twitter.com](https://developer.twitter.com) でアプリ作成
2. **User authentication settings** で Read and Write を有効化
3. 以下の4つのキーを取得：
   - API Key & Secret
   - Access Token & Secret（Generate ボタンで発行）

### 2. GitHubリポジトリの作成
```bash
# このプロジェクト全体をGitHubにpush
git init
git add .
git commit -m "init: AI news auto-poster"
git remote add origin https://github.com/YOUR_USERNAME/ai-news-poster.git
git push -u origin main
```

### 3. GitHub Secrets の設定
リポジトリの `Settings > Secrets and variables > Actions` に追加：

| Secret名 | 値 |
|---|---|
| `GEMINI_API_KEY` | Google AI Studio APIキー（無料） |
| `X_API_KEY` | X API Key |
| `X_API_SECRET` | X API Key Secret |
| `X_ACCESS_TOKEN` | X Access Token |
| `X_ACCESS_SECRET` | X Access Token Secret |

### 4. 動作確認
GitHub Actions の `Actions` タブ → `AI News Auto-Poster` → `Run workflow` で手動実行

---

## ローカル実行（テスト）
```bash
cd for-freelance/sns/ai-poster
pip install -r requirements.txt

export GEMINI_API_KEY=AIza...
export X_API_KEY=...
export X_API_SECRET=...
export X_ACCESS_TOKEN=...
export X_ACCESS_SECRET=...

python main.py
```

---

## ファイル構成
```
ai-poster/
├── main.py          # メイン処理（RSS取得 → Claude → 投稿）
├── infographic.py   # Pillowで図解画像生成
├── requirements.txt
└── .github/
    └── workflows/
        └── ai-news-poster.yml  # GitHub Actions スケジュール
```
