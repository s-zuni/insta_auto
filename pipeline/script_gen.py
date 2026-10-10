"""
Instagram Reels Script Generation Module using LLM JSON output (Gemini free tier first, OpenAI gpt-4o-mini fallback).
"""
import os
import json
from typing import List, Optional
from pydantic import BaseModel, Field
import sys
from dotenv import load_dotenv

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

load_dotenv()


class Scene(BaseModel):
    scene_id: int = Field(
        ...,
        description="장면 순번 (1부터 순서대로 증가)"
    )
    narration: str = Field(
        ...,
        description="해당 씬에서 읽을 자연스러운 한국어 내레이션 대사. 듣기 편하고 명확한 구어체."
    )
    visual_prompt: str = Field(
        ...,
        description="Imagen 3 생성용 구체적 영문 프롬프트. 16:9 가로(landscape) 구도, 시네마틱 조명, 고화질 묘사 포함, 텍스트 배제 지침 포함."
    )
    duration_estimate: int = Field(
        ...,
        description="해당 장면의 예상 재생 시간 (초 단위, 대사 길이에 따라 4~8초 내외)"
    )


class ReelsScript(BaseModel):
    title: str = Field(
        ...,
        description="영상 제목 (직관적이고 호기심을 유발하는 제목)"
    )
    hook: str = Field(
        ...,
        description="초반 3초 안에 시청자의 이탈을 막는 강력한 후킹 멘트"
    )
    scenes: List[Scene] = Field(
        ...,
        description="영상을 구성하는 씬 리스트 (총 4~7개 씬으로 전체 길이 30~50초 구성)"
    )
    instagram_caption: str = Field(
        ...,
        description="인스타그램 업로드용 본문 캡션 (핵심 요약 + 독자 댓글 유도 콜투액션 + 관련 인기 해시태그 8~12개)"
    )


def get_gemini_client():
    """
    환경 변수에 따라 google-genai Client를 적절한 모드(API Key 또는 Vertex AI)로 초기화합니다.
    """
    from google import genai

    api_key = os.getenv("GEMINI_API_KEY")
    project = os.getenv("GOOGLE_CLOUD_PROJECT")
    location = os.getenv("GCP_LOCATION", "us-central1")
    service_account = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    force_vertex = os.getenv("USE_VERTEX_GEMINI", "").strip().lower() in ("1", "true", "yes")

    # 1. AI Studio API Key 모드 (기본 우선순위: 서비스 계정 키가 있어도 Vertex AI API가
    #    비활성화되어 있을 수 있으므로, 명시적으로 강제하지 않는 한 API 키를 우선 사용합니다.)
    if api_key and not api_key.startswith("your_") and not force_vertex:
        return genai.Client(api_key=api_key)

    # 2. Vertex AI 모드 (USE_VERTEX_GEMINI=true 로 명시했거나 API 키가 없는 경우)
    if service_account and os.path.isfile(service_account):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = service_account
        return genai.Client(vertexai=True, project=project, location=location)

    # 3. 환경 변수 기본값 시도
    return genai.Client()


DEFAULT_LLM_MODEL = "gpt-4o-mini"
DEFAULT_GEMINI_TEXT_MODEL = "gemini-2.5-flash"


def get_llm_model(model_name: Optional[str] = None) -> str:
    """텍스트 생성에 쓸 OpenAI 모델명 (인자 > OPENAI_MODEL 환경변수 > gpt-4o-mini)."""
    return model_name or os.getenv("OPENAI_MODEL") or DEFAULT_LLM_MODEL


def get_openai_client():
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")
    return OpenAI(api_key=api_key)


def _llm_providers() -> List[str]:
    """LLM_PROVIDER(gemini|openai)를 1순위로, 나머지를 폴백으로 둔 호출 순서."""
    first = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
    first = first if first in ("gemini", "openai") else "gemini"
    return [first, "openai" if first == "gemini" else "gemini"]


def _parse_json_text(raw: str):
    raw = (raw or "").strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(raw)


def _generate_json_openai(system_prompt, user_prompt, schema, temperature, model_name):
    client = get_openai_client()
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})
    model = get_llm_model(model_name if model_name and not model_name.startswith("gemini") else None)

    if schema is not None:
        # json_object 모드는 프롬프트에 'JSON' 언급과 스키마 안내가 있어야 안정적입니다.
        messages[-1]["content"] += (
            "\n\n반드시 아래 JSON 스키마를 따르는 JSON 객체만 출력하세요:\n"
            + json.dumps(schema.model_json_schema(), ensure_ascii=False)
        )
    elif not any("json" in m["content"].lower() for m in messages):
        messages[-1]["content"] += "\n\nJSON 객체만 출력하세요."

    res = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        response_format={"type": "json_object"},
    )
    return _parse_json_text(res.choices[0].message.content)


