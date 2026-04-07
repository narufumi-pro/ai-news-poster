"""
図解画像生成モジュール
Pillow のみ使用（APIトークン不要）
出力サイズ: 1200x675 (Xのカード比率 16:9)

テンプレート種別:
  stat       - 数字強調型（大きい数字 + 3ポイント）
  list       - 箇条書き型（5項目）
  comparison - 比較型（A vs B）
  ranking    - ランキング型（1〜5位）
  grid       - グリッド型（3〜4列の概要まとめ）
"""

import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# ──────────────────────────────────────────────
# カラーパレット（ダーク × シアン）
# ──────────────────────────────────────────────
BG_DARK   = "#0D1117"
BG_PANEL  = "#161B22"
BG_HEADER = "#0A0F16"
ACCENT    = "#00D4FF"
ACCENT_DIM = "#0099BB"
WHITE     = "#F0F6FF"
GRAY      = "#6E7681"
GREEN     = "#3FB950"
RED       = "#F85149"
YELLOW    = "#FFD93D"
DOT_COLORS = [ACCENT, "#FF6B6B", YELLOW]
RANK_COLORS = ["#FFD700", "#C0C0C0", "#CD7F32", ACCENT, GRAY]

W, H = 1200, 675


# ──────────────────────────────────────────────
# 共通ユーティリティ
# ──────────────────────────────────────────────

def _get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """日本語対応フォントを取得"""
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


def _draw_rounded_rect(draw: ImageDraw.Draw, xy, radius: int, fill: str, outline: str = None, width: int = 2):
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=fill, outline=outline, width=width)


def _draw_header(draw: ImageDraw.Draw, title: str):
    """共通ヘッダーバー"""
    draw.rectangle([0, 0, W, 64], fill=BG_HEADER)
    draw.rectangle([0, 60, W, 64], fill=ACCENT)
    draw.text((30, 14), "AI最前線", font=_get_font(28, bold=True), fill=ACCENT)
    draw.text((170, 22), "by @AI_builderkun", font=_get_font(20), fill=GRAY)


