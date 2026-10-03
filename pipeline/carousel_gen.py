"""
Instagram 캐러셀 대본 생성 모듈 (Gemini Structured Output).
릴스와 동일한 시리즈/컨텍스트(MBTI, 오행, 사주, 신점, 자미두수, 타로 + trend_hint)를 받아
'훅 → 가치 슬라이드 → 저장 유도 CTA' 구조의 슬라이드 텍스트를 만듭니다.
"""
import json
import os
import sys
from typing import List, Optional

from pydantic import BaseModel, Field

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from pipeline.script_gen import get_gemini_client
from pipeline.mbti_saju_content import MBTI_KEYWORDS, FIVE_ELEMENTS, DOMAIN_LABELS

MIN_SLIDES, MAX_SLIDES = 5, 8


class CarouselSlide(BaseModel):
    headline: str = Field(..., description="슬라이드 핵심 문장. 한 줄로 읽히는 짧고 강한 문장 (표지는 호기심 유발 질문/선언, 25자 내외)")
    body: str = Field("", description="헤드라인을 뒷받침하는 설명 1~3문장 (표지는 빈 문자열 가능, 90자 이내)")


class CarouselScript(BaseModel):
    title: str = Field(..., description="캐러셀 전체 제목 (호기심을 유발하는 한 문장)")
    cover_visual_prompt: str = Field(
        ...,
        description="표지 배경용 영문 이미지 프롬프트. Horizontal 16:9 landscape, cinematic, mystical Korean fortune aesthetic, no text, no letters, no watermark",
    )
    slides: List[CarouselSlide] = Field(
        ...,
        description=f"슬라이드 {MIN_SLIDES}~{MAX_SLIDES}장. 첫 장=표지(훅), 중간=가치 슬라이드(핵심을 앞쪽에), 마지막 장=저장/팔로우 유도 CTA",
    )
    instagram_caption: str = Field(
        ...,
        description="인스타 캡션. 첫 125자 안에 훅, 본문 요약, 저장/댓글 유도 CTA, 마지막에 해시태그 3~5개",
    )


CAROUSEL_PERSONA = """[캐러셀 작가 페르소나]
당신은 대한민국 MZ세대 여성(20~30대)을 위한 인스타그램 캐러셀(카드뉴스) 전문 작가입니다.
사주 명리학 + MBTI 심리를 융합해 '저장하고 싶어지는' 정보형 슬라이드를 만듭니다.

[구성 규칙]
- 슬라이드 5~8장. 1장=표지(스크롤을 멈추게 하는 훅), 2장~마지막 전 장=가치 슬라이드, 마지막 장=저장/팔로우 CTA.
- 가장 가치 있는 정보는 앞쪽 슬라이드에 배치합니다(끝까지 안 넘겨도 얻는 게 있어야 함).
- 슬라이드마다 headline 한 문장 + body 1~3문장. 한 슬라이드에 하나의 메시지만 담습니다.
- 구체적인 숫자/상황/행동 팁을 형용사보다 우선합니다. 군더더기와 AI 말투(과한 대시, 상투적 마무리)는 피합니다.
- 팩트 중심의 날카로운 어조의 MZ 구어체. 이모지는 슬라이드당 최대 1개.
- 캡션은 첫 125자 안에 훅을 넣고, 해시태그는 3~5개만 사용합니다."""


def _series_brief(series: str, context: dict) -> str:
    if series == "MBTI":
        mbti = context.get("mbti", "INFP")
        nick, t1, t2 = MBTI_KEYWORDS.get(mbti, ("", "", ""))
        brief = f"[MBTI 시리즈: {mbti} ({nick})]\n핵심: {t1}, {t2}\n사주 오행/십신 진단과 MBTI 심리를 교차 분석하고 솔루션으로 마무리"
        if context.get("topic"):
            brief += f"\n[구체적 주제 - 반드시 이 주제를 중심으로]\n{context['topic']}"
        return brief
    if series in ("DAILY", "ELEMENT"):
        el = context.get("element", "목(木)")
        info = FIVE_ELEMENTS.get(el, {})
        brief = f"[오늘의 오행 운세: {el.split('(')[0]}]\n색상: {info.get('color', '')} | 기운: {info.get('booster', '')}\n오행 본질 → 실생활 팁"
        if context.get("topic"):
            brief += f"\n[구체적 주제 - 반드시 이 주제를 중심으로]\n{context['topic']}"
        return brief
    if series in DOMAIN_LABELS:
        label = DOMAIN_LABELS[series]
        return f"[{label} 시리즈]\n주제: {context.get('topic', f'{label} 특성 TOP 랭킹')}\n{label} 핵심 포인트 해석 → 현실 조언"
    return f"주제: {context.get('topic', '운세 캐러셀')}"


