"""
Visual Generation Module (Hybrid Video + Image Engine).
Video priority (for Hook / Video scenes):
  1. Google Gemini Flow Browser Automation (labs.google/fx/ko/tools/flow - $0 API cost)
  2. Pexels / Pixabay Free HD Video API ($0 cost, cloud-compatible)
  3. Vertex AI / Gemini Veo API (optional, when USE_VEO_API=true)
Image priority:
  1. Google Gemini Flow Image (optional) -> Gemini 2.5 Flash Image ("Nano Banana")
  2. Pollinations FLUX.1 (Free) -> Vertex AI Imagen 3.
Generates 16:9 landscape visuals and composites them into 9:16 vertical Reels frames
with a fixed top title header, a centered 16:9 visual, and a bottom narration subtitle zone.
"""
import os
import sys
import io
import shutil
import subprocess
import time
import requests
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageEnhance
from dotenv import load_dotenv

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@dataclass
class ImageGenResult:
    image_paths: List[str] = field(default_factory=list)
    placeholder_scene_ids: List[int] = field(default_factory=list)
    video_paths: Dict[int, str] = field(default_factory=dict)

    @property
    def placeholder_count(self) -> int:
        return len(self.placeholder_scene_ids)


def extract_first_frame_from_video(video_path: Path, output_jpg_path: Path) -> bool:
    """비디오 에셋에서 첫 번째 프레임(9:16 1080x1920 풀스크린)을 추출하여 베이스 이미지로 저장합니다."""
    try:
        from utils.ffmpeg_check import get_ffmpeg_path
        ffmpeg_bin = get_ffmpeg_path() or "ffmpeg"
        output_jpg_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            ffmpeg_bin, "-y",
            "-ss", "0.15",
            "-i", str(video_path),
            "-frames:v", "1",
            "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
            "-q:v", "2",
            str(output_jpg_path),
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return res.returncode == 0 and output_jpg_path.is_file() and output_jpg_path.stat().st_size > 5000
    except Exception:
        return False


def infer_curiosity_badge(title: str) -> str:
    """제목 키워드를 분석하여 상단 플로팅 필 뱃지 문구를 자동 선택합니다 (이모지 글리프 깨짐 방지)."""
    t = (title or "").upper()
    # mbtiju 타겟 조합 감지
    found_y = next((y for y in ("94년생","95년생","96년생","97년생","98년생","99년생","00년생","01년생","02년생","03년생","04년생") if y in t), "")
    found_m = next((m for m in ("INTJ","INTP","ENTJ","ENTP","INFJ","INFP","ENFJ","ENFP","ISTJ","ISFJ","ESTJ","ESFJ","ISTP","ISFP","ESTP","ESFP") if m in t), "")
    found_z = next((z for z in ("용띠","호랑이띠","범띠","토끼띠","소띠","개띠","돼지띠","쥐띠","뱀띠","말띠","양띠","원숭이띠","닭띠") if z in t), "")
    found_dm = next((d for d in ("갑목","을목","병화","정화","무토","기토","경금","신금","임수","계수") if d in t), "")

    if found_y and found_m:
        extra = f" {found_z}" if found_z else (f" {found_dm}" if found_dm else "")
        return f"[ {found_y}{extra} × {found_m} ]"
    if found_z and found_m:
        return f"[ {found_z} × {found_m} ]"
    if found_dm and found_m:
        return f"[ {found_dm} × {found_m} ]"
    if "TOP" in t or "조합" in t:
        return "[ 2026 대박 사주×MBTI 조합 ]"

    if any(k in t for k in ("도화살", "홍염살", "매력", "인기")):
        return "[ 소름 주의 ] 치명적 사주 매력"
    if any(k in t for k in ("손절", "겉착", "착한", "칼같", "반전", "오해")):
        return "[ 반전 주의 ] 99%가 속는 사주 본성"
    if any(k in t for k in ("3개", "체크", "해당", "맞으면")):
        return "[ 체크리스트 ] 3개 맞으면 100%"
    if any(k in t for k in ("궁합", "연애", "남자", "여자", "썸", "카톡")):
        return "[ 연애 사주 ] 소름 돋는 상대 속마음"
    if any(k in t for k in ("대운", "징조", "신호", "돈", "재물", "풀리")):
        return "[ 대운 시그널 ] 인생 터지기 직전 징조"
    return "[ 사주 × 심리 ] 소름 팩트체크"