def _draw_footer(draw: ImageDraw.Draw, conclusion: str):
    """共通フッター"""
    draw.rectangle([0, H - 68, W, H], fill=BG_HEADER)
    draw.rectangle([0, H - 68, W, H - 64], fill=ACCENT_DIM)
    draw.text((W // 2, H - 34), conclusion, font=_get_font(24), fill=WHITE, anchor="mm")


def _new_canvas() -> tuple[Image.Image, ImageDraw.Draw]:
    img = Image.new("RGB", (W, H), color=BG_DARK)
    return img, ImageDraw.Draw(img)


# ──────────────────────────────────────────────
# テンプレート1: stat（数字強調型）
# ──────────────────────────────────────────────

def _create_stat(data: dict, output_path: str):
    """
    data keys: title, key_stat, points(list[str] 最大3), conclusion
    """
    img, draw = _new_canvas()
    _draw_header(draw, data.get("title", ""))

    draw.text((W // 2, 100), data.get("title", ""), font=_get_font(36, bold=True), fill=WHITE, anchor="mm")

    # キースタット
    _draw_rounded_rect(draw, [160, 128, W - 160, 248], radius=16, fill=BG_PANEL)
    draw.rectangle([160, 128, 168, 248], fill=ACCENT)
    draw.text((W // 2, 188), data.get("key_stat", ""), font=_get_font(64, bold=True), fill=ACCENT, anchor="mm")

    # ポイント3項目
    points = (data.get("points") or [])[:3]
    for i, point in enumerate(points):
        y = 278 + i * 88
        _draw_rounded_rect(draw, [60, y, W - 60, y + 70], radius=12, fill=BG_PANEL)
        dot_color = DOT_COLORS[i % len(DOT_COLORS)]
        draw.ellipse([80, y + 18, 112, y + 50], fill=dot_color)
        draw.text((96, y + 34), str(i + 1), font=_get_font(20, bold=True), fill=BG_DARK, anchor="mm")
        draw.text((138, y + 34), textwrap.shorten(point, width=38, placeholder="…"), font=_get_font(28), fill=WHITE, anchor="lm")

    _draw_footer(draw, data.get("conclusion", ""))
    img.save(output_path, format="PNG", optimize=True)


# ──────────────────────────────────────────────
# テンプレート2: list（箇条書き型）
# ──────────────────────────────────────────────

def _create_list(data: dict, output_path: str):
    """
    data keys: title, points(list[str] 最大5), conclusion
    """
    img, draw = _new_canvas()
    _draw_header(draw, data.get("title", ""))

    draw.text((W // 2, 98), data.get("title", ""), font=_get_font(36, bold=True), fill=WHITE, anchor="mm")

    # アクセントライン
    lx = W // 2
    draw.rectangle([lx - 180, 118, lx + 180, 122], fill=ACCENT)

    points = (data.get("points") or [])[:5]
    item_h = 84
    start_y = 138

    for i, point in enumerate(points):
        y = start_y + i * item_h
        _draw_rounded_rect(draw, [50, y, W - 50, y + item_h - 10], radius=10, fill=BG_PANEL)

        # 番号バッジ
        badge_color = DOT_COLORS[i % len(DOT_COLORS)]
        _draw_rounded_rect(draw, [66, y + 14, 108, y + 56], radius=8, fill=badge_color)
        draw.text((87, y + 35), str(i + 1), font=_get_font(22, bold=True), fill=BG_DARK, anchor="mm")

        # テキスト（最大40字で折り返し）
        short = textwrap.shorten(point, width=40, placeholder="…")
        draw.text((126, y + 35), short, font=_get_font(26), fill=WHITE, anchor="lm")

    _draw_footer(draw, data.get("conclusion", ""))
    img.save(output_path, format="PNG", optimize=True)


# ──────────────────────────────────────────────
# テンプレート3: comparison（比較型）
# ──────────────────────────────────────────────

def _create_comparison(data: dict, output_path: str):
    """
    data keys: title, left_label, right_label,
               left_points(list[str] 最大3), right_points(list[str] 最大3),
               conclusion
    """
    img, draw = _new_canvas()
    _draw_header(draw, data.get("title", ""))

    draw.text((W // 2, 98), data.get("title", ""), font=_get_font(34, bold=True), fill=WHITE, anchor="mm")

    # 中央分割線
    cx = W // 2
    draw.rectangle([cx - 2, 120, cx + 2, H - 70], fill=GRAY)

    # VS バッジ
    _draw_rounded_rect(draw, [cx - 28, 192, cx + 28, 242], radius=20, fill=ACCENT)
    draw.text((cx, 217), "VS", font=_get_font(26, bold=True), fill=BG_DARK, anchor="mm")

    # 左右ラベル
    left_label  = data.get("left_label", "A")
    right_label = data.get("right_label", "B")
    _draw_rounded_rect(draw, [60, 124, cx - 40, 168], radius=10, fill=GREEN)
    _draw_rounded_rect(draw, [cx + 40, 124, W - 60, 168], radius=10, fill=RED)
    draw.text(((60 + cx - 40) // 2, 146), left_label,  font=_get_font(28, bold=True), fill=WHITE, anchor="mm")
    draw.text(((cx + 40 + W - 60) // 2, 146), right_label, font=_get_font(28, bold=True), fill=WHITE, anchor="mm")

    # 左右ポイント
    left_pts  = (data.get("left_points")  or [])[:3]
    right_pts = (data.get("right_points") or [])[:3]
    for i in range(max(len(left_pts), len(right_pts))):
        y = 260 + i * 105

        if i < len(left_pts):
            _draw_rounded_rect(draw, [50, y, cx - 30, y + 86], radius=10, fill=BG_PANEL)
            draw.ellipse([68, y + 22, 96, y + 50], fill=GREEN)
            draw.text((82, y + 36), "✓", font=_get_font(18, bold=True), fill=WHITE, anchor="mm")
            wrapped = textwrap.fill(left_pts[i], width=16)
            draw.text((110, y + 43), wrapped, font=_get_font(22), fill=WHITE, anchor="lm")

        if i < len(right_pts):
            _draw_rounded_rect(draw, [cx + 30, y, W - 50, y + 86], radius=10, fill=BG_PANEL)
            draw.ellipse([cx + 48, y + 22, cx + 76, y + 50], fill=RED)
            draw.text((cx + 62, y + 36), "✓", font=_get_font(18, bold=True), fill=WHITE, anchor="mm")
            wrapped = textwrap.fill(right_pts[i], width=16)
            draw.text((cx + 90, y + 43), wrapped, font=_get_font(22), fill=WHITE, anchor="lm")

    _draw_footer(draw, data.get("conclusion", ""))
    img.save(output_path, format="PNG", optimize=True)


# ──────────────────────────────────────────────
# テンプレート4: ranking（ランキング型）
# ──────────────────────────────────────────────

def _create_ranking(data: dict, output_path: str):
    """
    data keys: title, items(list[{name, desc}] 最大5), conclusion
    """
    img, draw = _new_canvas()
    _draw_header(draw, data.get("title", ""))

    draw.text((W // 2, 98), data.get("title", ""), font=_get_font(36, bold=True), fill=WHITE, anchor="mm")

    items = (data.get("items") or [])[:5]
    item_h = 86
    start_y = 126

    for i, item in enumerate(items):
        y = start_y + i * item_h
        _draw_rounded_rect(draw, [50, y, W - 50, y + item_h - 8], radius=10, fill=BG_PANEL)

        # ランクバッジ
        rank_color = RANK_COLORS[i] if i < len(RANK_COLORS) else GRAY
        _draw_rounded_rect(draw, [62, y + 12, 108, y + 64], radius=8, fill=rank_color)
        rank_num = str(i + 1)
        draw.text((85, y + 38), rank_num, font=_get_font(28, bold=True), fill=BG_DARK, anchor="mm")

        # 名前 + 説明
        name = item.get("name", "")
        desc = item.get("desc", "")
        draw.text((128, y + 20), name, font=_get_font(26, bold=True), fill=WHITE, anchor="lm")
        draw.text((128, y + 52), textwrap.shorten(desc, width=44, placeholder="…"), font=_get_font(20), fill=GRAY, anchor="lm")

    _draw_footer(draw, data.get("conclusion", ""))
    img.save(output_path, format="PNG", optimize=True)


# ──────────────────────────────────────────────
# テンプレート5: grid（グリッド型）
# ──────────────────────────────────────────────

def _create_grid(data: dict, output_path: str):
    """
    参考: SOUL.md図解のような複数列概要まとめ型

    data keys:
      title: str
      columns: list of {
        header: str           (列タイトル 10字以内)
        color:  str           (optional: "cyan"/"green"/"red"/"yellow", default "cyan")
        items:  list of {
          text: str           (内容 20字以内)
          type: str           ("normal"/"good"/"bad", default "normal")
        }
      }
      conclusion: str
    """
    img, draw = _new_canvas()
    _draw_header(draw, data.get("title", ""))

    # タイトル
    draw.text((W // 2, 96), data.get("title", ""), font=_get_font(30, bold=True), fill=WHITE, anchor="mm")

    columns = (data.get("columns") or [])[:4]
    n = len(columns)
    if n == 0:
        img.save(output_path, format="PNG", optimize=True)
        return

    HEADER_COLORS = {
        "cyan":   ACCENT,
        "green":  GREEN,
        "red":    RED,
        "yellow": YELLOW,
    }

    margin_x = 40
    gap = 12
    col_w = (W - margin_x * 2 - gap * (n - 1)) // n
    start_y = 120
    header_h = 44
    item_h = 40
    body_y = start_y + header_h + 8

    for ci, col in enumerate(columns):
        cx = margin_x + ci * (col_w + gap)
        color_key = col.get("color", "cyan")
        hdr_color = HEADER_COLORS.get(color_key, ACCENT)

        # 列ヘッダー
        _draw_rounded_rect(draw, [cx, start_y, cx + col_w, start_y + header_h], radius=8, fill=hdr_color)
        draw.text(
            (cx + col_w // 2, start_y + header_h // 2),
            textwrap.shorten(col.get("header", ""), width=12, placeholder="…"),
            font=_get_font(22, bold=True), fill=BG_DARK, anchor="mm"
        )

        # 列本体パネル
        panel_h = H - 68 - body_y - 6
        _draw_rounded_rect(draw, [cx, body_y, cx + col_w, body_y + panel_h], radius=8, fill=BG_PANEL)

        items = (col.get("items") or [])[:9]
        for ii, item in enumerate(items):
            iy = body_y + 10 + ii * item_h
            if iy + item_h > body_y + panel_h - 4:
                break

            itype = item.get("type", "normal")
            if itype == "good":
                badge = "✓"
                badge_color = GREEN
            elif itype == "bad":
                badge = "✕"
                badge_color = RED
            else:
                badge = "•"
                badge_color = GRAY

            # バッジ
            draw.text((cx + 14, iy + item_h // 2), badge, font=_get_font(18, bold=True), fill=badge_color, anchor="lm")

            # テキスト
            short = textwrap.shorten(item.get("text", ""), width=int(col_w / 14), placeholder="…")
            draw.text((cx + 32, iy + item_h // 2), short, font=_get_font(18), fill=WHITE, anchor="lm")

    _draw_footer(draw, data.get("conclusion", ""))
    img.save(output_path, format="PNG", optimize=True)


# ──────────────────────────────────────────────
# 公開インターフェース
# ──────────────────────────────────────────────

def create_infographic(data: dict, output_path: str) -> None:
    """
    data["template"] の値でテンプレートを選択して生成。
    未指定または不明な場合は stat にフォールバック。
    """
    template = data.get("template", "stat")
    dispatch = {
        "stat":       _create_stat,
        "list":       _create_list,
        "comparison": _create_comparison,
        "ranking":    _create_ranking,
        "grid":       _create_grid,
    }
    fn = dispatch.get(template, _create_stat)
    fn(data, output_path)
