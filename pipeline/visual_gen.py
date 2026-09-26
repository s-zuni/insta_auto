"""
Visual Generation Module.
Supports Vertex AI Imagen 3 and Pollinations FLUX.1 HD Engine (9:16 vertical 1080x1920).
Automatically generates rich cinematic visuals matching the scene narration.
"""
import os
import sys
import io
import time
import requests
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


def generate_with_pollinations_flux(prompt: str, output_path: Path) -> bool:
    """
    Pollinations FLUX.1 엔진을 사용하여 고화질 9:16 세로형(1080x1920) 이미지를 생성합니다.
    API 키 없이 안정적으로 고품질 비주얼을 제공합니다.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        clean_prompt = prompt.replace("\n", " ").strip()
        enhanced_prompt = f"{clean_prompt}, cinematic aesthetic, mystical mood, 8k resolution, vertical 9:16 ratio, hyperrealistic"
        encoded = requests.utils.quote(enhanced_prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded}?width=1080&height=1920&nologo=true&model=flux"
        
        print(f"    [AI-IMAGE] FLUX.1 생성 요청 중: '{prompt[:40]}...'")
        r = requests.get(url, timeout=45)
        if r.status_code == 200 and len(r.content) > 10000:
            with open(output_path, "wb") as f:
                f.write(r.content)
            return True
        else:
            print(f"    [WARN] FLUX 응답 비정상 (code={r.status_code}, len={len(r.content)})")
    except Exception as e:
        print(f"    [WARN] FLUX 생성 실패: {e}")
    return False


def generate_with_vertex_imagen(
    prompt: str,
    output_path: Path,
    project_id: str,
    location: str = "us-central1",
    model_name: str = "imagen-3.0-generate-002"
) -> bool:
    """Vertex AI SDK를 이용해 Imagen 3로 이미지를 생성합니다."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
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
    except Exception:
        pass
    return False


def create_aesthetic_placeholder(scene_id: int, narration: str, output_path: Path):
    """최후의 수단으로 사용하는 세련된 백드롭"""
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


def generate_scene_images(
    scenes: list,
    output_dir: Optional[str | Path] = None,
    force_mock: bool = False
) -> List[str]:
    """씬 리스트의 visual_prompt를 바탕으로 9:16 고화질 비주얼을 생성합니다."""
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
    print(f"[VISUAL] 총 {len(scenes)}개 씬 비주얼 생성 시작 (엔진: FLUX.1 / Imagen 3)...")

    for sc in scenes:
        scene_id = getattr(sc, "scene_id", sc.get("scene_id") if isinstance(sc, dict) else 1)
        narration = getattr(sc, "narration", sc.get("narration") if isinstance(sc, dict) else "")
        prompt = getattr(sc, "visual_prompt", sc.get("visual_prompt") if isinstance(sc, dict) else "")

        img_path = output_dir / f"scene_{scene_id:02d}.jpg"
        generated = False

        if not force_mock:
            # 1. FLUX.1 고품질 생성 시도 (가장 안정적이고 고화질)
            generated = generate_with_pollinations_flux(prompt, img_path)
            
            # 2. Vertex AI Imagen 3 시도 (설정된 경우)
            if not generated and can_use_vertex:
                generated = generate_with_vertex_imagen(prompt, img_path, project_id, location, model_name)

        if not generated:
            print(f"  [VISUAL] 씬 {scene_id} 백드롭 생성")
            create_aesthetic_placeholder(scene_id, narration, img_path)

        # 1080x1920 해상도 보정
        try:
            with Image.open(img_path) as im:
                if im.size != (1080, 1920):
                    im_resized = im.resize((1080, 1920), Image.Resampling.LANCZOS)
                    im_resized.save(img_path, "JPEG", quality=95)
        except Exception:
            pass

        image_paths.append(str(img_path.resolve()))
        print(f"  ✅ 씬 {scene_id} 이미지 준비 완료 -> {img_path.name}")

    print(f"[SUCCESS] 모든 씬({len(image_paths)}장) 고화질 비주얼 생성 완료!")
    return image_paths