def generate_carousel_script(series: str, context: Optional[dict] = None, model_name: Optional[str] = None) -> CarouselScript:
    from google.genai import types

    context = context or {}
    model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")

    system_prompt = f"{CAROUSEL_PERSONA}\n\n{_series_brief(series, context)}"
    trend_hint = str(context.get("trend_hint", "")).strip()
    if trend_hint:
        system_prompt += f"\n\n[참고할 실시간 트렌드 헤드라인]\n\"{trend_hint}\"\n(자연스러운 훅이나 사례로만 녹이고 억지로 끼워 맞추지 마세요.)"

    try:
        from pipeline.insights import get_top_examples, format_examples_for_prompt
        examples_block = format_examples_for_prompt(get_top_examples(n=3, fmt="carousel"))
        if examples_block:
            system_prompt += f"\n\n{examples_block}"
    except Exception as e:
        print(f"[WARN] 성과 예시 로드 실패(무시): {e}")

    user_prompt = f"인스타그램 캐러셀 JSON을 작성하세요.\n시리즈: {series} | 컨텍스트: {json.dumps(context, ensure_ascii=False)}"

    try:
        client = get_gemini_client()
        response = client.models.generate_content(
            model=model_name,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                response_schema=CarouselScript,
                temperature=0.8,
            ),
        )
        if getattr(response, "parsed", None) is not None:
            script = response.parsed if isinstance(response.parsed, CarouselScript) else CarouselScript.model_validate(response.parsed)
        else:
            raw = response.text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            script = CarouselScript.model_validate(json.loads(raw))
        return _normalize(script)
    except Exception as e:
        print(f"[WARNING] 캐러셀 대본 생성 실패 ({e}). 폴백 대본 사용.")
        return _fallback(series, context)


def _normalize(script: CarouselScript) -> CarouselScript:
    """슬라이드 수를 인스타 캐러셀 제한(2~10)과 설계 범위(5~8)에 맞춥니다."""
    if len(script.slides) > MAX_SLIDES:
        # 마지막 CTA 슬라이드는 반드시 보존
        script.slides = script.slides[: MAX_SLIDES - 1] + [script.slides[-1]]
    return script


def _fallback(series: str, context: dict) -> CarouselScript:
    mbti = context.get("mbti", "ENFP")
    nick, t1, t2 = MBTI_KEYWORDS.get(mbti, ("활동가", "열정", "자유"))
    topic = context.get("topic") or f"{mbti} {nick}"
    return CarouselScript(
        title=f"{topic}, 이것만 알아도 달라져요",
        cover_visual_prompt="Horizontal 16:9 landscape, mystical glowing constellations over ancient Korean fortune book, candlelight, cinematic, no text, no letters, no watermark",
        slides=[
            CarouselSlide(headline=f"{topic}, 아직도 모르세요?", body=""),
            CarouselSlide(headline=f"핵심은 '{t1}'", body=f"사주로 보면 {nick} 유형은 이 기운이 강하게 드러나는 경우가 많아요."),
            CarouselSlide(headline=f"약점은 '{t2}'", body="기운이 한쪽으로 쏠릴 때 관계와 일에서 같은 실수가 반복돼요."),
            CarouselSlide(headline="오늘 바로 할 행동 하나", body="결정을 내리기 전에 10분만 멈추고 메모해 보세요."),
            CarouselSlide(headline="저장해두고 다시 보기", body="도움이 됐다면 저장하고 팔로우해 주세요. 매일 새로운 운세 포인트를 알려드려요."),
        ],
        instagram_caption=f"{topic}, 이것만 알아도 달라져요. 저장해두고 필요할 때 꺼내 보세요.\n\n#{mbti} #MBTI운세 #사주 #운세",
    )