def _generate_json_gemini(system_prompt, user_prompt, schema, temperature, model_name):
    from google.genai import types

    client = get_gemini_client()
    model = model_name if model_name and model_name.startswith("gemini") else (
        os.getenv("GEMINI_TEXT_MODEL") or DEFAULT_GEMINI_TEXT_MODEL
    )
    config = {"response_mime_type": "application/json", "temperature": temperature}
    if system_prompt:
        config["system_instruction"] = system_prompt
    if schema is not None:
        config["response_schema"] = schema
    response = client.models.generate_content(
        model=model, contents=user_prompt, config=types.GenerateContentConfig(**config)
    )
    parsed = getattr(response, "parsed", None)
    if schema is not None and parsed is not None:
        return parsed if isinstance(parsed, schema) else schema.model_validate(parsed)
    return _parse_json_text(response.text)


def generate_json(system_prompt: Optional[str], user_prompt: str, schema=None,
                  temperature: float = 0.7, model_name: Optional[str] = None):
    """
    LLM으로 JSON 응답을 생성합니다. LLM_PROVIDER(기본 gemini)를 먼저 시도하고,
    실패(무료 한도 초과 등)하면 다른 프로바이더로 자동 폴백합니다.
    schema(pydantic 모델)가 있으면 검증된 인스턴스를, 없으면 dict를 반환합니다.
    """
    runners = {"gemini": _generate_json_gemini, "openai": _generate_json_openai}
    last_err = None
    for provider in _llm_providers():
        try:
            data = runners[provider](system_prompt, user_prompt, schema, temperature, model_name)
            return schema.model_validate(data) if schema is not None and isinstance(data, dict) else data
        except Exception as e:
            last_err = e
            print(f"[LLM][WARN] {provider} 호출 실패, 다음 프로바이더 시도: {str(e)[:200]}")
    raise RuntimeError(f"모든 LLM 프로바이더 호출 실패: {last_err}")


SYSTEM_PROMPT = """
당신은 인스타그램 릴스(Reels) 전문 숏폼 바이럴 디렉터이자 카피라이터입니다.
주어진 주제를 바탕으로 초반 1.5초 이탈을 원천 차단하고 시청 지속 시간(완독율)과 저장/공유를 극대화하는 30~45초 분량의 9:16 세로 릴스 대본을 기획하세요.

[제작 규칙]
1. 구성 (시청 지속 시간 극대화):
   - 씬 1 (초반 1.5초 후킹): 지루한 도입부("안녕하세요", "~알아볼게요") 절대 금지!
     [결핍/손실 회피형, 극단적 공감/반전형, 타겟 특정형] 중 하나로 시작하여 즉시 시선을 사로잡을 것.
   - 씬 2~4 (빠른 팩트 전개): 군더더기 없는 빠른 템포의 분석과 흥미 유지 + 친구 소환/댓글 유도 트리거.
   - 마지막 씬: 결핍을 해소할 프로필 링크 상세 확인 고전환 CTA.
   - 전체 씬 수: 4~6개 씬 (총 러닝타임 30~45초).
2. 내레이션:
   - 자연스럽고 몰입감 높은 한국어 구어체 (~해요, ~거든요, ~답니다 등 리듬감 있게).
   - narration 필드에는 한자(漢字)를 절대 포함하지 마세요. 오직 순수 한글(및 필요시 숫자/영문)만 사용합니다.
     (예: "토(土)" 대신 "토"만 사용 — TTS가 한글과 한자를 중복 발음하는 것을 방지하기 위함입니다.)
3. visual_prompt (FLUX / Imagen 가이드):
   - 반드시 '영문(English)'으로 작성.
   - 이미지는 16:9 가로 비율로 생성되어 릴스 프레임 중앙에 배치됩니다.
   - ★실사 규칙★ 가상 인물/일러스트/3D/신비주의 합성 느낌 금지. 실제 한국인이 일상에서 찍은 사진처럼 묘사한다.
     (예: "a Korean woman in her late 20s at a cafe window seat looking at her phone, natural daylight, candid smartphone photo")
     인물은 구체적 나이대·상황·표정·소품(카페, 퇴근길 지하철, 자취방 책상, 편의점)을 쓰고, glowing/mystical/neon/cosmic/fantasy 단어는 쓰지 않는다.
     씬마다 인물 구도를 바꾼다(클로즈업 손, 뒷모습, 옆얼굴, 사물 컷 등).
   - 글자나 텍스트가 이미지에 찍히지 않도록 "no text, no letters, no watermark, clean composition"을 항상 포함.
4. instagram_caption:
   - 이모지를 적절히 배치하여 가독성을 높이고, 저장/공유 유도 문구와 함께 인기 해시태그 8~12개 포함.
"""


