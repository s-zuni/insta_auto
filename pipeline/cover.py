"""
High-CTR Single-Focus Reels / Shorts Cover Generator (1080x1920).
Optimized for mbtiju.com: Minimalist, High-Impact 2-Tone Typography centered
in the Instagram Profile Grid 3:4 crop window (1080x1440, Y=240..1680)
and 1:1 feed square (1080x1080, Y=420..1500).

Core Philosophy:
- Zero Distraction: 잡다한 알약 뱃지, 테이프, 자잘한 서브 카피를 전면 삭제.
- Single Focus: 오직 하나의 거대 2톤 헤드라인에 0.1초 만에 시선이 꽂히는 극상의 가독성.
- Setup (White) + Punchline (Electric Gold) 2-Tone Visual Contrast.
"""
import re
import sys
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageEnhance

from pipeline.text_utils import sanitize_title, wrap_natural_title
from pipeline.visual_gen import infer_curiosity_badge

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
W, H = 1080, 1920


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
    """제목에서 출생연도, 띠, 일간, MBTI를 자동 추출하여 미니멀한 타겟 태그 문구를 만듭니다."""
    if category_tag.strip():
        clean_tag = category_tag.strip().strip("[] ")
        return f"✦ {clean_tag} ✦"
    t = (title or "").upper()

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
        return f"✦ {found_year} {found_zodiac} × {found_mbti} ✦"
    if found_year and found_dm and found_mbti:
        return f"✦ {found_year} {found_dm} × {found_mbti} ✦"
    if found_year and found_mbti:
        return f"✦ {found_year} × {found_mbti} ✦"
    if found_zodiac and found_mbti:
        return f"✦ {found_zodiac} × {found_mbti} ✦"
    if found_dm and found_mbti:
        return f"✦ {found_dm} × {found_mbti} ✦"
    if found_mbti:
        return f"✦ {found_mbti} 사주 심층 분석 ✦"
    if "TOP" in t or "조합" in title:
        return "✦ 2026 대박 사주 × MBTI 조합 ✦"

    raw_badge = infer_curiosity_badge(title).strip("[] ")
    return f"✦ {raw_badge} ✦"


