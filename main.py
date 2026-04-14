"""
AI News Content Generator for @AI_builderkun
- YouTube Data API で直近3日のAI動画を取得（言語不問・海外動画含む）
- Groq①: 最良動画の選定
- Groq②: 動画内容を日本語で要点まとめ + 図解生成
- Pillowで図解画像を生成（無料）
- daily-content/ にJSONと画像を保存（手動投稿用）
- YouTubeが取得できない場合はRSSにフォールバック
全て無料〜低コストで動作
"""

import feedparser
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path

from groq import Groq

from infographic import create_infographic

# ──────────────────────────────────────────────
# YouTube 検索設定
# ──────────────────────────────────────────────

YOUTUBE_SEARCH_QUERIES = [
    "AI artificial intelligence breakthrough",
    "ChatGPT Claude Gemini new feature",
    "LLM large language model 2025",
    "OpenAI Anthropic Google AI announcement",
    "AI agent automation 2025",
]

YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"


def fetch_youtube_videos(api_key: str, days: int = 3) -> list[dict]:
    """直近N日のAI関連YouTube動画を取得（言語不問）"""
    published_after = (datetime.now(timezone.utc) - timedelta(days=days)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    seen_ids = set()
    videos = []

    for query in YOUTUBE_SEARCH_QUERIES:
        params = urllib.parse.urlencode({
            "part": "snippet",
            "q": query,
            "type": "video",
            "publishedAfter": published_after,
            "maxResults": 5,
            "order": "relevance",
            "key": api_key,
        })
        url = f"{YOUTUBE_API_BASE}/search?{params}"

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "AI-News-Bot/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            print(f"YouTube検索失敗 ({query}): {e}")
            continue

        for item in data.get("items", []):
            video_id = item["id"].get("videoId", "")
            if not video_id or video_id in seen_ids:
                continue
            seen_ids.add(video_id)

            snippet = item["snippet"]
            videos.append({
                "title": snippet.get("title", ""),
                "summary": snippet.get("description", "")[:600],
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "channel": snippet.get("channelTitle", ""),
                "published": snippet.get("publishedAt", ""),
                "source": "youtube",
            })

    print(f"YouTube動画取得: {len(videos)}件")
    return videos


# ──────────────────────────────────────────────
# RSSフォールバック
# ──────────────────────────────────────────────

RSS_SOURCES = [
    "https://techcrunch.com/feed/",
    "https://venturebeat.com/feed/",
    "https://www.theverge.com/rss/index.xml",
    "https://openai.com/blog/rss/",
    "https://www.artificialintelligence-news.com/feed/",
    "https://feeds.feedburner.com/oreilly/radar",
    "http://arxiv.org/rss/cs.AI",
    "https://huggingface.co/blog/feed.xml",
    "https://www.anthropic.com/news/rss",
    "https://deepmind.google/blog/rss.xml",
]

KEYWORDS_INCLUDE = [
    "AI", "artificial intelligence", "LLM", "GPT", "ChatGPT", "Claude",
    "Gemini", "machine learning", "deep learning", "neural", "OpenAI",
    "Anthropic", "Google DeepMind", "Meta AI", "agent", "model", "benchmark",
]

KEYWORDS_EXCLUDE = [
    "I made", "I created", "I built", "check out my", "my project",
    "my AI", "I used AI to", "tutorial", "how I", "sponsored", "advertisement",
]


def fetch_rss_news() -> list[dict]:
    """24時間以内のAI関連ニュースをRSSから収集（フォールバック用）"""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    items = []

    for url in RSS_SOURCES:
        try:
            feed = feedparser.parse(url)
        except Exception:
            continue

        for entry in feed.entries:
            pub = entry.get("published_parsed") or entry.get("updated_parsed")
            if not pub:
                continue
            pub_dt = datetime(*pub[:6], tzinfo=timezone.utc)
            if pub_dt < cutoff:
                continue

            title = entry.get("title", "")
            summary = entry.get("summary", "")[:600]
            text = (title + " " + summary).lower()

            if not any(kw.lower() in text for kw in KEYWORDS_INCLUDE):
                continue
            if any(kw.lower() in text for kw in KEYWORDS_EXCLUDE):
                continue

            items.append({
                "title": title,
                "summary": summary,
                "url": entry.get("link", ""),
                "published": pub_dt.strftime("%Y-%m-%d %H:%M UTC"),
                "source": "rss",
            })

    seen = set()
    unique = []
    for item in items:
        if item["title"] not in seen:
            seen.add(item["title"])
            unique.append(item)

    return unique[:12]


# ──────────────────────────────────────────────
# HTML本文抽出（RSSフォールバック用）
# ──────────────────────────────────────────────

class _TextExtractor(HTMLParser):
    SKIP_TAGS = {"script", "style", "nav", "header", "footer", "aside", "noscript"}

    def __init__(self):
        super().__init__()
        self._skip_depth = 0
        self.chunks: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in self.SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data):
        if self._skip_depth == 0:
            s = data.strip()
            if len(s) > 20:
                self.chunks.append(s)


