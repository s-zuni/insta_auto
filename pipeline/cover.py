"""
High-CTR Curiosity-Driven Reels / Shorts Cover Generator (1080x1920).
Optimized for the Instagram Profile Grid 3:4 crop window (1080x1440, Y=240..1680)
and mobile Reels/Shorts browse feeds.

Features:
- Authentic 9:16 portrait visual background with cinematic keylight enhancement
- Top Curiosity Trigger Pill Badge (Y=290, safe from 3:4 grid crop)
- Sub-hook Teaser Tape (Y=1010)
- 2-Tone Giant Impact Typography: White setup + Electric Gold punchline (Y=1080..1520)
- Heavy stroke & deep multi-layered drop shadow for 100% readability across any background
"""
import sys
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageEnhance

from pipeline.text_utils import sanitize_title, wrap_by_pixel_width
from pipeline.visual_gen import infer_curiosity_badge

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
W, H = 1080, 1920
SAFE_TOP, SAFE_BOTTOM = 240, 1680  # Instagram 3:4 Grid Crop Window


def _font(size: int) -> ImageFont.FreeTypeFont:
    for name in ("Pretendard-Bold.otf", "NanumGothic-Bold.ttf"):
        p = PROJECT_ROOT / "assets" / "fonts" / name
        if p.is_file():
            try:
                return ImageFont.truetype(str(p), size)
            except Exception:
                continue
    return ImageFont.load_default()


