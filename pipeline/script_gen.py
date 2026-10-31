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
        description="해당 씬에서 읽을 한국어 구어체 대사. 한 씬 = 한 문장(공백 포함 22~38자, 길어도 50자 이내), 읽는 데 1.8~3.2초. 한 씬에 정보 하나만."
    )
    visual_prompt: str = Field(
        ...,
        description="비주얼/영상 생성용 구체적 영문 프롬프트. Vertical 9:16 세로(portrait) 풀스크린 구도, 실제 한국인의 일상 장면 묘사, 텍스트 배제 지침 포함."
    )
    duration_estimate: int = Field(
        ...,
        description="해당 장면의 예상 재생 시간 (초 단위, 대사 길이에 따라 2~4초 내외, 길어도 5초 이내)"
    )
    media_type: str = Field(
        default="image",
        description="비주얼 소스 타입: 초반 1~2씬(후킹 구간)은 'video', 나머지 본문 씬은 'image'"
    )


class ReelsScript(BaseModel):
    title: str = Field(
        ...,
        description="영상 제목 (직관적이고 호기심을 유발하는 16자 이내 제목)"
    )
    hook: str = Field(
        ...,
        description="초반 2.5초 안에 시청자의 이탈을 막는 강력한 후킹 멘트"
    )
    scenes: List[Scene] = Field(
        ...,
        description="영상을 구성하는 씬 리스트 (총 8~10개 씬으로 전체 길이 20~30초 구성, 씬이 짧고 빠르게 넘어가야 함)"
    )
    instagram_caption: str = Field(
        ...,
        description="인스타그램 업로드용 본문 캡션 (핵심 요약 + 독자 댓글/공유 유도 콜투액션 + 관련 인기 해시태그 8~12개)"
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
당신은 인스타그램 릴스(Reels) 100만 바이럴 전문 디렉터이자 카피라이터입니다.
주어진 주제를 바탕으로 초반 1.5초 이탈을 원천 차단하고 시청 지속 시간(완독율)과 저장/공유/댓글을 극대화하는 20~30초 분량의 9:16 세로 릴스 대본을 기획하세요.

[100만 바이럴 구성 법칙]
1. 씬 1 (초반 1.5초 스크롤 정지 훅, media_type="video"):
   - 지루한 인사("안녕하세요", "~알아볼게요") 절대 금지!
   - 일반 대중 100%가 보자마자 멈추는 [체크리스트형("여기서 3개 이상 맞으면"), 페이크아웃 통념반박형("겉은 다정한데 손절 제일 빠른 이유"), 일상/카톡 POV형, 대운 징조 미스터리형]으로 시작하세요.
2. 씬 2~4 (소름 돋는 일상 장면 3연타, scene 2는 media_type="video"):
   - 카톡 답장 속도, 퇴근 후 침대, 월급날, 싸울 때 말투 등 시청자가 "헐 내 얘기잖아" 하고 무릎을 치는 구체적 장면을 1씬 1문장(22~38자)으로 빠르게 배치하세요.
3. 씬 5~6 (사주 x MBTI 원인 해부 및 반전):
   - "사실 이게 성격 문제가 아니라 사주에 OO(일간/도화살/홍염살/십성) 기운이 강한 사람들의 특징이거든요"처럼 명리학 근거로 정체성을 풀어주세요. (장점 1 : 아픈 점 2 비율)
4. 씬 7~8 (결론/현실 조언):
   - 이 기질이 앞으로 운을 트이게 하려면 딱 무엇 하나만 바꾸면 되는지 강렬한 한 줄 조언으로 마무리하세요. (프로필 링크/댓글 CTA는 시스템이 뒤에 자동 추가합니다.)
5. 내레이션 & 제목 규칙:
   - MBTI 유형(예: INFP, ENTJ, ESFJ) 및 'MBTI' 단어는 한글 음차(인프피, 엠비티아이)가 아닌 반드시 표준 영문 대문자(예: INFP, MBTI)로 작성하세요.
   - narration과 title에는 한자(漢字)를 절대 포함하지 마세요. MBTI 영문 대문자와 숫자를 제외한 본문은 순수 한글 구어체만 사용합니다.
   - title(화면 제목)은 공백 포함 14~20자 내외로, 말이 중간에 끊기지 않는 '완성된 호기심 유발 문장'으로 작성하세요. (예: "겉은 다정한데 손절 제일 칼같은 이유", "00년생 용띠가 인간관계 지치는 이유")
6. visual_prompt (Google Flow Veo 영상 & Imagen/FLUX 실사 가이드):
   - 반드시 '영문(English)'으로 작성, Vertical 9:16 세로 풀스크린 비율.
   - 실제 한국인이 일상(카페 창가, 퇴근길 지하철, 자취방 스탠드 조명, 한강 산책로 등)에서 찍은 자연스러운 세로 숏폼 영상/사진처럼 묘사하고, 씬 1~2에는 자연스러운 움직임(subtle movement, looking up from smartphone, sipping iced coffee 등)을 포함하세요.
   - glowing/mystical/neon/cosmic/fantasy/3D render 금지, "no text, no letters, no watermark" 필수 포함.
"""


from pipeline.text_utils import sanitize_title


def generate_script(topic: str, model_name: Optional[str] = None) -> ReelsScript:
    """
    주제(topic)를 받아 Gemini를 통해 구조화된 ReelsScript 객체를 반환합니다.
    """
    prompt = f"다음 주제에 대해 인스타그램 릴스 대본을 기획해주세요:\n\n주제: {topic}"

    script = generate_json(SYSTEM_PROMPT, prompt, ReelsScript, temperature=0.7, model_name=model_name)

    def _enforce_cta(sc: ReelsScript) -> ReelsScript:
        for idx, s in enumerate(sc.scenes):
            s.media_type = "video" if idx < 2 else "image"
        is_fortune = any(w in (topic + " " + sc.title) for w in ["사주", "운명", "운세", "타로", "신점", "자미두수", "궁합", "도화살", "대운"])
        if is_fortune:
            try:
                from pipeline.cta import apply_reel_cta
                _, caption_cta = apply_reel_cta(sc.scenes, sc.instagram_caption, "", topic or sc.title)
            except Exception:
                caption_cta = "💬 댓글에 [사주] 남기거나 👉 프로필 링크에서 내 일간부터 무료로 확인하세요!"
        else:
            fixed_cta = "댓글로 의견을 남기거나 프로필 링크에서 더 자세한 전체 내용을 확인해보세요!"
            caption_cta = "👉 프로필 링크에서 더 자세한 꿀팁과 전체 내용을 확인하세요!"
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
        sc.title = sanitize_title(sc.title.replace("\n", " "))
        if len(sc.title) > 16:
            sc.title = sc.title[:16].strip()
        return sc

    return _enforce_cta(script)


def create_sample_script(topic: str) -> ReelsScript:
    """
    API 키가 없거나 테스트/오프라인 환경일 때 파이프라인 전체 동작을 검증하기 위한 샘플 대본입니다.
    """
    fixed_cta = "댓글에 사주라고 남기거나 프로필 링크에서 삼십 초 만에 내 일간을 무료로 확인해보세요!"
    caption_cta = "💬 댓글에 [사주] 남기거나\n👉 프로필 링크에서 가입 없이 30초 무료 체험으로 내 일간부터 확인하세요!"
    return ReelsScript(
        title=f"{topic}"[:16],
        hook="여기서 세 개 이상 맞으면 사주에 도화살이 낀 사람입니다.",
        scenes=[
            Scene(
                scene_id=1,
                narration="솔직히 여기서 세 개 이상 해당되면 사주에 도화살이 낀 사람입니다.",
                visual_prompt="Horizontal 16:9 landscape ratio, candid smartphone video of a Korean woman in her late 20s at a cozy cafe window seat looking up from her phone with subtle natural movement, natural daylight, no text, no watermark",
                duration_estimate=3,
                media_type="video",
            ),
            Scene(
                scene_id=2,
                narration="첫째 가만히 있어도 길에서 도를 아십니까나 번호 따이는 일이 유독 잦아요.",
                visual_prompt="Horizontal 16:9 landscape ratio, candid shot of a Korean woman walking down a lively Seoul street in Seongsu at sunset, natural available light, no text",
                duration_estimate=4,
                media_type="video",
            ),
            Scene(
                scene_id=3,
                narration="둘째 겉으로는 엄청 다정해 보이는데 한 번 마음이 식으면 뒤도 안 돌아보고 손절합니다.",
                visual_prompt="Horizontal 16:9 landscape ratio, close-up candid photo of hands holding an iced americano on a wooden table, soft afternoon sunlight, no text",
                duration_estimate=4,
                media_type="image",
            ),
            Scene(
                scene_id=4,
                narration="사실 이게 어장관리가 아니라 사주에 을목이나 홍염살 기운이 강해서 생기는 특징이거든요.",
                visual_prompt="Horizontal 16:9 landscape ratio, candid photo of a Korean woman reading a book quietly in her warm bedroom at night under a desk lamp, no text",
                duration_estimate=4,
                media_type="image",
            ),
            Scene(
                scene_id=5,
                narration=fixed_cta,
                visual_prompt="Horizontal 16:9 landscape ratio, candid photo of a Korean woman holding a smartphone smiling softly at home, natural window light, no text",
                duration_estimate=4,
                media_type="image",
            ),
        ],
        instagram_caption=f"""🔥 {topic}, 내 얘기인지 체크해보세요!

{caption_cta}

#사주 #MBTI #도화살 #운세 #연애심리 #병오년운세 #사주풀이 #릴스"""
    )


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Reels 대본 기획 테스트 CLI")
    parser.add_argument("--topic", type=str, default="여기서 3개 이상 맞으면 도화살 사주", help="릴스 주제")
    parser.add_argument("--mock", action="store_true", help="API 호출 없이 샘플 데이터 생성")
    args = parser.parse_args()
    if args.mock:
        print(create_sample_script(args.topic).model_dump_json(indent=2))
    else:
        print(generate_script(args.topic).model_dump_json(indent=2))