def generate_script(topic: str, model_name: Optional[str] = None) -> ReelsScript:
    """
    주제(topic)를 받아 Gemini를 통해 구조화된 ReelsScript 객체를 반환합니다.
    """
    prompt = f"다음 주제에 대해 인스타그램 릴스 대본을 기획해주세요:\n\n주제: {topic}"

    script = generate_json(SYSTEM_PROMPT, prompt, ReelsScript, temperature=0.7, model_name=model_name)

    def _enforce_cta(sc: ReelsScript) -> ReelsScript:
        fixed_cta = "프로필 링크에서 당신의 모든 운명을 확인하세요!"
        caption_cta = "👉 프로필 링크에서 당신의 모든 운명을 확인하세요!"
        if sc.scenes:
            sc.scenes[-1].narration = fixed_cta
            if sc.scenes[-1].duration_estimate < 3:
                sc.scenes[-1].duration_estimate = 4
        if caption_cta not in sc.instagram_caption:
            if "#" in sc.instagram_caption:
                parts = sc.instagram_caption.split("#", 1)
                sc.instagram_caption = f"{parts[0].strip()}\n\n{caption_cta}\n\n#{parts[1]}"
            else:
                sc.instagram_caption = f"{sc.instagram_caption.strip()}\n\n{caption_cta}"
        sc.title = sc.title.replace("\n", " ").strip()
        if len(sc.title) > 16:
            sc.title = sc.title[:16].strip()
        return sc

    return _enforce_cta(script)


def create_sample_script(topic: str) -> ReelsScript:
    """
    API 키가 없거나 테스트/오프라인 환경일 때 파이프라인 전체 동작을 검증하기 위한 샘플 대본입니다.
    """
    fixed_cta = "프로필 링크에서 당신의 모든 운명을 확인하세요!"
    caption_cta = "👉 프로필 링크에서 당신의 모든 운명을 확인하세요!"
    return ReelsScript(
        title=f"{topic}"[:16],
        hook="아직도 이걸 모르고 계셨나요? 30초 만에 완벽 정리해 드립니다!",
        scenes=[
            Scene(
                scene_id=1,
                narration="아직도 이걸 모르고 계셨나요? 30초 만에 완벽 정리해 드립니다!",
                visual_prompt="Horizontal 16:9 landscape ratio, shocked person looking at a glowing futuristic smartphone screen in modern minimalist room, cinematic dramatic lighting, photorealistic, 8k, no text, no watermark",
                duration_estimate=4
            ),
            Scene(
                scene_id=2,
                narration="첫 번째로 기억해야 할 핵심은 바로 효율적인 자동화 파이프라인의 구축입니다.",
                visual_prompt="Horizontal 16:9 landscape ratio, sleek modern digital workspace with glowing nodes connecting seamlessly, neon blue and warm orange aesthetic, cinematic depth of field, photorealistic, no text",
                duration_estimate=6
            ),
            Scene(
                scene_id=3,
                narration="인공지능 도구들을 유기적으로 결합하면 반복 작업의 시간을 90% 이상 줄일 수 있죠.",
                visual_prompt="Horizontal 16:9 landscape ratio, futuristic hourglass with glowing light particles flowing upward, cinematic high tech studio background, photorealistic, vibrant colors, 8k, no text",
                duration_estimate=6
            ),
            Scene(
                scene_id=4,
                narration=fixed_cta,
                visual_prompt="Horizontal 16:9 landscape ratio, smartphone screen displaying profile link with mystical glow, golden hour warm sunlight, cinematic masterpiece, photorealistic, no text",
                duration_estimate=4
            )
        ],
        instagram_caption=f"""🔥 {topic}의 모든 것, 30초 만에 마스터하기!

{caption_cta}

#인스타릴스 #{topic.replace(' ', '')} #생산성 #AI자동화 #릴스제작 #크리에이터 #쇼츠 #꿀팁"""
    )


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Reels 대본 기획 테스트 CLI")
    parser.add_argument("--topic", type=str, default="AI로 생산성 10배 올리는 3가지 비밀", help="릴스 주제")
    parser.add_argument("--mock", action="store_true", help="API 호출 없이 샘플 데이터 생성")
    args = parser.parse_args()

    print(f"[INFO] 주제 기획 시작: '{args.topic}'")
    try:
        if args.mock:
            script = create_sample_script(args.topic)
            print("[INFO] Mock 대본이 생성되었습니다.")
        else:
            script = generate_script(args.topic)
            print("[SUCCESS] Gemini로부터 대본 생성 완료!")

        print("\n" + "="*50)
        print(f"📌 제목: {script.title}")
        print(f"⚡ 후킹: {script.hook}")
        print(f"🎬 총 씬 개수: {len(script.scenes)}개")
        for sc in script.scenes:
            print(f"  [{sc.scene_id}] ({sc.duration_estimate}초) {sc.narration}")
            print(f"      🖼️ Visual: {sc.visual_prompt[:60]}...")
        print("="*50)
        print(f"📝 인스타 캡션:\n{script.instagram_caption}")
    except Exception as e:
        print(f"[ERROR] 대본 생성 실패: {e}")
        print("\n[TIP] 오프라인 테스트는 '--mock' 옵션을 사용하여 검증할 수 있습니다.")
