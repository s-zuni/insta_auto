"""
Visual Generation Module.
Engine priority: Gemini 2.5 Flash Image ("Nano Banana") -> Pollinations FLUX.1 -> Vertex AI Imagen 3.
Generates 16:9 landscape visuals and composites them into 9:16 vertical Reels frames
with a fixed top title header, a centered 16:9 visual, and a bottom narration subtitle zone.
"""
import os
import sys
import io
import time
import requests
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
from PIL import Image, ImageDraw, ImageFont, ImageFilter
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

    @property
    def placeholder_count(self) -> int:
        return len(self.placeholder_scene_ids)


def compose_reels_frame(
    image_path: Path,
    title: str,
    category_tag: str = "MBTI x 사주 트렌드"
):
    """
    16:9 AI 생성 이미지를 상단 고정 주제 타이틀 + 중앙 16:9 비주얼 + 하단 나레이션 자막 영역으로
    구성된 1080x1920 세로 릴스 프레임으로 합성합니다. (하단 자막은 composer.py에서 하드번인됨)
    """
    if not image_path.is_file():
        return

    try:
        from pipeline.text_utils import wrap_by_pixel_width

        CANVAS_W, CANVAS_H = 1080, 1920
        IMG_H = 608  # 1080 * 9 / 16 (반올림)
        ACCENT = (255, 187, 64)
        BG_DARK = (14, 16, 26)

        raw_img = Image.open(image_path).convert("RGB")
        img_16_9 = raw_img.resize((CANVAS_W, IMG_H), Image.Resampling.LANCZOS)

        # 1. 1080x1920 블러 처리된 사진 + 어두운 틴트 오버레이 배경
        bg = raw_img.resize((CANVAS_W, CANVAS_H), Image.Resampling.LANCZOS)
        bg = bg.filter(ImageFilter.GaussianBlur(radius=35))
        dark_overlay = Image.new("RGB", (CANVAS_W, CANVAS_H), BG_DARK)
        bg = Image.blend(bg, dark_overlay, alpha=0.75)

        draw = ImageDraw.Draw(bg)

        # 2. 폰트 준비 (상단 주제 폰트 1.5배 확대: 105pt)
        font_path = PROJECT_ROOT / "assets" / "fonts" / "NanumGothic-Bold.ttf"
        font_file = str(font_path) if font_path.is_file() else None
        try:
            title_font = ImageFont.truetype(font_file, 105) if font_file else ImageFont.load_default()
        except Exception:
            title_font = ImageFont.load_default()

        # 3. 상단 고정 주제 텍스트 (카테고리 태그 제거, 1.5배 대형 105pt 폰트 + 6px 검은색 윤곽선)
        # 중심 Y 좌표를 320px로 완전 고정하여 줄 수에 관계없이 항상 동일한 위치 유지
        clean_title = title.replace("\n", " ").strip()
        max_title_width = CANVAS_W - 120
        lines = wrap_by_pixel_width(clean_title, title_font, max_title_width) or [clean_title]
        if len(lines) > 2:
            lines = lines[:2]
            lines[-1] = lines[-1].rstrip() + "…"

        line_h = 120
        TARGET_CENTER_Y = 320
        total_text_h = line_h * len(lines)
        title_start_y = TARGET_CENTER_Y - (total_text_h // 2) + (line_h // 2)

        for idx, line in enumerate(lines):
            y_pos = title_start_y + idx * line_h
            draw.text(
                (CANVAS_W // 2, y_pos),
                line,
                font=title_font,
                fill=(255, 255, 255),
                anchor="mm",
                stroke_width=6,
                stroke_fill=(0, 0, 0)
            )

        # 4. 비주얼 이미지 정가운데 배치 ((W-w)/2, (H-h)/2) -> Y: 656~1264px
        img_y0 = (CANVAS_H - IMG_H) // 2  # 656px (정가운데)
        img_y1 = img_y0 + IMG_H           # 1264px
        bg.paste(img_16_9, (0, img_y0))
        draw.line([(0, img_y0), (CANVAS_W, img_y0)], fill=ACCENT, width=3)
        draw.line([(0, img_y1), (CANVAS_W, img_y1)], fill=ACCENT, width=3)

        # Save Final Composite Frame
        bg.save(image_path, "JPEG", quality=95)
        print(f"  [FRAME] 고정 320px 위치 105pt 대형 주제 + 정가운데 16:9 비주얼 합성 완료 -> {image_path.name}")
    except Exception as e:
        print(f"  [WARN] 프레임 합성 중 오류 발생: {e}")


def generate_with_gemini_nanobanana(prompt: str, output_path: Path, retries: int = 2) -> bool:
    """Gemini 2.5 Flash Image ("나노바나나") 모델로 16:9 가로형 초고화질 이미지를 생성합니다."""
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key or api_key.startswith("your_"):
        return False

    model_name = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")
    clean_prompt = prompt.replace("\n", " ").strip()
    enhanced_prompt = (
        f"{clean_prompt}. Horizontal 16:9 landscape aspect ratio, ultra-high resolution, "
        "photorealistic, cinematic lighting, sharp focus, rich detail, no text, no letters, "
        "no watermark, no logo, no subtitles baked into the image."
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    for attempt in range(1, retries + 1):
        try:
            print(f"    [AI-IMAGE] 나노바나나(Gemini 2.5 Flash Image) 생성 요청 중 (시도 {attempt}/{retries}): '{prompt[:40]}...'")
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model=model_name,
                contents=enhanced_prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["TEXT", "IMAGE"],
                    image_config=types.ImageConfig(
                        aspect_ratio="16:9",
                        image_size=os.getenv("GEMINI_IMAGE_SIZE", "2K"),
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
    Pollinations FLUX.1 엔진을 사용하여 고화질 16:9 가로형(1080x608) 이미지를 생성합니다.
    API 키 없이 안정적으로 고품질 비주얼을 제공합니다. 일시적 네트워크/지연 오류에 대비해
    지수 백오프로 재시도합니다.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    clean_prompt = prompt.replace("\n", " ").strip()
    enhanced_prompt = f"{clean_prompt}, cinematic aesthetic, mystical mood, 8k resolution, landscape 16:9 ratio, hyperrealistic"
    encoded = requests.utils.quote(enhanced_prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width=1080&height=608&nologo=true&model=flux"

    for attempt in range(1, retries + 1):
        try:
            print(f"    [AI-IMAGE] FLUX.1 16:9 생성 요청 중 (시도 {attempt}/{retries}): '{prompt[:40]}...'")
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
    model_name: str = "imagen-3.0-generate-002"
) -> bool:
    """Vertex AI SDK를 이용해 Imagen 3로 16:9 이미지를 생성합니다."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import vertexai
        from vertexai.preview.vision_models import ImageGenerationModel
        vertexai.init(project=project_id, location=location)
        model = ImageGenerationModel.from_pretrained(model_name)
        images = model.generate_images(
            prompt=prompt,
            number_of_images=1,
            aspect_ratio="16:9",
            safety_filter_level="block_some",
            person_generation="allow_adult",
        )
        if images:
            images[0].save(location=str(output_path), include_generation_parameters=False)
            return True
    except Exception:
        pass
    return False


def create_aesthetic_placeholder(scene_id: int, narration: str, output_path: Path):
    """최후의 수단으로 사용하는 16:9 그래디언트 백드롭"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    color_schemes = [
        ((25, 20, 60), (90, 45, 140)),
        ((15, 32, 67), (35, 110, 160)),
        ((40, 20, 20), (160, 60, 40)),
        ((20, 40, 30), (45, 120, 85)),
        ((35, 25, 55), (130, 80, 140)),
    ]
    c_start, c_end = color_schemes[(scene_id - 1) % len(color_schemes)]
    base = Image.new("RGB", (1080, 608), c_start)
    draw = ImageDraw.Draw(base)
    for y in range(608):
        ratio = y / 608
        r = int(c_start[0] + (c_end[0] - c_start[0]) * ratio)
        g = int(c_start[1] + (c_end[1] - c_start[1]) * ratio)
        b = int(c_start[2] + (c_end[2] - c_start[2]) * ratio)
        draw.line([(0, y), (1080, y)], fill=(r, g, b))
    base.save(output_path, "JPEG", quality=95)


def generate_scene_images(
    scenes: list,
    output_dir: Optional[str | Path] = None,
    force_mock: bool = False,
    title: str = "릴스 주제"
) -> "ImageGenResult":
    """씬 리스트의 visual_prompt를 바탕으로 16:9 이미지를 생성한 후 상단 제목+중앙 16:9 릴스 프레임으로 합성합니다."""
    if output_dir is None:
        output_dir = Path("assets/images")
    else:
        output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "")
    location = os.getenv("GCP_LOCATION", "us-central1")
    model_name = os.getenv("IMAGEN_MODEL", "imagen-3.0-generate-002")
    sa_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    can_use_vertex = (not force_mock) and bool(project_id) and bool(sa_path and os.path.isfile(sa_path))

    gemini_api_key = os.getenv("GEMINI_API_KEY", "")
    can_use_nanobanana = bool(gemini_api_key and not gemini_api_key.startswith("your_"))

    result = ImageGenResult()
    print(f"[VISUAL] 총 {len(scenes)}개 씬 비주얼 생성 및 릴스 프레임 레이아웃 합성 시작...")

    for sc in scenes:
        scene_id = getattr(sc, "scene_id", sc.get("scene_id") if isinstance(sc, dict) else 1)
        narration = getattr(sc, "narration", sc.get("narration") if isinstance(sc, dict) else "")
        prompt = getattr(sc, "visual_prompt", sc.get("visual_prompt") if isinstance(sc, dict) else "")

        img_path = output_dir / f"scene_{scene_id:02d}.jpg"
        generated = False

        if not force_mock:
            # 1. 나노바나나(Gemini 2.5 Flash Image) 최우선 시도 (최고화질/프롬프트 반영도)
            if can_use_nanobanana:
                generated = generate_with_gemini_nanobanana(prompt, img_path)

            # 2. FLUX.1 시도 (나노바나나 실패 또는 키 미설정 시 대체)
            if not generated:
                generated = generate_with_pollinations_flux(prompt, img_path)

            # 3. Vertex AI Imagen 3 시도 (설정된 경우)
            if not generated and can_use_vertex:
                generated = generate_with_vertex_imagen(prompt, img_path, project_id, location, model_name)

        if not generated:
            print(f"  [VISUAL] 씬 {scene_id} 16:9 플레이스홀더 생성")
            create_aesthetic_placeholder(scene_id, narration, img_path)
            result.placeholder_scene_ids.append(scene_id)

        # 16:9 해상도 보정
        try:
            with Image.open(img_path) as im:
                if im.size != (1080, 608):
                    im_resized = im.resize((1080, 608), Image.Resampling.LANCZOS)
                    im_resized.save(img_path, "JPEG", quality=95)
        except Exception:
            pass

        # 16:9 이미지를 상단 고정 제목 + 중앙 16:9 프레임(1080x1920)으로 합성
        compose_reels_frame(img_path, title=title)

        result.image_paths.append(str(img_path.resolve()))
        print(f"  ✅ 씬 {scene_id} 릴스 프레임 준비 완료 -> {img_path.name}")

    if result.placeholder_scene_ids:
        print(f"[WARN] {result.placeholder_count}/{len(scenes)}개 씬이 백드롭 플레이스홀더로 대체되었습니다 (씬: {result.placeholder_scene_ids}).")
    else:
        print(f"[SUCCESS] 모든 씬({len(result.image_paths)}장) 16:9 프레임 비주얼 합성 완료!")
    return result