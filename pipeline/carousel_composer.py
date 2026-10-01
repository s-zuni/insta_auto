"""
캐러셀 슬라이드 렌더러 (PIL). 1080x1350 (4:5) JPEG 슬라이드를 만듭니다.

- 표지: 16:9로 생성한 비주얼을 4:5로 중앙 크롭 + 어두운 오버레이 위에 훅 헤드라인
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


def render_cover(headline: str, tag: str, cover_image: Optional[Path], out_path: Path, total: int) -> None:
    if cover_image and cover_image.is_file():
        img = _cover_crop(cover_image)
        # 아래로 갈수록 어두워지는 오버레이로 흰 글씨 가독성 확보
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)
        for y in range(H):
            alpha = int(90 + 140 * (y / H))
            od.line([(0, y), (W, y)], fill=(8, 8, 13, min(alpha, 235)))
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    else:
        img = _gradient_bg()

    d = ImageDraw.Draw(img)
    d.text((W // 2, 120), f"[ {tag} ]", font=_font(34), fill=ACCENT, anchor="mm")

    font, lines, line_h = _fit_lines(headline, W - MARGIN_X * 2, 520, start=104, min_size=64, line_ratio=1.28)
    block_h = len(lines) * line_h
    y = (H - block_h) // 2 + 60
    _draw_lines(d, lines, font, MARGIN_X, y, line_h, WHITE, center_x=W // 2)

    d.line([(W // 2 - 60, y - 40), (W // 2 + 60, y - 40)], fill=ACCENT, width=5)
    d.text((W // 2, H - 110), "넘겨서 확인하기  →", font=_font(36), fill=ACCENT, anchor="mm")
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
        else:
            render_content(i, total, sl.headline, sl.body, out, is_last=(i == total))
        paths.append(str(out.resolve()))
        print(f"  ✅ 슬라이드 {i}/{total} 렌더 완료 -> {out.name}")
    return paths