def fetch_article_body(url: str, max_chars: int = 4000) -> str:
    """記事URLから本文テキストを取得"""
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; AI-News-Bot/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        parser = _TextExtractor()
        parser.feed(html)
        text = " ".join(parser.chunks)
        text = " ".join(text.split())
        return text[:max_chars]

    except Exception as e:
        print(f"記事取得失敗 ({url}): {e}")
        return ""


# ──────────────────────────────────────────────
# Groq①: コンテンツ選定
# ──────────────────────────────────────────────

def select_best_item(items: list[dict], client: Groq) -> int:
    """タイトル+要約を渡して最良の1件のインデックスを返す"""
    items_text = "\n".join(
        f"[{i+1}] {item['title']} / ch: {item.get('channel', '')} ({item.get('published', '')})"
        for i, item in enumerate(items)
    )

    prompt = f"""以下のAI関連コンテンツ一覧から、日本のXユーザーに最もバズりそうな1本の番号だけを返してください。

【選定基準】
- 企業発表・新モデルリリース・業界動向を優先
- 具体的な数字・比較・ビジネスインパクトがあるものを優先
- 「日本人がまだ知らない海外の最新AI情報」として紹介できるものを優先
- 個人作品・チュートリアル系は選ばない

【コンテンツ一覧】
{items_text}

番号のみ（例: 3）を返してください。説明不要。"""

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=10,
    )
    raw = response.choices[0].message.content.strip()
    try:
        idx = int(raw.split()[0]) - 1
        return max(0, min(idx, len(items) - 1))
    except ValueError:
        return 0


# ──────────────────────────────────────────────
# Groq②: 日本語要点まとめ + 図解生成
# ──────────────────────────────────────────────