def build_reel_cover(
    raw_image: Optional[str | Path],
    title: str,
    out_path: str | Path,
    category_tag: str = "",
    hook_text: str = "",
) -> Path:
    """
    호기심을 극대화하여 클릭률(CTR)과 프로필 방문 전환을 끌어올리는
    1080x1920 풀스크린 숏츠/릴스 썸네일(커버)을 생성합니다.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. 배경 이미지 준비 (실제 씬 비주얼 활용 또는 시네마틱 딥 다크 그라데이션)
    base_img = None
    if raw_image:
        raw_p = Path(raw_image)
        if raw_p.is_file():
            try:
                loaded = Image.open(raw_p).convert("RGB")
                # 인물 얼굴이 있는 상단 35% 중심으로 1080x1920 세로 핏
                base_img = ImageOps.fit(
                    loaded, (W, H), method=Image.Resampling.LANCZOS, centering=(0.5, 0.35)
                )
                # 모바일 피드에서 눈길을 끌도록 대비 및 채도 강조
                base_img = ImageEnhance.Contrast(base_img).enhance(1.14)
                base_img = ImageEnhance.Color(base_img).enhance(1.16)
            except Exception as e:
                print(f"[COVER][WARN] 원본 이미지 로드 실패({e}), 그래디언트 생성으로 대체")
                base_img = None

    if base_img is None:
        BG_TOP = (20, 22, 36)
        BG_BOTTOM = (6, 7, 12)
        base_img = Image.new("RGB", (W, H), BG_TOP)
        d_bg = ImageDraw.Draw(base_img)
        for y_pos in range(H):
            t = y_pos / H
            r = int(BG_TOP[0] + (BG_BOTTOM[0] - BG_TOP[0]) * t)
            g = int(BG_TOP[1] + (BG_BOTTOM[1] - BG_TOP[1]) * t)
            b = int(BG_TOP[2] + (BG_BOTTOM[2] - BG_TOP[2]) * t)
            d_bg.line([(0, y_pos), (W, y_pos)], fill=(r, g, b))

    # 2. 시네마틱 비네팅 오버레이 (얼굴은 밝게 살리고 텍스트 영역 Y=920..1920은 짙은 그라데이션)
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d_ov = ImageDraw.Draw(overlay)

    # 상단 안전 비네팅 (Y=0..380)
    for y in range(380):
        t = 1.0 - (y / 380)
        d_ov.line([(0, y), (W, y)], fill=(6, 7, 14, int(180 * (t ** 1.3))))

    # 하단 텍스트 가독성 비네팅 (Y=880..1920)
    bot_start = 880
    for y in range(bot_start, H):
        t = (y - bot_start) / (H - bot_start)
        d_ov.line([(0, y), (W, y)], fill=(5, 6, 12, int(245 * (t ** 1.15))))

    # 3. 상단 호기심 자극 알림 뱃지 (Y=295, 3:4 그리드 Y=240 안쪽 안전 영역)
    badge_text = category_tag.strip() if category_tag.strip() else infer_curiosity_badge(title)
    badge_font = _font(42)
    bbox_b = d_ov.textbbox((0, 0), badge_text, font=badge_font)
    bw, bh = bbox_b[2] - bbox_b[0], bbox_b[3] - bbox_b[1]
    px, py = 38, 16
    pill_w = bw + px * 2
    pill_h = bh + py * 2
    pill_x0 = (W - pill_w) // 2
    pill_y0 = 295

    # 네온 글로우 테두리
    d_ov.rounded_rectangle(
        [pill_x0 - 2, pill_y0 - 2, pill_x0 + pill_w + 2, pill_y0 + pill_h + 2],
        radius=pill_h // 2 + 2,
        outline=(255, 75, 110, 180),
        width=2,
    )
    d_ov.rounded_rectangle(
        [pill_x0, pill_y0, pill_x0 + pill_w, pill_y0 + pill_h],
        radius=pill_h // 2,
        fill=(15, 16, 28, 235),
        outline=(255, 212, 59, 255),
        width=3,
    )
    d_ov.text(
        (W // 2, pill_y0 + pill_h // 2),
        badge_text,
        font=badge_font,
        fill=(255, 224, 102, 255),
        anchor="mm",
    )

    # 4. 서브 훅 티저 태그 (Y=1005)
    teaser_text = "설마 나도 해당될까?"
    if hook_text and "3개" in hook_text:
        teaser_text = "3개 이상 맞으면 진짜 100%"
    elif hook_text and "손절" in hook_text:
        teaser_text = "겉은 다정한데 속은 칼같다?"

    teaser_font = _font(38)
    bbox_t = d_ov.textbbox((0, 0), teaser_text, font=teaser_font)
    tw, th = bbox_t[2] - bbox_t[0], bbox_t[3] - bbox_t[1]
    t_px, t_py = 28, 12
    t_w = tw + t_px * 2
    t_h = th + t_py * 2
    t_x0 = (W - t_w) // 2
    t_y0 = 1005
    d_ov.rounded_rectangle(
        [t_x0, t_y0, t_x0 + t_w, t_y0 + t_h],
        radius=14,
        fill=(255, 224, 102, 245),
    )
    d_ov.text(
        (W // 2, t_y0 + t_h // 2),
        teaser_text,
        font=teaser_font,
        fill=(16, 17, 28, 255),
        anchor="mm",
    )

    # 5. 거대 2톤 임팩트 타이포그래피 (Y=1090..1520, 3:4 그리드 Y=1680 안쪽)
    clean = sanitize_title(title).replace("\n", " ").strip()
    size = 126
    while True:
        font = _font(size)
        lines = wrap_by_pixel_width(clean, font, W - 140) or [clean]
        line_h = int(size * 1.22)
        if (len(lines) <= 2 and len(lines) * line_h <= 380) or size <= 78:
            break
        size -= 6
    lines = lines[:2]

    # 1줄일 경우 시각적 임팩트를 위해 2줄 분할
    if len(lines) == 1:
        words = lines[0].split()
        if len(words) >= 3:
            mid = len(words) // 2
            lines = [" ".join(words[:mid]), " ".join(words[mid:])]

    title_start_y = t_y0 + t_h + 35
    line_h = int(size * 1.24)
    stroke_w = max(7, int(size * 0.08))

    for idx, line in enumerate(lines):
        y_pos = title_start_y + idx * line_h
        # 마지막 줄(핵심 키워드)은 일렉트릭 골드, 첫 줄은 화이트
        fill_color = (255, 220, 68, 255) if (len(lines) > 1 and idx == len(lines) - 1) else (255, 255, 255, 255)

        # 3중 다중 드롭 섀도우 (피드에서 1초 만에 튀어나오는 입체감)
        for dx, dy in [(0, 8), (4, 10), (-3, 10)]:
            d_ov.text(
                (W // 2 + dx, y_pos + dy),
                line,
                font=font,
                fill=(0, 0, 0, 200),
                anchor="mt",
                stroke_width=stroke_w + 4,
                stroke_fill=(0, 0, 0, 200),
            )
        # 메인 텍스트 렌더링
        d_ov.text(
            (W // 2, y_pos),
            line,
            font=font,
            fill=fill_color,
            anchor="mt",
            stroke_width=stroke_w,
            stroke_fill=(6, 7, 12, 255),
        )

    # 6. 알파 합성 및 최종 JPEG 저장
    final_img = Image.alpha_composite(base_img.convert("RGBA"), overlay).convert("RGB")
    final_img.save(out_path, "JPEG", quality=96)
    print(f"[COVER] ✅ 호기심 극대화 9:16 고CTR 썸네일 생성 완료 -> {out_path.name}")
    return out_path
