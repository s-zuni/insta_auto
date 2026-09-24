"""
Instagram Reels Script Generation Module using Gemini Structured Outputs.
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
        description="Imagen 3 생성용 구체적 영문 프롬프트. 9:16 세로 구도, 시네마틱 조명, 고화질 묘사 포함, 텍스트 배제 지침 포함."
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

    # 1. Vertex AI 모드 (서비스 계정 키가 명시되어 있거나 API 키가 없는 경우)
    if service_account and os.path.isfile(service_account):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = service_account
        return genai.Client(vertexai=True, project=project, location=location)

    # 2. AI Studio API Key 모드
    if api_key and not api_key.startswith("your_"):
        return genai.Client(api_key=api_key)

    # 3. 환경 변수 기본값 시도
    return genai.Client()


SYSTEM_PROMPT = """
당신은 인스타그램 릴스(Reels) 전문 숏폼 영상 디렉터이자 바이럴 카피라이터입니다.
주어진 주제를 바탕으로 시청 지속 시간을 극대화하고 저장 및 공유를 유도하는 30~50초 분량의 9:16 세로 릴스 대본을 기획하세요.

[제작 규칙]
1. 구성:
   - 첫 씬은 무조건 3초 안에 흥미를 끄는 강력한 '후킹(Hook)'으로 시작합니다.
   - 본문 씬(3~5개): 군더더기 없는 빠른 정보 전달과 호기심 유지.
   - 마지막 씬: 명확한 결론 및 댓글/저장을 유도하는 클로징 CTA.
   - 전체 씬 수: 4~7개 씬 (총 러닝타임 30~50초).
2. 내레이션:
   - 자연스럽고 몰입감 높은 한국어 구어체 (~해요, ~했죠, ~있습니다 등 리듬감 있게).
   - 발음하기 어려운 외래어나 복잡한 문장은 피하고 리듬감 있게 분할.
3. visual_prompt (Imagen 3 전용 프롬프트 가이드):
   - 반드시 '영문(English)'으로 작성.
   - 인스타그램 릴스 9:16 비율에 최적화된 구도, 피사체, 조명, 색감, 카메라 앵글을 구체적으로 묘사.
   - 키워드 예시: "Vertical 9:16 ratio, cinematic lighting, photorealistic, 8k resolution, sharp focus, vibrant colors, shallow depth of field".
   - 글자나 텍스트가 이미지에 찍히지 않도록 "no text, no letters, no watermark, clean composition"을 항상 포함.
4. instagram_caption:
   - 이모지를 적절히 배치하여 가독성을 높이고 영상 내용을 한눈에 요약.
   - 팔로우/저장 유도 문구와 함께 인기 해시태그 8~12개 포함.
"""


def generate_script(topic: str, model_name: Optional[str] = None) -> ReelsScript:
    """
    주제(topic)를 받아 Gemini를 통해 구조화된 ReelsScript 객체를 반환합니다.
    """
    from google.genai import types

    if not model_name:
        model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    client = get_gemini_client()

    prompt = f"다음 주제에 대해 인스타그램 릴스 대본을 기획해주세요:\n\n주제: {topic}"

    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=ReelsScript,
            temperature=0.7,
        ),
    )

    if hasattr(response, "parsed") and response.parsed is not None:
        if isinstance(response.parsed, ReelsScript):
            return response.parsed
        return ReelsScript.model_validate(response.parsed)

    # 텍스트 응답에서 JSON 파싱
    raw_text = response.text.strip()
    # 마크다운 코드 블록 제거
    if raw_text.startswith("```json"):
        raw_text = raw_text[7:]
    if raw_text.startswith("```"):
        raw_text = raw_text[3:]
    if raw_text.endswith("```"):
        raw_text = raw_text[:-3]

    data = json.loads(raw_text.strip())
    return ReelsScript.model_validate(data)


def create_sample_script(topic: str) -> ReelsScript:
    """
    API 키가 없거나 테스트/오프라인 환경일 때 파이프라인 전체 동작을 검증하기 위한 샘플 대본입니다.
    """
    return ReelsScript(
        title=f"{topic} - 30초 핵심 가이드",
        hook="아직도 이걸 모르고 계셨나요? 30초 만에 완벽 정리해 드립니다!",
        scenes=[
            Scene(
                scene_id=1,
                narration="아직도 이걸 모르고 계셨나요? 30초 만에 완벽 정리해 드립니다!",
                visual_prompt="Vertical 9:16 ratio, shocked person looking at a glowing futuristic smartphone screen in modern minimalist room, cinematic dramatic lighting, photorealistic, 8k, no text, no watermark",
                duration_estimate=4
            ),
            Scene(
                scene_id=2,
                narration="첫 번째로 기억해야 할 핵심은 바로 효율적인 자동화 파이프라인의 구축입니다.",
                visual_prompt="Vertical 9:16 ratio, sleek modern digital workspace with glowing nodes connecting seamlessly, neon blue and warm orange aesthetic, cinematic depth of field, photorealistic, no text",
                duration_estimate=6
            ),
            Scene(
                scene_id=3,
                narration="인공지능 도구들을 유기적으로 결합하면 반복 작업의 시간을 90% 이상 줄일 수 있죠.",
                visual_prompt="Vertical 9:16 ratio, futuristic hourglass with glowing light particles flowing upward, cinematic high tech studio background, photorealistic, vibrant colors, 8k, no text",
                duration_estimate=6
            ),
            Scene(
                scene_id=4,
                narration="지금 바로 저장해 두시고, 다음 프로젝트에 직접 적용해 보세요!",
                visual_prompt="Vertical 9:16 ratio, inspiring bright sunrise over modern city skyline viewed from high rise window, golden hour warm sunlight, cinematic masterpiece, photorealistic, no text",
                duration_estimate=4
            )
        ],
        instagram_caption=f"""🔥 {topic}의 모든 것, 30초 만에 마스터하기!

바쁜 일상 속 생산성을 극대화하는 실전 팁을 정리했습니다.
도움이 되셨다면 나중에 다시 찾아볼 수 있게 [저장] 누르고 팔로우해 두세요! 🚀

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
