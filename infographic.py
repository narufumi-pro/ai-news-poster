"""
図解画像生成モジュール
Pillow のみ使用（APIトークン不要）
出力サイズ: 1200x675 (Xのカード比率 16:9)
"""

import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# ──────────────────────────────────────────────
# カラーパレット（ダーク × シアン）
# ──────────────────────────────────────────────
BG_DARK = "#0D1117"
BG_PANEL = "#161B22"
BG_HEADER = "#0A0F16"
ACCENT = "#00D4FF"
ACCENT_DIM = "#0099BB"
WHITE = "#F0F6FF"
GRAY = "#6E7681"
DOT_COLORS = ["#00D4FF", "#FF6B6B", "#FFD93D"]

W, H = 1200, 675


def _get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """日本語対応フォントを取得（Noto Sans CJK → fallback）"""
    candidates_bold = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
        "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
        "/System/Library/Fonts/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    candidates_regular = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
        "/System/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    candidates = candidates_bold if bold else candidates_regular
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _draw_rounded_rect(draw: ImageDraw.Draw, xy, radius: int, fill: str):
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=fill)


def create_infographic(data: dict, output_path: str) -> None:
    """
    data = {
        "title": str,
        "key_stat": str,
        "points": [str, str, str],
        "conclusion": str,
    }
    """
    img = Image.new("RGB", (W, H), color=BG_DARK)
    draw = ImageDraw.Draw(img)

    # ── フォント ──
    f_title = _get_font(38, bold=True)
    f_stat = _get_font(68, bold=True)
    f_point = _get_font(30)
    f_small = _get_font(22)
    f_label = _get_font(20, bold=True)

    # ── ヘッダーバー ──
    draw.rectangle([0, 0, W, 64], fill=BG_HEADER)
    draw.rectangle([0, 60, W, 64], fill=ACCENT)  # 下線
    # ロゴ風テキスト
    draw.text((30, 14), "AI最前線", font=_get_font(28, bold=True), fill=ACCENT)
    draw.text((170, 22), "by @AI_builderkun", font=f_small, fill=GRAY)

    # ── タイトル ──
    title_text = data.get("title", "AI最新情報")
    draw.text((W // 2, 105), title_text, font=f_title, fill=WHITE, anchor="mm")

    # ── キースタット（中央大きく）──
    stat_text = data.get("key_stat", "")
    # 背景パネル
    _draw_rounded_rect(draw, [160, 135, W - 160, 255], radius=16, fill=BG_PANEL)
    # アクセントライン
    draw.rectangle([160, 135, 168, 255], fill=ACCENT)
    draw.text((W // 2, 195), stat_text, font=f_stat, fill=ACCENT, anchor="mm")

    # ── ポイント3項目 ──
    points = (data.get("points") or [])[:3]
    for i, point in enumerate(points):
        y_base = 285 + i * 90
        # パネル背景
        _draw_rounded_rect(draw, [60, y_base, W - 60, y_base + 72], radius=12, fill=BG_PANEL)
        # ドット
        dot_color = DOT_COLORS[i % len(DOT_COLORS)]
        draw.ellipse([80, y_base + 20, 112, y_base + 52], fill=dot_color)
        # 番号
        draw.text((96, y_base + 36), str(i + 1), font=f_label, fill=BG_DARK, anchor="mm")
        # テキスト（長い場合は折り返し）
        wrapped = textwrap.shorten(point, width=36, placeholder="…")
        draw.text((140, y_base + 36), wrapped, font=f_point, fill=WHITE, anchor="lm")

    # ── フッター（結論）──
    draw.rectangle([0, H - 72, W, H], fill=BG_HEADER)
    draw.rectangle([0, H - 72, W, H - 68], fill=ACCENT_DIM)
    conclusion = data.get("conclusion", "")
    draw.text((W // 2, H - 36), conclusion, font=_get_font(26), fill=WHITE, anchor="mm")

    img.save(output_path, format="PNG", optimize=True)
