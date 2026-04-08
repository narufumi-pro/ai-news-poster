"""
AI News Content Generator for @AI_builderkun
- RSSから24時間以内のAIニュースを取得
- Groq①: 最良記事の選定（タイトル+要約）
- 元記事URLから本文を取得（stdlib urllib）
- Groq②: 本文を読んで図解+投稿文を生成
- Pillowで図解画像を生成（無料）
- daily-content/ にJSONと画像を保存（手動投稿用）
全て無料で動作
"""

import feedparser
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path

from groq import Groq

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


# ──────────────────────────────────────────────
# HTML本文抽出（外部ライブラリ不要）
# ──────────────────────────────────────────────

class _TextExtractor(HTMLParser):
    """HTMLからテキストだけを取り出すパーサー"""
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
            if len(s) > 20:  # 短すぎる断片は除外
                self.chunks.append(s)


def fetch_article_body(url: str, max_chars: int = 4000) -> str:
    """記事URLから本文テキストを取得（最大max_chars文字）"""
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

        # 空白を整理して返す
        text = " ".join(text.split())
        return text[:max_chars]

    except Exception as e:
        print(f"記事取得失敗 ({url}): {e}")
        return ""


# ──────────────────────────────────────────────
# RSSニュース収集
# ──────────────────────────────────────────────

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
            })

    seen = set()
    unique = []
    for item in items:
        if item["title"] not in seen:
            seen.add(item["title"])
            unique.append(item)

    return unique[:12]


# ──────────────────────────────────────────────
# Groq呼び出し①: 記事選定のみ（軽量）
# ──────────────────────────────────────────────

def select_article(items: list[dict], client: Groq) -> int:
    """12件のタイトル+要約を渡して最良の1件のインデックスを返す"""
    articles_text = "\n".join(
        f"[{i+1}] {item['title']} ({item['published']})"
        for i, item in enumerate(items)
    )

    prompt = f"""以下のAIニュース一覧から、日本のXユーザーに最もバズりそうな1本の番号だけを返してください。

【選定基準】
- 企業発表・新モデルリリース・業界動向を優先
- 具体的な数字・比較・ビジネスインパクトがあるものを優先
- 個人作品・チュートリアル系は選ばない

【ニュース一覧】
{articles_text}

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
# Groq呼び出し②: 本文を読んで図解+投稿文を生成
# ──────────────────────────────────────────────

def generate_content(article: dict, body: str, client: Groq) -> dict:
    """記事本文から図解データ + X投稿文を生成する"""

    prompt = f"""あなたはAI情報発信のプロです。以下の記事を深く読み、日本のXユーザー向けに図解コンテンツを作成してください。

【記事タイトル】
{article['title']}

【記事本文】
{body if body else article['summary']}

【テンプレート選択ルール】
- stat:       インパクトある数字・記録・スペックが中心の記事
- list:       5つの特徴・変化・ポイントが挙げられる記事
- comparison: 2つのモデル・サービス・手法を比較している記事
- ranking:    順位・シェア・ベンチマーク形式で整理できる記事

【重要】
- 図解の各ポイントは必ず記事本文に書かれている事実から作成すること
- 推測や補完で埋めないこと。情報が足りなければポイント数を減らすこと
- stat テンプレートのpoints は実際に抽出できる分だけ（1〜3個）

【出力】必ず以下のJSONのみ返してください（説明文・コメント不要）:
{{
  "caption": "<日本語X投稿文。インパクトある冒頭＋要点＋ハッシュタグ3個以内。270字以内>",
  "needs_infographic": true,
  "infographic": {{
    "template": "<stat | list | comparison | ranking>",
    "title": "<図解タイトル 18字以内>",
    "conclusion": "<まとめ一文 35字以内>",

    // stat の場合
    "key_stat": "<最もインパクトある数字や事実 25字以内>",
    "points": ["<実際に記事にある事実 30字以内>", ...],

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

    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw)


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

    # 1. ニュース収集
    items = fetch_news()
    if not items:
        print("24時間以内の新着AIニュースなし → 終了")
        sys.exit(0)
    print(f"取得: {len(items)}件")

    # 2. Groq①: 最良記事の選定（タイトルのみ・軽量）
    idx = select_article(items, client)
    selected = items[idx]
    print(f"選定記事: {selected['title']}")

    # 3. 元記事から本文を取得
    print(f"記事本文取得中: {selected['url']}")
    body = fetch_article_body(selected["url"])
    print(f"本文取得: {len(body)}文字")

    # 4. Groq②: 本文を読んで図解+投稿文を生成
    result = generate_content(selected, body, client)
    print(f"キャプション: {result['caption'][:60]}...")

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
