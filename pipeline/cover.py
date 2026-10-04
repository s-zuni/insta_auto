"""
릴스 커버 프레임 생성 (1080x1920).

프로필 그리드는 세로 중앙 3:4(1080x1440, y=240~1680)만 잘라 보여주므로, 제목은 그 안쪽 안전 영역에
배치합니다. 배경은 씬 1의 16:9 원본 비주얼(합성 전)을 꽉 차게 중앙 크롭 + 어두운 오버레이입니다.
릴스 본편 프레임 레이아웃(`visual_gen.compose_reels_frame`)과는 별개입니다.
"""
import sys
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from pipeline.text_utils import wrap_by_pixel_width

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
W, H = 1080, 1920
ACCENT = (255, 187, 64)
SAFE_TOP, SAFE_BOTTOM = 240, 1680  # 그리드 3:4 크롭 기준 안전 영역


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
) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if raw_image and Path(raw_image).is_file():
        img = Image.open(raw_image).convert("RGB")
        scale = H / img.height
        img = img.resize((max(int(img.width * scale), W), H), Image.Resampling.LANCZOS)
        left = (img.width - W) // 2
        img = img.crop((left, 0, left + W, H))
        overlay = Image.new("RGBA", (W, H), (8, 8, 13, 150))
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    else:
        img = Image.new("RGB", (W, H), (17, 18, 28))

    d = ImageDraw.Draw(img)
    clean = title.replace("\n", " ").strip()

    # 제목 폰트 크기: 기존 112에서 약 1.3배 증가한 146부터 시작
    size = 146
    while True:
        font = _font(size)
        lines = wrap_by_pixel_width(clean, font, W - 160) or [clean]
        line_h = int(size * 1.25)
        if (len(lines) <= 4 and len(lines) * line_h <= 680) or size <= 88:
            break
        size -= 6
    lines = lines[:4]

    block_h = len(lines) * line_h
    center_y = (SAFE_TOP + SAFE_BOTTOM) // 2
    y = center_y - block_h // 2

    # 태그 [ MBTI x 사주 트렌드 ] 및 밑줄은 출력하지 않음
    stroke_w = max(5, int(size * 0.045))
    for line in lines:
        d.text((W // 2, y), line, font=font, fill=(255, 255, 255), anchor="ma",
               stroke_width=stroke_w, stroke_fill=(0, 0, 0))
        y += line_h

    img.save(out_path, "JPEG", quality=95)
    return out_path
