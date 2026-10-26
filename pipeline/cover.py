"""
High-CTR Curiosity-Driven Reels / Shorts Cover Generator (1080x1920).
Optimized for mbtiju.com: Bold Minimalist Typography centered in the
Instagram Profile Grid 3:4 crop window (1080x1440, Y=240..1680).

Features:
- Dimmed cinematic background visual for 100% text clarity and zero distraction
- Top Personalized Target Pill Badge (Y=340..420, e.g. '[ 98년생 × INFP ]', '[ 00년생 용띠 × ESFJ ]')
- Center Giant 2-Tone Impact Typography (Y=560..1060): Pure White setup + Electric Gold punchline
- Sub-hook Teaser Tape (Y=1140)
- Bottom Brand Trust Pill (Y=1460): '[ mbtiju 사주 심층 분석 ]'
- Triple deep drop shadows for instant 0.3s feed scroll-stopping power
"""
import re
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


def _font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    names = ("Pretendard-Black.otf", "Pretendard-Bold.otf", "NanumGothic-Bold.ttf") if bold else ("Pretendard-SemiBold.otf", "Pretendard-Bold.otf")
    for name in names:
        p = PROJECT_ROOT / "assets" / "fonts" / name
        if p.is_file():
            try:
                return ImageFont.truetype(str(p), size)
            except Exception:
                continue
    return ImageFont.load_default()


def infer_mbtiju_badge(title: str, category_tag: str = "") -> str:
    """제목에서 출생연도, 띠, 일간, MBTI를 자동 추출하여 핀셋 타겟 뱃지 텍스트를 만듭니다."""
    if category_tag.strip():
        return category_tag.strip()
    t = title.upper()

    found_year = ""
    for y in ("94년생", "95년생", "96년생", "97년생", "98년생", "99년생", "00년생", "01년생", "02년생", "03년생", "04년생"):
        if y in title:
            found_year = y
            break

    found_mbti = ""
    for m in ("INTJ", "INTP", "ENTJ", "ENTP", "INFJ", "INFP", "ENFJ", "ENFP",
              "ISTJ", "ISFJ", "ESTJ", "ESFJ", "ISTP", "ISFP", "ESTP", "ESFP"):
        if m in t:
            found_mbti = m
            break

    found_zodiac = ""
    for z in ("용띠", "호랑이띠", "범띠", "토끼띠", "소띠", "개띠", "돼지띠", "쥐띠", "뱀띠", "말띠", "양띠", "원숭이띠", "닭띠"):
        if z in title:
            found_zodiac = z
            break

    found_dm = ""
    for d in ("갑목", "을목", "병화", "정화", "무토", "기토", "경금", "신금", "임수", "계수"):
        if d in title:
            found_dm = d
            break

    if found_year and found_zodiac and found_mbti:
        return f"[ {found_year} {found_zodiac} × {found_mbti} ]"
    if found_year and found_dm and found_mbti:
        return f"[ {found_year} {found_dm} × {found_mbti} ]"
    if found_year and found_mbti:
        return f"[ {found_year} × {found_mbti} ]"
    if found_zodiac and found_mbti:
        return f"[ {found_zodiac} × {found_mbti} ]"
    if found_dm and found_mbti:
        return f"[ {found_dm} × {found_mbti} ]"
    if "TOP" in t or "조합" in title:
        return "[ 2026 대박 사주×MBTI 조합 ]"
    return infer_curiosity_badge(title)


