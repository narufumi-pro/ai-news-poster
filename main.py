"""
AI News Auto-Poster for @AI_builderkun
- RSSから24時間以内のAIニュースを取得
- Google Gemini Flash（無料枠：1日1,500回）で選定 + 投稿文生成
- Pillowで図解画像を生成（無料）
- TweepyでXに自動投稿
全て無料で動作
"""

import feedparser
import json
import os
import sys
from datetime import datetime, timedelta, timezone

import google.generativeai as genai
import tweepy

from infographic import create_infographic

# ──────────────────────────────────────────────
# ニュースソース（RSSフィード）
# ──────────────────────────────────────────────
NEWS_SOURCES = [
    "https://techcrunch.com/feed/",
    "https://venturebeat.com/feed/",
    "https://www.theverge.com/rss/index.xml",
    "https://openai.com/blog/rss/",
    "https://www.artificialintelligence-news.com/feed/",
    "https://feeds.feedburner.com/oreilly/radar",
    "http://arxiv.org/rss/cs.AI",
    "https://huggingface.co/blog/feed.xml",
]

# 含める必要あり（どれか1つ以上）
KEYWORDS_INCLUDE = [
    "AI", "artificial intelligence", "LLM", "GPT", "ChatGPT", "Claude",
    "Gemini", "machine learning", "deep learning", "neural", "OpenAI",
    "Anthropic", "Google DeepMind", "Meta AI", "agent", "model", "benchmark",
]

# これが含まれる記事は除外（個人投稿・PR系）
KEYWORDS_EXCLUDE = [
    "I made", "I created", "I built", "check out my", "my project",
    "my AI", "I used AI to", "tutorial", "how I", "sponsored", "advertisement",
]


def fetch_news() -> list[dict]:
    """24時間以内のAI関連ニュースをRSSから収集"""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    items = []

    for url in NEWS_SOURCES:
        try:
            feed = feedparser.parse(url)
        except Exception:
            continue

        for entry in feed.entries:
            # 日時チェック
            pub = entry.get("published_parsed") or entry.get("updated_parsed")
            if not pub:
                continue
            pub_dt = datetime(*pub[:6], tzinfo=timezone.utc)
            if pub_dt < cutoff:
                continue

            title = entry.get("title", "")
            summary = entry.get("summary", "")[:600]
            text = (title + " " + summary).lower()

            # キーワードフィルタ
            if not any(kw.lower() in text for kw in KEYWORDS_INCLUDE):
                continue
            if any(kw.lower() in text for kw in KEYWORDS_EXCLUDE):
                continue

            items.append({
                "title": title,
                "summary": summary,
                "url": entry.get("link", ""),
                "published": pub_dt.strftime("%Y-%m-%d %H:%M UTC"),
            })

    # 重複除去（タイトルで）
    seen = set()
    unique = []
    for item in items:
        if item["title"] not in seen:
            seen.add(item["title"])
            unique.append(item)

    return unique[:12]  # 最大12件をGeminiに渡す


def select_and_generate(items: list[dict]) -> dict:
    """
    Google Gemini Flash（無料枠）を1回だけ呼び出し：
    - 最もバズりそうな記事を選定
    - 日本語キャプション生成
    - 図解テキスト生成（必要な場合）
    """
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    model = genai.GenerativeModel("gemini-1.5-flash")

    articles_text = "\n\n".join(
        f"[{i+1}] {item['title']}\n{item['summary']}\n配信: {item['published']}"
        for i, item in enumerate(items)
    )

    prompt = f"""あなたはAI情報発信のプロです。以下のAI関連ニュース一覧から最も日本のXユーザーにバズりそうな1本を選び、投稿コンテンツを生成してください。

【ニュース一覧】
{articles_text}

【選定基準】
- 企業発表・研究成果・業界動向を優先
- 「AIで〇〇作ってみた」系の個人投稿は選ばない
- 数字・比較・驚き・ビジネスインパクトがあるものを優先

【出力】必ず以下のJSONのみ返してください（説明文不要）:
{{
  "selected_index": <1始まりの番号>,
  "caption": "<日本語X投稿文。インパクトある冒頭＋内容＋ハッシュタグ。270字以内>",
  "needs_infographic": <true または false>,
  "infographic": {{
    "title": "<図解タイトル 15字以内>",
    "key_stat": "<最もインパクトある数字や事実 25字以内>",
    "points": [
      "<ポイント1 30字以内>",
      "<ポイント2 30字以内>",
      "<ポイント3 30字以内>"
    ],
    "conclusion": "<まとめ一文 35字以内>"
  }}
}}

needs_infographicは、数字・比較・フロー・変化を図解できる場合のみtrue。単なるニュースはfalse。"""

    response = model.generate_content(prompt)
    raw = response.text.strip()

    # JSON部分だけ抽出（```json ... ``` に包まれている場合も対応）
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw)


def post_to_x(caption: str, image_path: str | None = None) -> None:
    """X APIv2でツイート（画像あり/なし）"""
    # v2 クライアント（テキスト投稿）
    client_v2 = tweepy.Client(
        consumer_key=os.environ["X_API_KEY"],
        consumer_secret=os.environ["X_API_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_SECRET"],
    )

    media_id = None
    if image_path and os.path.exists(image_path):
        # 画像アップロードはv1.1 API
        auth = tweepy.OAuth1UserHandler(
            os.environ["X_API_KEY"],
            os.environ["X_API_SECRET"],
            os.environ["X_ACCESS_TOKEN"],
            os.environ["X_ACCESS_SECRET"],
        )
        api_v1 = tweepy.API(auth)
        media = api_v1.media_upload(filename=image_path)
        media_id = media.media_id

    client_v2.create_tweet(
        text=caption,
        media_ids=[media_id] if media_id else None,
    )


def main():
    print("=== AI News Auto-Poster 起動 ===")

    # 1. ニュース収集
    items = fetch_news()
    if not items:
        print("24時間以内の新着AIニュースなし → 終了")
        sys.exit(0)
    print(f"取得: {len(items)}件")

    # 2. Gemini Flash で選定 & コンテンツ生成（1回のみ・無料）
    result = select_and_generate(items)
    idx = result["selected_index"] - 1
    selected = items[idx] if 0 <= idx < len(items) else items[0]
    print(f"選定記事: {selected['title']}")
    print(f"キャプション: {result['caption'][:60]}...")

    # 3. 図解生成（必要な場合）
    image_path = None
    if result.get("needs_infographic") and result.get("infographic"):
        image_path = "/tmp/infographic.png"
        create_infographic(result["infographic"], image_path)
        print("図解生成: 完了")

    # 4. X に投稿
    post_to_x(result["caption"], image_path)
    print("Xへの投稿: 完了")


if __name__ == "__main__":
    main()
