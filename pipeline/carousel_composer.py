"""
캐러셀 슬라이드 렌더러 (PIL). 1080x1350 (4:5) JPEG 슬라이드를 만듭니다.

- 표지: Figma MJ_1 디자인(풀블리드 이미지 + 검정 그라디언트 + MBTIJU 브랜드/헤드라인/슬로건)
- 본문: 릴스와 동일한 다크 그라디언트(#111121 -> #08080d) + accent(#FFBB40) 톤, 카드 박스 없이 배경에 직접 텍스트
- 마지막: CTA 슬라이드

릴스 레이아웃(`visual_gen.compose_reels_frame`)과는 별개의 렌더러입니다.
"""
import sys
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from pipeline.text_utils import wrap_by_pixel_width

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FONT_DIR = PROJECT_ROOT / "assets" / "fonts"

W, H = 1080, 1350
MARGIN_X = 90
ACCENT = (255, 187, 64)
BG_TOP = (17, 18, 28)
BG_BOTTOM = (8, 8, 13)
WHITE = (255, 255, 255)
SOFT = (205, 207, 220)


def _font_path() -> Optional[str]:
    for name in ("Pretendard-Bold.otf", "NanumGothic-Bold.ttf"):
        p = FONT_DIR / name
        if p.is_file():
            return str(p)
    return None


def _font(size: int) -> ImageFont.FreeTypeFont:
    fp = _font_path()
    try:
        return ImageFont.truetype(fp, size) if fp else ImageFont.load_default()
    except Exception:
        return ImageFont.load_default()


def _gradient_bg() -> Image.Image:
    img = Image.new("RGB", (W, H), BG_TOP)
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(BG_TOP[i] + (BG_BOTTOM[i] - BG_TOP[i]) * t) for i in range(3)))
    return img


def _fit_lines(text: str, max_w: int, max_h: int, start: int, min_size: int, line_ratio: float) -> Tuple[ImageFont.FreeTypeFont, List[str], int]:
    """max_w x max_h 안에 들어갈 때까지 폰트를 줄여가며 (font, lines, line_height)를 반환합니다."""
    size = start
    while True:
        font = _font(size)
        lines: List[str] = []
        for para in text.replace("\r", "").split("\n"):
            lines += wrap_by_pixel_width(para.strip(), font, max_w)
        line_h = int(size * line_ratio)
        if len(lines) * line_h <= max_h or size <= min_size:
            return font, lines, line_h
        size -= 4


def _draw_lines(d: ImageDraw.ImageDraw, lines: List[str], font, x: int, y: int, line_h: int, fill, anchor: str = "la", center_x: Optional[int] = None) -> int:
    for line in lines:
        if center_x is not None:
            d.text((center_x, y), line, font=font, fill=fill, anchor="ma")
        else:
            d.text((x, y), line, font=font, fill=fill, anchor=anchor)
        y += line_h
    return y


def _cover_crop(image_path: Path) -> Image.Image:
    """16:9 이미지를 4:5 캔버스에 꽉 차게(높이 기준 스케일 후 중앙 크롭) 맞춥니다."""
    img = Image.open(image_path).convert("RGB")
    scale = H / img.height
    img = img.resize((max(int(img.width * scale), W), H), Image.Resampling.LANCZOS)
    left = (img.width - W) // 2
    return img.crop((left, 0, left + W, H))


def _weight_font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    """Pretendard 웨이트별 폰트(Black/SemiBold). 파일이 없으면 Bold 계열로 대체."""
    p = FONT_DIR / f"Pretendard-{weight}.otf"
    try:
        return ImageFont.truetype(str(p), size) if p.is_file() else _font(size)
    except Exception:
        return _font(size)


def _tracked_width(text: str, font: ImageFont.FreeTypeFont, spacing: float) -> float:
    return sum(font.getlength(ch) + spacing for ch in text) - spacing if text else 0.0


def _draw_tracked(d: ImageDraw.ImageDraw, x: float, center_y: float, text: str, font, fill, spacing: float,
                  align: str = "left") -> None:
    """자간(letter-spacing, px)을 적용해 글자 단위로 그립니다. center_y는 줄 상자의 세로 중심."""
    asc, desc = font.getmetrics()
    baseline = center_y + (asc - desc) / 2
    if align == "right":
        x -= _tracked_width(text, font, spacing)
    for ch in text:
        d.text((x, baseline), ch, font=font, fill=fill, anchor="ls")
        x += font.getlength(ch) + spacing


def _wrap_tracked(text: str, font, max_w: int, spacing: float) -> List[str]:
    """공백 기준 단어 단위로 자간 포함 폭을 재서 줄바꿈(한 단어가 폭을 넘으면 글자 단위로 분할)."""
    lines: List[str] = []
    for para in text.replace("\r", "").split("\n"):
        cur = ""
        for word in para.split():
            cand = f"{cur} {word}".strip()
            if _tracked_width(cand, font, spacing) <= max_w:
                cur = cand
                continue
            if cur:
                lines.append(cur)
            cur = ""
            for ch in word:
                if cur and _tracked_width(cur + ch, font, spacing) > max_w:
                    lines.append(cur)
                    cur = ch
                else:
                    cur += ch
        if cur:
            lines.append(cur)
    return lines


