"""
Visual Generation Module using Vertex AI Imagen 3 API.
Generates 9:16 vertical images (1080x1920) for each scene and saves them in assets/images/.
Includes aesthetic fallback generator for offline testing or when GCP ADC is not configured.
"""
import os
import sys
import io
from pathlib import Path
from typing import List, Optional
from PIL import Image, ImageDraw, ImageFont
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


def create_aesthetic_placeholder(
    scene_id: int,
    narration: str,
    output_path: Path,
    width: int = 1080,
    height: int = 1920
):
    """
    Imagen 3 API 호출이 불가능할 때(인증 미비 등) 영상 합성 테스트를 위해
    고해상도 9:16 그라디언트 배경의 더미 이미지를 생성합니다.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 씬 번호에 따른 세련된 그라디언트 색상 페어
    color_schemes = [
        ((25, 20, 60), (90, 45, 140)),    # Deep Purple to Magenta
        ((15, 32, 67), (35, 110, 160)),   # Midnight Blue to Cyan
        ((40, 20, 20), (160, 60, 40)),    # Dark Crimson to Amber
        ((20, 40, 30), (45, 120, 85)),    # Forest to Emerald
        ((35, 25, 55), (130, 80, 140)),   # Violet Sunset
    ]
    c_start, c_end = color_schemes[(scene_id - 1) % len(color_schemes)]

    # 1080x1920 세로 그라디언트 버퍼 생성
    base = Image.new("RGB", (width, height), c_start)
    draw = ImageDraw.Draw(base)

    for y in range(height):
        ratio = y / height
        r = int(c_start[0] + (c_end[0] - c_start[0]) * ratio)
        g = int(c_start[1] + (c_end[1] - c_start[1]) * ratio)
        b = int(c_start[2] + (c_end[2] - c_start[2]) * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    # 중앙 원형 포인트 그래픽
    center_y = height // 2 - 100
    draw.ellipse(
        [(width // 2 - 180, center_y - 180), (width // 2 + 180, center_y + 180)],
        outline=(255, 255, 255, 120),
        width=4
    )

    # 텍스트 오버레이
    try:
        font_large = ImageFont.truetype("malgun.ttf", 72)
        font_sub = ImageFont.truetype("malgun.ttf", 36)
    except Exception:
        font_large = ImageFont.load_default()
        font_sub = ImageFont.load_default()

    scene_label = f"SCENE {scene_id:02d}"
    draw.text((width // 2, center_y), scene_label, font=font_large, fill=(255, 255, 255), anchor="mm")
    draw.text((width // 2, center_y + 80), "Instagram Reels Automation", font=font_sub, fill=(200, 200, 220), anchor="mm")

    base.save(output_path, "JPEG", quality=95)
    print(f"  [IMAGE] 씬 {scene_id} 플레이스홀더 이미지 생성 완료 -> {output_path.name}")


def generate_with_vertex_imagen(
    prompt: str,
    output_path: Path,
    project_id: str,
    location: str = "us-central1",
    model_name: str = "imagen-3.0-generate-002"
) -> bool:
    """
    Vertex AI SDK를 이용해 Imagen 3로 9:16 이미지를 생성합니다.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. vertexai preview vision_models 시도
    try:
        import vertexai
        from vertexai.preview.vision_models import ImageGenerationModel

        vertexai.init(project=project_id, location=location)
        model = ImageGenerationModel.from_pretrained(model_name)
        images = model.generate_images(
            prompt=prompt,
            number_of_images=1,
            aspect_ratio="9:16",
            safety_filter_level="block_some",
            person_generation="allow_adult",
        )
        if images:
            images[0].save(location=str(output_path), include_generation_parameters=False)
            return True
    except Exception as e1:
        # 2. google-genai Client 시도
        try:
            from google import genai
            client = genai.Client(vertexai=True, project=project_id, location=location)
            result = client.models.generate_images(
                model=model_name,
                prompt=prompt,
                config=dict(
                    number_of_images=1,
                    aspect_ratio="9:16",
                    output_mime_type="image/jpeg",
                )
            )
            if result.generated_images:
                img_data = result.generated_images[0].image.image_bytes
                image = Image.open(io.BytesIO(img_data))
                image.save(output_path, "JPEG", quality=95)
                return True
        except Exception as e2:
            print(f"  [WARN] Imagen API 호출 실패: {e1} / {e2}")
            return False

    return False


def generate_scene_images(
    scenes: list,
    output_dir: Optional[str | Path] = None,
    force_mock: bool = False
) -> List[str]:
    """
    씬 리스트의 visual_prompt를 순회하며 9:16 이미지를 생성/저장하고 경로 리스트를 반환합니다.
    """
    if output_dir is None:
        output_dir = Path("assets/images")
    else:
        output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "proud-climber-458207-e8")
    location = os.getenv("GCP_LOCATION", "us-central1")
    model_name = os.getenv("IMAGEN_MODEL", "imagen-3.0-generate-002")
    sa_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

    can_use_vertex = (not force_mock) and bool(sa_path and os.path.isfile(sa_path))
    image_paths: List[str] = []

    print(f"[VISUAL] 총 {len(scenes)}개 씬에 대한 9:16 이미지 생성을 시작합니다...")

    for sc in scenes:
        scene_id = getattr(sc, "scene_id", sc.get("scene_id") if isinstance(sc, dict) else 1)
        narration = getattr(sc, "narration", sc.get("narration") if isinstance(sc, dict) else "")
        prompt = getattr(sc, "visual_prompt", sc.get("visual_prompt") if isinstance(sc, dict) else "")

        img_path = output_dir / f"scene_{scene_id:02d}.jpg"
        generated = False

        if can_use_vertex:
            print(f"  [VISUAL] 씬 {scene_id} Imagen 3 생성 중: '{prompt[:45]}...'")
            generated = generate_with_vertex_imagen(prompt, img_path, project_id, location, model_name)

        if not generated:
            create_aesthetic_placeholder(scene_id, narration, img_path)

        # 이미지 크기 검증 및 필요 시 1080x1920 리사이즈 보정
        try:
            with Image.open(img_path) as im:
                if im.size != (1080, 1920):
                    im_resized = im.resize((1080, 1920), Image.Resampling.LANCZOS)
                    im_resized.save(img_path, "JPEG", quality=95)
        except Exception:
            pass

        image_paths.append(str(img_path.resolve()))

    print(f"[SUCCESS] 모든 씬({len(image_paths)}장) 이미지 준비 완료!")
    return image_paths


if __name__ == "__main__":
    from pipeline.script_gen import create_sample_script

    sample = create_sample_script("테스트 릴스")
    paths = generate_scene_images(sample.scenes, force_mock=True)
    print("\n생성된 이미지 목록:")
    for p in paths:
        print(f"  - {p}")