def generate_content(item: dict, body: str, client: Groq) -> dict:
    """動画/記事の内容から日本語投稿文 + 図解データを生成"""

    is_youtube = item.get("source") == "youtube"
    source_label = "YouTube動画" if is_youtube else "記事"
    url = item["url"]

    prompt = f"""あなたは海外AI情報を日本語でわかりやすく発信するSNSクリエイターです。
以下の{source_label}の内容を深く読み、日本のXユーザー向けに図解コンテンツを作成してください。

【タイトル】
{item['title']}

【チャンネル/ソース】
{item.get('channel', '')}

【内容】
{body if body else item['summary']}

【投稿文のルール】
- 冒頭は「🔥」「⚡」「🚨」などで始め、インパクトを出す
- 「日本語でわかりやすく解説します」「海外では〜」など、日本人向けに橋渡しする文脈を入れる
- {'最後にYouTubeのURLを「🎥 動画はこちら→ ' + url + '」の形式で必ず含める' if is_youtube else 'ハッシュタグ3個以内'}
- 270字以内（URLを含む）

【テンプレート選択ルール】
- stat:       インパクトある数字・記録・スペックが中心
- list:       5つの特徴・変化・ポイントが挙げられる
- comparison: 2つのモデル・サービス・手法を比較している
- ranking:    順位・シェア・ベンチマーク形式で整理できる

【重要】
- 図解の各ポイントは必ず内容から抽出した事実を使うこと
- 推測や補完で埋めないこと。情報が足りなければポイント数を減らすこと

【出力】必ず以下のJSONのみ返してください（説明文・コメント不要）:
{{
  "caption": "<日本語X投稿文。270字以内>",
  "needs_infographic": true,
  "infographic": {{
    "template": "<stat | list | comparison | ranking>",
    "title": "<図解タイトル 18字以内>",
    "conclusion": "<まとめ一文 35字以内>",

    // stat の場合
    "key_stat": "<最もインパクトある数字や事実 25字以内>",
    "points": [
      "<①何か：定義 30字以内>",
      "<②何ができるか：主要機能 30字以内>",
      "<③なぜ重要か：意義・インパクト 30字以内>",
      "<④規模感：数字・比較 30字以内>",
      "<⑤背景・競合・今後 30字以内>"
    ],

    // list の場合
    "points": ["<35字以内>", "<35字以内>", "<35字以内>", "<35字以内>", "<35字以内>"],

    // comparison の場合
    "left_label": "<比較対象A 10字以内>",
    "right_label": "<比較対象B 10字以内>",
    "left_points": ["<25字以内>", "<25字以内>", "<25字以内>"],
    "right_points": ["<25字以内>", "<25字以内>", "<25字以内>"],

    // ranking の場合
    "items": [
      {{"name": "<名前 12字以内>", "desc": "<説明 28字以内>"}},
      {{"name": "<名前 12字以内>", "desc": "<説明 28字以内>"}},
      {{"name": "<名前 12字以内>", "desc": "<説明 28字以内>"}},
      {{"name": "<名前 12字以内>", "desc": "<説明 28字以内>"}},
      {{"name": "<名前 12字以内>", "desc": "<説明 28字以内>"}}
    ]
  }}
}}

使わないキーは出力に含めないこと。"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1200,
    )
    raw = response.choices[0].message.content.strip()

    # コードブロック除去
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    # JSONオブジェクトを正規表現で抽出（余分なテキストがあっても安全に取り出す）
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if not match:
        raise ValueError(f"JSONが見つかりません: {raw[:200]}")
    return json.loads(match.group())


# ──────────────────────────────────────────────
# コンテンツ保存
# ──────────────────────────────────────────────

def save_content(caption: str, infographic_data: dict | None, source_url: str, image_path: str | None) -> str:
    """daily-content/ にJSON + 画像を保存"""
    today = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d")
    output_dir = Path("daily-content")
    output_dir.mkdir(exist_ok=True)

    final_image_path = None
    if image_path and Path(image_path).exists():
        final_image_path = str(output_dir / f"{today}.png")
        Path(image_path).rename(final_image_path)

    content = {
        "date": today,
        "caption": caption,
        "image": final_image_path,
        "source_url": source_url,
        "infographic_data": infographic_data,
        "status": "ready",
    }
    json_path = output_dir / f"{today}.json"
    json_path.write_text(json.dumps(content, ensure_ascii=False, indent=2))
    return str(json_path)


# ──────────────────────────────────────────────
# メイン
# ──────────────────────────────────────────────

def main():
    print("=== AI News Content Generator 起動 ===")
    client = Groq(api_key=os.environ["GROQ_API_KEY"])

    # 1. YouTubeを優先ソースとして取得、失敗 or 0件ならRSSにフォールバック
    youtube_api_key = os.environ.get("YOUTUBE_API_KEY", "")
    items = []

    if youtube_api_key:
        items = fetch_youtube_videos(youtube_api_key, days=3)
    else:
        print("YOUTUBE_API_KEY未設定 → RSSにフォールバック")

    if not items:
        print("YouTube動画なし → RSSにフォールバック")
        items = fetch_rss_news()

    if not items:
        print("コンテンツ取得なし → 終了")
        sys.exit(0)

    print(f"候補: {len(items)}件 (ソース: {items[0].get('source', 'unknown')})")

    # 2. Groq①: 最良コンテンツの選定
    idx = select_best_item(items, client)
    selected = items[idx]
    print(f"選定: {selected['title']}")
    print(f"URL: {selected['url']}")

    # 3. 本文取得（YouTubeは説明文のみ、RSSは記事本文をスクレイピング）
    if selected.get("source") == "youtube":
        body = selected.get("summary", "")
        print(f"動画説明文: {len(body)}文字")
    else:
        print(f"記事本文取得中: {selected['url']}")
        body = fetch_article_body(selected["url"])
        print(f"本文取得: {len(body)}文字")

    # 4. Groq②: 日本語要点まとめ + 図解生成
    result = generate_content(selected, body, client)
    print(f"キャプション: {result['caption'][:80]}...")

    # 5. 図解生成
    image_path = None
    if result.get("needs_infographic") and result.get("infographic"):
        image_path = "/tmp/infographic.png"
        create_infographic(result["infographic"], image_path)
        print("図解生成: 完了")

    # 6. 保存
    today = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d")
    json_path = save_content(
        caption=result["caption"],
        infographic_data=result.get("infographic"),
        source_url=selected["url"],
        image_path=image_path,
    )
    print(f"保存完了: {json_path}")
    print(f"CONTENT_DATE={today}")


if __name__ == "__main__":
    main()