def build_shorts_overlay(
    title: str,
    output_png_path: Path,
    category_tag: str = "",
) -> Path:
    """
    9:16 풀스크린 숏츠/릴스 영상 및 이미지 위에 얹을 투명 오버레이(1080x1920 RGBA PNG)를 생성합니다.
    - 상단 시네마틱 다크 비네팅 (Y=0..460) + 하단 자막 가독성 다크 비네팅 (Y=1140..1920)
    - 상단 플로팅 글래스모피즘 호기심 뱃지 (Y=148)
    - 2톤 임팩트 훅 타이틀 (흰색 + 일렉트릭 골드 하이라이트, Y=228)
    """
    from pipeline.text_utils import sanitize_title, wrap_by_pixel_width

    CANVAS_W, CANVAS_H = 1080, 1920
    overlay = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # 1. 상단 & 하단 시네마틱 비네팅 그라데이션 (가독성 확보 + 영상 몰입감 유지)
    top_end = 470
    for y in range(top_end):
        t = 1.0 - (y / top_end)
        alpha = int(205 * (t ** 1.35))
        draw.line([(0, y), (CANVAS_W, y)], fill=(6, 7, 14, alpha))

    bot_start = 1120
    for y in range(bot_start, CANVAS_H):
        t = (y - bot_start) / (CANVAS_H - bot_start)
        alpha = int(230 * (t ** 1.25))
        draw.line([(0, y), (CANVAS_W, y)], fill=(6, 7, 14, alpha))

    # 2. 폰트 로드
    font_path = PROJECT_ROOT / "assets" / "fonts" / "Pretendard-Bold.otf"
    if not font_path.is_file():
        font_path = PROJECT_ROOT / "assets" / "fonts" / "NanumGothic-Bold.ttf"
    font_file = str(font_path) if font_path.is_file() else None

    def _load(size: int):
        try:
            return ImageFont.truetype(font_file, size) if font_file else ImageFont.load_default()
        except Exception:
            return ImageFont.load_default()

    # 3. 상단 플로팅 호기심 필 뱃지 (Y=145)
    badge_text = category_tag.strip() if category_tag.strip() else infer_curiosity_badge(title)
    badge_font = _load(36)
    bbox = draw.textbbox((0, 0), badge_text, font=badge_font)
    bw, bh = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad_x, pad_y = 34, 15
    pill_w = bw + pad_x * 2
    pill_h = bh + pad_y * 2
    pill_x0 = (CANVAS_W - pill_w) // 2
    pill_y0 = 142
    draw.rounded_rectangle(
        [pill_x0, pill_y0, pill_x0 + pill_w, pill_y0 + pill_h],
        radius=pill_h // 2,
        fill=(14, 15, 26, 215),
        outline=(255, 212, 59, 235),
        width=3,
    )
    draw.text(
        (CANVAS_W // 2, pill_y0 + pill_h // 2),
        badge_text,
        font=badge_font,
        fill=(255, 224, 102, 255),
        anchor="mm",
    )

    # 4. 상단 플로팅 2톤 훅 타이틀 (Y=232)
    clean_title = sanitize_title(title).replace(chr(10), " ").strip()
    max_title_width = CANVAS_W - 110
    title_size = 86
    while True:
        title_font = _load(title_size)
        lines = wrap_by_pixel_width(clean_title, title_font, max_title_width) or [clean_title]
        if len(lines) <= 2 or title_size <= 64:
            break
        title_size -= 6
    if len(lines) > 2:
        lines = lines[:2]
        lines[-1] = lines[-1].rstrip() + "…"

    # 한 줄에 어절이 3개 이상이면 시각적 리듬감을 위해 2줄(흰색 셋업 + 골드 강조)로 분할
    if len(lines) == 1:
        words = lines[0].split()
        if len(words) >= 3:
            mid = len(words) // 2
            lines = [" ".join(words[:mid]), " ".join(words[mid:])]

    title_y = pill_y0 + pill_h + 26
    line_h = int(title_size * 1.22)
    for idx, line in enumerate(lines):
        # 첫 줄은 깔끔한 화이트, 마지막 줄(핵심 키워드)은 시선을 끄는 일렉트릭 골드
        fill_color = (255, 216, 64, 255) if (len(lines) > 1 and idx == len(lines) - 1) else (255, 255, 255, 255)
        y_pos = title_y + idx * line_h
        # 소프트 드롭 섀도우
        draw.text(
            (CANVAS_W // 2 + 3, y_pos + 5),
            line,
            font=title_font,
            fill=(0, 0, 0, 185),
            anchor="mt",
            stroke_width=8,
            stroke_fill=(0, 0, 0, 185),
        )
        draw.text(
            (CANVAS_W // 2, y_pos),
            line,
            font=title_font,
            fill=fill_color,
            anchor="mt",
            stroke_width=6,
            stroke_fill=(8, 8, 14, 255),
        )

    output_png_path.parent.mkdir(parents=True, exist_ok=True)
    overlay.save(output_png_path, "PNG")
    return output_png_path


def compose_reels_frame(
    image_path: Path,
    title: str,
    category_tag: str = ""
):
    """
    기존의 답답한 [검은 여백 + 16:9 가로 사진 + 검은 여백] 구도를 탈피하여,
    1080x1920 화면 전체를 꽉 채우는 9:16 풀블리드(Full-Bleed) 숏츠 구도 + 시네마틱 비네팅 + 플로팅 훅 헤더로 합성합니다.
    """
    if not image_path.is_file():
        return

    try:
        CANVAS_W, CANVAS_H = 1080, 1920
        raw_img = Image.open(image_path).convert("RGB")
        # 9:16 꽉 찬 구도로 크롭/스케일 (인물 얼굴이 주로 위치한 상단~중상단 중심)
        full_img = ImageOps.fit(
            raw_img, (CANVAS_W, CANVAS_H), method=Image.Resampling.LANCZOS, centering=(0.5, 0.38)
        )
        # 모바일 화면에서 색감과 대비가 살아나도록 미세 보정
        full_img = ImageEnhance.Contrast(full_img).enhance(1.06)
        full_img = ImageEnhance.Color(full_img).enhance(1.08)

        overlay_path = image_path.parent / "shorts_overlay.png"
        build_shorts_overlay(title=title, output_png_path=overlay_path, category_tag=category_tag)

        overlay_rgba = Image.open(overlay_path).convert("RGBA")
        composed = Image.alpha_composite(full_img.convert("RGBA"), overlay_rgba).convert("RGB")
        composed.save(image_path, "JPEG", quality=95)
        print(f"  [FRAME] 9:16 풀스크린 숏츠 구도 + 플로팅 훅 헤더 합성 완료 -> {image_path.name}")
    except Exception as e:
        print(f"  [WARN] 프레임 합성 중 오류 발생: {e}")


# 실제 사람이 찍은 스마트폰 세로(9:16) 사진처럼 보이게 하는 공통 스타일
REALISM_SUFFIX = (
    "Candid vertical smartphone photo taken by a real person, authentic Korean everyday scene, "
    "natural available light, realistic skin texture with pores and slight imperfections, "
    "ordinary un-retouched look, slight film grain, shallow but natural depth of field, "
    "not a studio shot, not CGI, not 3D render, not illustration, no airbrushed or doll-like face, "
    "Vertical 9:16 portrait full-screen aspect ratio, subject framed naturally in center-upper area, "
    "no text, no letters, no watermark, no logo."
)


def generate_with_gemini_nanobanana(prompt: str, output_path: Path, retries: int = 2) -> bool:
    """Gemini 2.5 Flash Image ("나노바나나") 모델로 9:16 세로형 풀스크린 초고화질 이미지를 생성합니다."""
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key or api_key.startswith("your_"):
        return False

    model_name = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")
    clean_prompt = prompt.replace("\n", " ").strip()
    enhanced_prompt = (
        f"{clean_prompt}. {REALISM_SUFFIX}"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    for attempt in range(1, retries + 1):
        try:
            print(f"    [AI-IMAGE] 나노바나나(Gemini 2.5 Flash Image 9:16) 생성 요청 중 (시도 {attempt}/{retries}): '{prompt[:40]}...'")
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=model_name,
                contents=enhanced_prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    image_config=types.ImageConfig(
                        aspect_ratio="9:16",
                        image_size=os.getenv("GEMINI_IMAGE_SIZE", "1K"),
                    ),
                ),
            )

            image_bytes = None
            for candidate in getattr(response, "candidates", None) or []:
                for part in getattr(candidate.content, "parts", None) or []:
                    inline_data = getattr(part, "inline_data", None)
                    if inline_data and inline_data.data:
                        image_bytes = inline_data.data
                        break
                if image_bytes:
                    break

            if image_bytes and len(image_bytes) > 10000:
                with open(output_path, "wb") as f:
                    f.write(image_bytes)
                return True
            print("    [WARN] 나노바나나 응답에 유효한 이미지 데이터가 없습니다.")
        except Exception as e:
            print(f"    [WARN] 나노바나나 생성 실패 (시도 {attempt}/{retries}): {e}")

        if attempt < retries:
            time.sleep(2 * attempt)
    return False


def generate_with_pollinations_flux(prompt: str, output_path: Path, retries: int = 3) -> bool:
    """
    Pollinations FLUX.1 엔진을 사용하여 고화질 9:16 세로형(1080x1920) 이미지를 생성합니다.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    clean_prompt = prompt.replace("\n", " ").strip()
    enhanced_prompt = f"{clean_prompt}. {REALISM_SUFFIX}"
    encoded = requests.utils.quote(enhanced_prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=1080&height=1920&nologo=true&model=flux"

    for attempt in range(1, retries + 1):
        try:
            print(f"    [AI-IMAGE] FLUX.1 9:16 생성 요청 중 (시도 {attempt}/{retries}): '{prompt[:40]}...'")
            r = requests.get(url, timeout=60)
            if r.status_code == 200 and len(r.content) > 10000:
                with open(output_path, "wb") as f:
                    f.write(r.content)
                return True
            print(f"    [WARN] FLUX 응답 비정상 (code={r.status_code}, len={len(r.content)})")
        except Exception as e:
            print(f"    [WARN] FLUX 생성 실패 (시도 {attempt}/{retries}): {e}")

        if attempt < retries:
            time.sleep(3 * attempt)
    return False


def generate_with_vertex_imagen(
    prompt: str,
    output_path: Path,
    project_id: str,
    location: str = "us-central1",
    model_name: str = "gemini-2.5-flash-image",
    retries: int = 2,
) -> bool:
    """Vertex AI API를 이용해 고화질 9:16 세로 이미지를 생성합니다."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    clean_prompt = prompt.replace("\n", " ").strip()
    enhanced_prompt = (
        f"{clean_prompt}. {REALISM_SUFFIX}"
    )

    for attempt in range(1, retries + 1):
        try:
            print(f"    [VERTEX-AI] 9:16 이미지 생성 요청 중 (시도 {attempt}/{retries}, model={model_name}): '{prompt[:40]}...'")
            from google import genai
            from google.genai import types

            client = genai.Client(vertexai=True, project=project_id, location=location)

            # 1. Gemini Flash Image 계열 모델
            if "gemini" in model_name:
                resp = client.models.generate_content(
                    model=model_name,
                    contents=enhanced_prompt,
                    config=types.GenerateContentConfig(
                        response_modalities=["IMAGE"],
                        image_config=types.ImageConfig(
                            aspect_ratio="9:16",
                            image_size=os.getenv("GEMINI_IMAGE_SIZE", "1K"),
                        ),
                    ),
                )
                image_bytes = None
                for candidate in getattr(resp, "candidates", None) or []:
                    for part in getattr(candidate.content, "parts", None) or []:
                        inline_data = getattr(part, "inline_data", None)
                        if inline_data and inline_data.data:
                            image_bytes = inline_data.data
                            break
                    if image_bytes:
                        break

                if image_bytes and len(image_bytes) > 10000:
                    with open(output_path, "wb") as f:
                        f.write(image_bytes)
                    return True

            # 2. Imagen 3 레거시/전용 엔드포인트
            else:
                result = client.models.generate_images(
                    model=model_name,
                    prompt=prompt,
                    config=dict(number_of_images=1, aspect_ratio="9:16"),
                )
                if result and result.generated_images:
                    img_obj = result.generated_images[0]
                    with open(output_path, "wb") as f:
                        f.write(img_obj.image.image_bytes)
                    return True

        except Exception as e:
            print(f"    [WARN] Vertex AI 생성 실패 (시도 {attempt}/{retries}): {e}")

        if attempt < retries:
            time.sleep(2 * attempt)

    return False


def create_aesthetic_placeholder(scene_id: int, narration: str, output_path: Path):
    """최후의 수단으로 사용하는 9:16 세로 그래디언트 백드롭"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    color_schemes = [
        ((25, 20, 60), (90, 45, 140)),
        ((15, 32, 67), (35, 110, 160)),
        ((40, 20, 20), (160, 60, 40)),
        ((20, 40, 30), (45, 120, 85)),
        ((35, 25, 55), (130, 80, 140)),
    ]
    c_start, c_end = color_schemes[(scene_id - 1) % len(color_schemes)]
    base = Image.new("RGB", (1080, 1920), c_start)
    draw = ImageDraw.Draw(base)
    for y in range(1920):
        ratio = y / 1920
        r = int(c_start[0] + (c_end[0] - c_start[0]) * ratio)
        g = int(c_start[1] + (c_end[1] - c_start[1]) * ratio)
        b = int(c_start[2] + (c_end[2] - c_start[2]) * ratio)
        draw.line([(0, y), (1080, y)], fill=(r, g, b))
    base.save(output_path, "JPEG", quality=95)


def _should_use_video_for_scene(scene_id: int, sc: object) -> bool:
    """
    해당 씬에 비디오 클립(Google Flow / Pexels 무료 스톡 / Veo)을 시도할지 결정합니다.
    - VIDEO_HOOK_SCENES 환경변수(기본 2): 초반 1~2씬(첫 3~5초 훅)은 비디오 소스를 우선 탐색.
    - 또는 씬 객체의 media_type == "video" 인 경우.
    """
    hook_count = int(os.getenv("VIDEO_HOOK_SCENES", "2"))
    media_type = getattr(sc, "media_type", sc.get("media_type") if isinstance(sc, dict) else "")
    if str(media_type).lower() == "video":
        return True
    return scene_id <= hook_count


def generate_scene_images(
    scenes: list,
    output_dir: Optional[str | Path] = None,
    force_mock: bool = False,
    title: str = "릴스 주제"
) -> "ImageGenResult":
    """
    씬 리스트의 visual_prompt를 바탕으로 하이브리드 비주얼(초반 핵심 훅 영상 + 16:9 고화질 이미지)을 생성한 후
    상단 제목+중앙 16:9 릴스 프레임(1080x1920)으로 합성합니다.
    """
    if output_dir is None:
        output_dir = Path("assets/images")
    else:
        output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    video_dir = output_dir.parent / "videos"
    video_dir.mkdir(parents=True, exist_ok=True)

    # 이전 실행의 잔여 비디오 파일 정리 (FLOW_REUSE_EXISTING=true 가 아닐 때)
    if os.getenv("FLOW_REUSE_EXISTING", "").strip().lower() not in ("1", "true", "yes"):
        for old_vid in video_dir.glob("scene_*_raw.mp4"):
            try:
                old_vid.unlink()
            except Exception:
                pass

    project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "")
    location = os.getenv("GCP_LOCATION", "us-central1")
    model_name = os.getenv("VERTEX_IMAGE_MODEL") or os.getenv("IMAGEN_MODEL") or "gemini-2.5-flash-image"
    sa_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    can_use_vertex = (not force_mock) and bool(project_id) and bool(sa_path and os.path.isfile(sa_path))

    gemini_api_key = os.getenv("GEMINI_API_KEY", "")
    can_use_nanobanana = bool(gemini_api_key and not gemini_api_key.startswith("your_"))

    # Gemini API Key가 있으면 고품질 무워터마크 맞춤 사진을 위해 Gemini 나노바나나를 기본 엔진으로 사용
    default_engine = "gemini" if can_use_nanobanana else "flux"
    engine_preference = os.getenv("IMAGE_ENGINE", default_engine).lower().strip()
    result = ImageGenResult()
    print(f"[VISUAL] 총 {len(scenes)}개 씬 하이브리드 비주얼(영상+이미지) 생성 및 프레임 합성 시작 (기본 엔진: {engine_preference})...")

    from pipeline.flow_automation import acquire_scene_video, generate_with_google_flow_browser

    for sc in scenes:
        scene_id = getattr(sc, "scene_id", sc.get("scene_id") if isinstance(sc, dict) else 1)
        narration = getattr(sc, "narration", sc.get("narration") if isinstance(sc, dict) else "")
        prompt = getattr(sc, "visual_prompt", sc.get("visual_prompt") if isinstance(sc, dict) else "")

        img_path = output_dir / f"scene_{scene_id:02d}.jpg"
        generated = False

        if not force_mock:
            # 0. 하이브리드 영상 씬(초반 훅 씬 등): Google Flow 브라우저 자동화 또는 Pexels 무료 HD 영상 우선 확보
            if _should_use_video_for_scene(scene_id, sc):
                vid_path = acquire_scene_video(scene_id, prompt, video_dir)
                if vid_path and vid_path.is_file():
                    result.video_paths[scene_id] = str(vid_path.resolve())
                    # 영상 첫 프레임을 추출하여 베이스 프레임 이미지로 활용 (API 호출 비용 절약!)
                    if extract_first_frame_from_video(vid_path, img_path):
                        generated = True
                        print(f"  🎬 씬 {scene_id} 하이브리드 비디오 클립 연결 완료 -> {vid_path.name}")

            # 0-b. Google Flow 이미지 모드 지원 (USE_GOOGLE_FLOW=true 인데 비디오가 아닌 이미지 씬인 경우)
            if not generated and os.getenv("USE_GOOGLE_FLOW_IMAGES", "").strip().lower() in ("1", "true", "yes"):
                generated = generate_with_google_flow_browser(prompt, img_path, asset_type="image")

            # 1. Gemini 나노바나나 우선 모드 (초고화질 실사 맞춤 사진, 무워터마크)
            if not generated and engine_preference in ("gemini", "nanobanana"):
                if can_use_nanobanana:
                    generated = generate_with_gemini_nanobanana(prompt, img_path)
                if not generated:
                    generated = generate_with_pollinations_flux(prompt, img_path)
                if not generated and can_use_vertex:
                    generated = generate_with_vertex_imagen(prompt, img_path, project_id, location, model_name)

            # 2. FLUX 우선 모드 (비용 0원, 실패 시 Gemini 폴백)
            elif not generated and engine_preference == "flux":
                generated = generate_with_pollinations_flux(prompt, img_path)
                if not generated and can_use_nanobanana:
                    generated = generate_with_gemini_nanobanana(prompt, img_path)
                if not generated and can_use_vertex:
                    generated = generate_with_vertex_imagen(prompt, img_path, project_id, location, model_name)

            # 3. 기타 또는 Vertex Imagen 우선 모드
            elif not generated:
                if can_use_vertex:
                    generated = generate_with_vertex_imagen(prompt, img_path, project_id, location, model_name)
                if not generated and can_use_nanobanana:
                    generated = generate_with_gemini_nanobanana(prompt, img_path)
                if not generated:
                    generated = generate_with_pollinations_flux(prompt, img_path)

        if not generated:
            print(f"  [VISUAL] 씬 {scene_id} 9:16 플레이스홀더 생성")
            create_aesthetic_placeholder(scene_id, narration, img_path)
            result.placeholder_scene_ids.append(scene_id)

        # 9:16 풀스크린(1080x1920) 해상도 및 색감 보정
        try:
            with Image.open(img_path) as im:
                im_rgb = im.convert("RGB")
                if im_rgb.size != (1080, 1920):
                    im_rgb = ImageOps.fit(
                        im_rgb, (1080, 1920), method=Image.Resampling.LANCZOS, centering=(0.5, 0.38)
                    )
                im_rgb = ImageEnhance.Contrast(im_rgb).enhance(1.06)
                im_rgb = ImageEnhance.Color(im_rgb).enhance(1.08)
                im_rgb.save(img_path, "JPEG", quality=95)
        except Exception:
            pass

        # 커버 썸네일 및 풀스크린 줌 모션용으로 합성 전 9:16 풀스크린 원본을 보존 (scene_XX_raw.jpg)
        try:
            shutil.copy2(img_path, output_dir / f"scene_{scene_id:02d}_raw.jpg")
        except Exception:
            pass

        # 9:16 풀스크린 숏츠 구도 + 시네마틱 비네팅 + 플로팅 훅 헤더(1080x1920) 합성
        compose_reels_frame(img_path, title=title)

        result.image_paths.append(str(img_path.resolve()))
        mode_tag = "VIDEO+FRAME" if scene_id in result.video_paths else "IMAGE+FRAME"
        print(f"  ✅ 씬 {scene_id} [{mode_tag}] 준비 완료 -> {img_path.name}")

    if result.placeholder_scene_ids:
        print(f"[WARN] {result.placeholder_count}/{len(scenes)}개 씬이 백드롭 플레이스홀더로 대체되었습니다 (씬: {result.placeholder_scene_ids}).")
    else:
        print(f"[SUCCESS] 모든 씬({len(result.image_paths)}장, 비디오 씬 {len(result.video_paths)}개) 하이브리드 비주얼 합성 완료!")
    return result