def build_reel_cover(
    raw_image: Optional[str | Path],
    title: str,
    out_path: str | Path,
    category_tag: str = "",
    hook_text: str = "",
) -> Path:
    """
    심플 텍스트 중심형(Bold Minimalist Typography):
    이미지 비중을 어둡게 눌러 가독성을 100% 확보하고,
    타겟 조합(연도/띠+MBTI)과 핵심 카피를 화면 전체에 거대하게 부각시킵니다.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. 딥 차콜-네이비 그라데이션 및 비주얼 배경 세팅
    base_img = None
    if raw_image:
        raw_p = Path(raw_image)
        if raw_p.is_file():
            try:
                loaded = Image.open(raw_p).convert("RGB")
                base_img = ImageOps.fit(
                    loaded, (W, H), method=Image.Resampling.LANCZOS, centering=(0.5, 0.35)
                )
                # 텍스트가 돋보이도록 이미지를 어둡고 차분하게 누름
                base_img = ImageEnhance.Brightness(base_img).enhance(0.42)
                base_img = ImageEnhance.Contrast(base_img).enhance(1.22)
            except Exception as e:
                print(f"[COVER][WARN] 원본 이미지 로드 실패({e}), 그래디언트 생성으로 대체")
                base_img = None

    if base_img is None:
        BG_TOP = (16, 18, 28)
        BG_BOTTOM = (7, 8, 14)
        base_img = Image.new("RGB", (W, H), BG_TOP)
        d_bg = ImageDraw.Draw(base_img)
        for y_pos in range(H):
            t = y_pos / H
            r = int(BG_TOP[0] + (BG_BOTTOM[0] - BG_TOP[0]) * t)
            g = int(BG_TOP[1] + (BG_BOTTOM[1] - BG_TOP[1]) * t)
            b = int(BG_TOP[2] + (BG_BOTTOM[2] - BG_TOP[2]) * t)
            d_bg.line([(0, y_pos), (W, y_pos)], fill=(r, g, b))

    # 2. 풀스크린 다크 비네팅 오버레이 (텍스트 가독성 극대화)
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d_ov = ImageDraw.Draw(overlay)

    # 3:4 그리드 영역(Y=240..1680) 텍스트 배경을 짙은 다크로 블렌딩
    for y in range(H):
        t_center = abs(y - 960) / 960.0
        alpha = int(140 + 80 * (1.0 - t_center))
        d_ov.line([(0, y), (W, y)], fill=(8, 9, 16, alpha))

    # 3. 상단 개인화 타겟 뱃지 (Y=350, 3:4 그리드 Y=240 안쪽 안전 영역)
    badge_text = infer_mbtiju_badge(title, category_tag)
    badge_font = _font(46, bold=True)
    bbox_b = d_ov.textbbox((0, 0), badge_text, font=badge_font)
    bw, bh = bbox_b[2] - bbox_b[0], bbox_b[3] - bbox_b[1]
    px, py = 42, 18
    pill_w = bw + px * 2
    pill_h = bh + py * 2
    pill_x0 = (W - pill_w) // 2
    pill_y0 = 350

    # 뱃지 골드 네온 테두리 & 배경
    d_ov.rounded_rectangle(
        [pill_x0 - 2, pill_y0 - 2, pill_x0 + pill_w + 2, pill_y0 + pill_h + 2],
        radius=pill_h // 2 + 2,
        outline=(255, 212, 59, 210),
        width=2,
    )
    d_ov.rounded_rectangle(
        [pill_x0, pill_y0, pill_x0 + pill_w, pill_y0 + pill_h],
        radius=pill_h // 2,
        fill=(14, 15, 25, 245),
        outline=(255, 224, 102, 255),
        width=3,
    )
    d_ov.text(
        (W // 2, pill_y0 + pill_h // 2),
        badge_text,
        font=badge_font,
        fill=(255, 224, 102, 255),
        anchor="mm",
    )

    # 4. 거대 2톤 임팩트 타이포그래피 (화면 중앙 Y=560..1060 집중 배치)
    clean = sanitize_title(title).replace("\n", " ").strip()
    # 뱃지에 들어간 연도/MBTI 문구는 메인 헤드라인에서 중복 제거하여 더 큰 글씨로 핵심 키워드 강조
    main_text = clean
    for tag_item in ("98년생", "00년생", "97년생", "99년생", "95년생", "96년생", "01년생", "02년생", "03년생", "04년생",
                     "용띠", "소띠", "토끼띠", "호랑이띠", "개띠", "돼지띠", "쥐띠"):
        if tag_item in main_text and len(main_text) > 10:
            main_text = main_text.replace(tag_item, "").strip()

    size = 142
    while True:
        font = _font(size, bold=True)
        lines = wrap_by_pixel_width(main_text, font, W - 120) or [main_text]
        line_h = int(size * 1.22)
        if (len(lines) <= 2 and len(lines) * line_h <= 450) or size <= 84:
            break
        size -= 6
    lines = lines[:2]

    if len(lines) == 1:
        words = lines[0].split()
        if len(words) >= 3:
            mid = len(words) // 2
            lines = [" ".join(words[:mid]), " ".join(words[mid:])]

    title_start_y = 590
    line_h = int(size * 1.25)
    stroke_w = max(8, int(size * 0.08))

    for idx, line in enumerate(lines):
        y_pos = title_start_y + idx * line_h
        # 마지막 줄(핵심 키워드)은 일렉트릭 골드, 첫 줄은 화이트
        fill_color = (255, 220, 68, 255) if (len(lines) > 1 and idx == len(lines) - 1) else (255, 255, 255, 255)

        # 3중 다중 드롭 섀도우 (피드에서 1초 만에 튀어나오는 입체감)
        for dx, dy in [(0, 10), (4, 12), (-4, 12)]:
            d_ov.text(
                (W // 2 + dx, y_pos + dy),
                line,
                font=font,
                fill=(0, 0, 0, 220),
                anchor="mt",
                stroke_width=stroke_w + 6,
                stroke_fill=(0, 0, 0, 220),
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

    # 5. 서브 훅 티저 태그 (Y=1140)
    teaser_text = "올해 이 타이밍 놓치면 평생 후회"
    if hook_text and "3개" in hook_text:
        teaser_text = "3개 이상 맞으면 진짜 100%"
    elif hook_text and "손절" in hook_text:
        teaser_text = "겉은 다정한데 속은 칼같다?"
    elif "결혼" in title or "연애" in title:
        teaser_text = "올해 하반기 인연 타이밍 공개"
    elif "이직" in title or "돈" in title or "직장" in title:
        teaser_text = "2026년 대운 터지는 결정적 신호"

    teaser_font = _font(40, bold=True)
    bbox_t = d_ov.textbbox((0, 0), teaser_text, font=teaser_font)
    tw, th = bbox_t[2] - bbox_t[0], bbox_t[3] - bbox_t[1]
    t_px, t_py = 32, 14
    t_w = tw + t_px * 2
    t_h = th + t_py * 2
    t_x0 = (W - t_w) // 2
    t_y0 = 1140
    d_ov.rounded_rectangle(
        [t_x0, t_y0, t_x0 + t_w, t_y0 + t_h],
        radius=14,
        fill=(255, 224, 102, 245),
    )
    d_ov.text(
        (W // 2, t_y0 + t_h // 2),
        teaser_text,
        font=teaser_font,
        fill=(14, 15, 24, 255),
        anchor="mm",
    )

    # 6. 하단 브랜드 신뢰 뱃지 (Y=1460, 3:4 그리드 하단 안전 영역)
    brand_text = "[ mbtiju.com 심층 사주 분석 ]"
    brand_font = _font(34, bold=False)
    d_ov.text(
        (W // 2, 1460),
        brand_text,
        font=brand_font,
        fill=(190, 200, 220, 200),
        anchor="mm",
    )

    # 7. 알파 합성 및 최종 JPEG 저장
    final_img = Image.alpha_composite(base_img.convert("RGBA"), overlay).convert("RGB")
    final_img.save(out_path, "JPEG", quality=96)
    print(f"[COVER] ✅ mbtiju 맞춤 텍스트 중심형 썸네일 생성 완료 -> {out_path.name}")
    return out_path