def build_reel_cover(
    raw_image: Optional[str | Path],
    title: str,
    out_path: str | Path,
    category_tag: str = "",
    hook_text: str = "",
) -> Path:
    """
    단일 시선 집중형(Single-Focus High-CTR) 릴스/숏츠 썸네일 생성기.
    - 산만한 부가 요소(테이프, 서브박스, 다중 알약)를 제거하고,
    - 0.3초 만에 스크롤을 멈추는 초대형 2톤 타이포그래피(화이트 셋업 + 일렉트릭 골드 펀치라인)로 화면 압도.
    - 3:4 그리드(인스타 프로필) 및 1:1 그리드(피드) 어디서든 완벽하게 노출.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. 딥 시네마틱 배경 준비 (어둡고 차분하게 눌러 텍스트 가독성 100% 확보)
    base_img = None
    if raw_image:
        raw_p = Path(raw_image)
        if raw_p.is_file():
            try:
                loaded = Image.open(raw_p).convert("RGB")
                base_img = ImageOps.fit(
                    loaded, (W, H), method=Image.Resampling.LANCZOS, centering=(0.5, 0.35)
                )
                base_img = ImageEnhance.Brightness(base_img).enhance(0.38)
                base_img = ImageEnhance.Contrast(base_img).enhance(1.25)
            except Exception as e:
                print(f"[COVER][WARN] 원본 이미지 로드 실패({e}), 그래디언트 생성으로 대체")
                base_img = None

    if base_img is None:
        BG_TOP = (15, 16, 26)
        BG_BOTTOM = (6, 7, 12)
        base_img = Image.new("RGB", (W, H), BG_TOP)
        d_bg = ImageDraw.Draw(base_img)
        for y_pos in range(H):
            t = y_pos / H
            r = int(BG_TOP[0] + (BG_BOTTOM[0] - BG_TOP[0]) * t)
            g = int(BG_TOP[1] + (BG_BOTTOM[1] - BG_TOP[1]) * t)
            b = int(BG_TOP[2] + (BG_BOTTOM[2] - BG_TOP[2]) * t)
            d_bg.line([(0, y_pos), (W, y_pos)], fill=(r, g, b))

    # 2. 풀스크린 시네마틱 비네팅 오버레이 (화면 중앙 집중)
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d_ov = ImageDraw.Draw(overlay)

    # 3:4 그리드 영역(Y=240..1680) 텍스트 배경을 짙고 부드럽게 감싸는 다크 그라데이션
    for y in range(H):
        t_center = abs(y - 940) / 940.0
        alpha = int(170 + 75 * (1.0 - min(t_center, 1.0)))
        d_ov.line([(0, y), (W, y)], fill=(6, 7, 13, alpha))

    # 3. 상단 미니멀 타겟 캡슐 태그 (Y=390, 모던하고 절제된 형태)
    badge_text = infer_mbtiju_badge(title, category_tag)
    badge_font = _font(38, bold=True)
    bbox_b = d_ov.textbbox((0, 0), badge_text, font=badge_font)
    bw, bh = bbox_b[2] - bbox_b[0], bbox_b[3] - bbox_b[1]
    px, py = 32, 14
    pill_w = bw + px * 2
    pill_h = bh + py * 2
    pill_x0 = (W - pill_w) // 2
    pill_y0 = 390

    # 은은하고 모던한 반투명 다크 캡슐
    d_ov.rounded_rectangle(
        [pill_x0, pill_y0, pill_x0 + pill_w, pill_y0 + pill_h],
        radius=pill_h // 2,
        fill=(18, 20, 32, 220),
        outline=(255, 218, 90, 180),
        width=2,
    )
    d_ov.text(
        (W // 2, pill_y0 + pill_h // 2),
        badge_text,
        font=badge_font,
        fill=(255, 224, 102, 255),
        anchor="mm",
    )

    # 4. 화면 정중앙 초대형 2톤 임팩트 타이포그래피 (Y=620..1060)
    # 제목 원본의 후킹성을 훼손하지 않고 온전하게 노출 (임의 단어 삭제 방지!)
    clean_title = sanitize_title(title).replace("\n", " ").strip()
    max_title_w = W - 140  # 좌우 70px씩 시원한 여백

    title_size = 126
    while True:
        font = _font(title_size, bold=True)
        lines = wrap_natural_title(clean_title, font, max_title_w, max_lines=2) or [clean_title]
        line_h = int(title_size * 1.28)
        if (len(lines) <= 2 and len(lines) * line_h <= 380) or title_size <= 86:
            break
        title_size -= 4

    lines = lines[:2]
    # 만약 한 줄인데 어절이 3개 이상이면 시각적 리듬감을 위해 2줄 분할
    if len(lines) == 1:
        words = lines[0].split()
        if len(words) >= 3:
            mid = len(words) // 2
            lines = [" ".join(words[:mid]), " ".join(words[mid:])]

    # 세로 중심 맞춤 (3:4 그리드 및 1:1 정사각 그리드의 완벽한 중앙)
    total_text_h = len(lines) * line_h
    title_start_y = 660 if len(lines) >= 2 else 720
    stroke_w = max(8, int(title_size * 0.08))

    for idx, line in enumerate(lines):
        y_pos = title_start_y + idx * line_h
        # 1줄: 순백색 셋업(White), 2줄: 하이볼티지 일렉트릭 골드 펀치라인(Electric Gold)
        fill_color = (255, 226, 38, 255) if (len(lines) > 1 and idx == len(lines) - 1) else (255, 255, 255, 255)

        # 또렷하고 단단한 딥 섀도우 (피드에서 글자가 칼같이 튀어나오는 시인성)
        d_ov.text(
            (W // 2, y_pos + 10),
            line,
            font=font,
            fill=(0, 0, 0, 230),
            anchor="mt",
            stroke_width=stroke_w + 4,
            stroke_fill=(0, 0, 0, 230),
        )
        # 메인 타이포 렌더링
        d_ov.text(
            (W // 2, y_pos),
            line,
            font=font,
            fill=fill_color,
            anchor="mt",
            stroke_width=stroke_w,
            stroke_fill=(5, 6, 10, 255),
        )

    # 5. 하단 미니멀 브랜드 워터마크 (Y=1460, 3:4 그리드 하단 안전 영역)
    # 기존의 잡다한 테이프/뱃지를 걷어내고 세련된 한 줄 브랜딩만 은은하게 유지
    brand_text = "✦ mbtiju.com 사주 × MBTI 심층 분석 ✦"
    brand_font = _font(30, bold=False)
    d_ov.text(
        (W // 2, 1460),
        brand_text,
        font=brand_font,
        fill=(190, 202, 225, 170),
        anchor="mm",
    )

    # 6. 알파 합성 및 최종 고화질 JPEG 저장
    final_img = Image.alpha_composite(base_img.convert("RGBA"), overlay).convert("RGB")
    final_img.save(out_path, "JPEG", quality=96)
    print(f"[COVER] ✅ 초집중 단일 포커스 썸네일 생성 완료 -> {out_path.name}")
    return out_path