# Figma "MJ_1" (node 292:180) 표지 스펙. 1080x1350, 모든 자간은 폰트 크기의 -5%.
COVER_BRAND = "MBTIJU"
COVER_SLOGAN = "MBTIJU: MBTI와 사주가 만나다."


def render_cover(headline: str, tag: str, cover_image: Optional[Path], out_path: Path, total: int) -> None:
    """표지 슬라이드: 이미지 없이 다크 그라디언트 배경에 제목만 정가운데 배치."""
    img = _gradient_bg()
    d = ImageDraw.Draw(img)

    clean_title = headline.replace("\r", "").replace("\n", " ").strip()
    text_w = W - MARGIN_X * 2  # 좌우 여백 90px씩 확보 (900px)

    # 제목 폰트 크기 자동 조절 (88px부터 시작, 3~4줄 이내로 화면 중앙에 맞춤)
    font, lines, line_h = _fit_lines(clean_title, text_w, 480, start=88, min_size=56, line_ratio=1.35)
    total_h = len(lines) * line_h
    start_y = (H - total_h) // 2

    # 제목 텍스트 그리기 (가로 중앙 W//2, 세로 중앙 start_y)
    _draw_lines(d, lines, font, MARGIN_X, start_y, line_h, WHITE, center_x=W // 2)

    img.save(out_path, "JPEG", quality=95)



def render_content(index: int, total: int, headline: str, body: str, out_path: Path, is_last: bool = False) -> None:
    img = _gradient_bg()
    d = ImageDraw.Draw(img)

    # 상단: 번호 + 진행도
    d.text((MARGIN_X, 110), f"{index:02d}", font=_font(76), fill=ACCENT, anchor="lm")
    d.text((W - MARGIN_X, 110), f"{index} / {total}", font=_font(32), fill=SOFT, anchor="rm")
    d.line([(MARGIN_X, 175), (W - MARGIN_X, 175)], fill=ACCENT, width=3)

    text_w = W - MARGIN_X * 2
    h_font, h_lines, h_lh = _fit_lines(headline, text_w, 380, start=76, min_size=52, line_ratio=1.3)
    y = 260
    y = _draw_lines(d, h_lines, h_font, MARGIN_X, y, h_lh, WHITE)

    if body.strip():
        y += 50
        b_font, b_lines, b_lh = _fit_lines(body, text_w, H - y - 200, start=46, min_size=32, line_ratio=1.55)
        _draw_lines(d, b_lines, b_font, MARGIN_X, y, b_lh, SOFT)

    footer = "저장  ·  팔로우  ·  공유" if is_last else "다음 장  →"
    d.text((W // 2, H - 90), footer, font=_font(34), fill=ACCENT, anchor="mm")
    img.save(out_path, "JPEG", quality=95)


def render_last_slide(out_path: Path) -> bool:
    """캐러셀 마지막 장: 고정 CTA 프로필 안내 이미지(assets/templates/carousel_cta.png)를 1080x1350으로 렌더링합니다."""
    cta_path = PROJECT_ROOT / "assets" / "templates" / "carousel_cta.png"
    if cta_path.is_file():
        img = Image.open(cta_path).convert("RGBA")
        canvas = Image.new("RGB", (W, H), (255, 255, 255))
        scale = min(W / img.width, H / img.height)
        nw, nh = int(img.width * scale), int(img.height * scale)
        img_resized = img.resize((nw, nh), Image.Resampling.LANCZOS)
        ox, oy = (W - nw) // 2, (H - nh) // 2
        canvas.paste(img_resized, (ox, oy), mask=img_resized.split()[3] if img_resized.mode == "RGBA" else None)
        canvas.save(out_path, "JPEG", quality=95)
        return True
    return False


def render_carousel(script, output_dir: str | Path, cover_image: Optional[str | Path] = None, tag: str = "MBTI x 사주 트렌드") -> List[str]:
    """CarouselScript를 슬라이드 JPEG 목록으로 렌더링하고 경로 리스트를 반환합니다."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("slide_*.jpg"):
        old.unlink()

    slides = script.slides
    total = len(slides)
    paths: List[str] = []
    for i, sl in enumerate(slides, 1):
        out = out_dir / f"slide_{i:02d}.jpg"
        if i == 1:
            render_cover(sl.headline, tag, Path(cover_image) if cover_image else None, out, total)
        elif i == total:
            # 마지막 장은 사용자가 지정한 고정 프로필 CTA 이미지로 렌더링
            if not render_last_slide(out):
                render_content(i, total, sl.headline, sl.body, out, is_last=True)
        else:
            render_content(i, total, sl.headline, sl.body, out, is_last=False)
        paths.append(str(out.resolve()))
        print(f"  ✅ 슬라이드 {i}/{total} 렌더 완료 -> {out.name}")
    return paths
