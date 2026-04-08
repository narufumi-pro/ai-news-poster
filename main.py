"""
AI News Content Generator for @AI_builderkun
- RSSから24時間以内のAIニュースを取得
- Groq（無料枠）で選定 + 投稿文生成
- Pillowで図解画像を生成（無料）
- daily-content/ にJSONと画像を保存（手動投稿用）
全て無料で動作
"""

import feedparser
import json
import os
import sys
from datetime import datetime, timedelta, timezone
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
    Groq（無料枠）を1回だけ呼び出し：
    - 最もバズりそうな記事を選定
    - 日本語キャプション生成
    - テンプレート選択 + 図解テキスト生成
    """
    client = Groq(api_key=os.environ["GROQ_API_KEY"])

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

【テンプレート選択ルール】
- stat:       インパクトある数字・記録・スペックがある場合
- list:       5つの特徴・変化・ポイントをまとめる場合
- comparison: 2つのモデル・サービス・手法を比較する場合
- ranking:    上位N位形式で整理できる場合（ベンチマーク・シェア等）

【出力】必ず以下のJSONのみ返してください（説明文不要）:
{{
  "selected_index": <1始まりの番号>,
  "caption": "<日本語X投稿文。インパクトある冒頭＋内容＋ハッシュタグ3個以内。270字以内>",
  "needs_infographic": <true または false>,
  "infographic": {{
    "template": "<stat | list | comparison | ranking>",
    "title": "<図解タイトル 18字以内>",
    "conclusion": "<まとめ一文 35字以内>",

    // template=stat の場合のみ
    "key_stat": "<最もインパクトある数字や事実 25字以内>",
    "points": ["<30字以内>", "<30字以内>", "<30字以内>"],

    // template=list の場合のみ
    "points": ["<35字以内>", "<35字以内>", "<35字以内>", "<35字以内>", "<35字以内>"],

    // template=comparison の場合のみ
    "left_label": "<比較対象A 10字以内>",
    "right_label": "<比較対象B 10字以内>",
    "left_points": ["<25字以内>", "<25字以内>", "<25字以内>"],
    "right_points": ["<25字以内>", "<25字以内>", "<25字以内>"],

    // template=ranking の場合のみ
    "items": [
      {{"name": "<名前 12字以内>", "desc": "<説明 28字以内>"}},
      {{"name": "<名前 12字以内>", "desc": "<説明 28字以内>"}},
      {{"name": "<名前 12字以内>", "desc": "<説明 28字以内>"}},
      {{"name": "<名前 12字以内>", "desc": "<説明 28字以内>"}},
      {{"name": "<名前 12字以内>", "desc": "<説明 28字以内>"}}
    ]
  }}
}}

needs_infographicはtrue推奨。図解にしにくい単純なニュースのみfalse。
使わないキーは出力に含めないこと。"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1200,
    )
    raw = response.choices[0].message.content.strip()

    # JSON部分だけ抽出（```json ... ``` に包まれている場合も対応）
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw)


def save_content(caption: str, infographic_data: dict | None, source_url: str, image_path: str | None) -> str:
    """daily-content/ にJSON + 画像を保存して投稿準備完了状態にする"""
    today = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d")
    output_dir = Path("daily-content")
    output_dir.mkdir(exist_ok=True)

    # 画像をdaily-contentに移動
    final_image_path = None
    if image_path and Path(image_path).exists():
        final_image_path = str(output_dir / f"{today}.png")
        Path(image_path).rename(final_image_path)

    # JSON保存
    content = {
        "date": today,
        "caption": caption,
        "image": final_image_path,
        "source_url": source_url,
        "infographic_data": infographic_data,
        "status": "ready",  # 手動投稿待ち
    }
    json_path = output_dir / f"{today}.json"
    json_path.write_text(json.dumps(content, ensure_ascii=False, indent=2))

    return str(json_path)


def main():
    print("=== AI News Content Generator 起動 ===")

    # 1. ニュース収集
    items = fetch_news()
    if not items:
        print("24時間以内の新着AIニュースなし → 終了")
        sys.exit(0)
    print(f"取得: {len(items)}件")

    # 2. Groq で選定 & コンテンツ生成（1回のみ・無料）
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

    # 4. daily-content/ に保存
    today = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d")
    json_path = save_content(
        caption=result["caption"],
        infographic_data=result.get("infographic"),
        source_url=selected["url"],
        image_path=image_path,
    )
    print(f"保存完了: {json_path}")
    print(f"CONTENT_DATE={today}")  # ワークフローで参照用


if __name__ == "__main__":
    main()
