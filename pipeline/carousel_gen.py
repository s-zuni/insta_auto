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

from pipeline.script_gen import generate_json
from pipeline.mbti_saju_content import MBTI_KEYWORDS, FIVE_ELEMENTS, DOMAIN_LABELS, MBTI_TYPES
from pipeline.saju_knowledge import STEMS, ELEMENT_FLOW, detect_stem, stem_brief, general_brief

MIN_SLIDES, MAX_SLIDES = 6, 8


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
당신은 사주명리학을 깊이 공부한 MZ세대 여성(20~30대) 타깃 인스타그램 캐러셀(카드뉴스) 전문 작가입니다.
십천간·십신·오행 상생상극·합충을 근거로 '저장하고 싶어지는' 정보형 슬라이드를 만듭니다.

[구성 규칙]
- 슬라이드 6~8장. 1장=표지(스크롤을 멈추게 하는 훅), 2장~마지막 전 장=가치 슬라이드, 마지막 장=저장/팔로우 CTA.
- 마지막 장 CTA는 '프로필 링크'로만 안내하고, 주제와 이어지게 쓴다(예: 내 앞으로 3년 흐름 / 나와 상대의 사주 흐름 → 3년 사주 리포트). URL·가격·없는 기능은 쓰지 않는다.
- 가장 가치 있는 정보는 앞쪽에 배치(끝까지 안 넘겨도 얻는 게 있어야 함).
- 슬라이드마다 headline 한 문장 + body 2~3문장(90자 이내). 한 슬라이드에 하나의 메시지만 담습니다.
- 슬라이드 흐름 권장: 표지 훅 → 이 기운의 정체(자연물 비유) → 강점 → 연애/관계에서 드러나는 모습(구체적 장면) →
  약점·갈등 패턴 → 잘 맞는/조심할 상대(천간 합·충 근거) → 오늘 바로 할 행동 → CTA.

[전문성 규칙 - 매우 중요]
- 반드시 사주 용어를 구체적으로 사용하세요: 천간(갑을병정무기경신임계), 오행 상생·상극, 천간합·충, 십신(비견·식신·정재 등).
  단순히 "오행이 강하다/기운이 쏠린다" 같은 모호한 문장은 금지입니다.
- 모든 주장에는 근거 비유를 붙입니다. (예: "을목은 덩굴이라 혼자 서기보다 감고 올라갈 곳을 찾아요")
- 성격 설명은 추상 형용사 대신 "이럴 때 이렇게 행동한다" 식의 구체적 장면/대사/숫자로 씁니다.
- 어느 유형에나 해당되는 뻔한 말(바넘 효과)과 "~하는 경우가 많아요" 반복을 피하고, 이 주제만의 차별점을 쓰세요.
- 슬라이드 텍스트에는 한자를 쓰지 않고 한글로만 표기합니다(렌더링 폰트 보호).
- MZ 구어체, 날카롭고 팩트 중심. 이모지는 슬라이드당 최대 1개. 군더더기와 AI 말투(과한 대시, 상투적 마무리) 금지.
- 캡션은 첫 125자 안에 훅, 해시태그는 3~5개만 사용합니다."""


def _topic_block(context: dict) -> str:
    if not context.get("topic"):
        return ""
    return f"\n[구체적 주제 - 반드시 이 주제를 중심으로]\n{context['topic']}"


def _series_brief(series: str, context: dict) -> str:
    topic = context.get("topic", "")
    stem = detect_stem(topic)
    if stem:
        # 천간 주제는 시리즈와 무관하게 사주 풀이로 작성 (MBTI 기본값이 새어 들어가지 않도록)
        brief = (
            f"[사주 천간 시리즈: {stem}]{_topic_block(context)}\n\n{stem_brief(stem)}\n\n"
            "위 사전을 근거로 하되 그대로 복붙하지 말고 주제 맥락(예: 연애/직장)에 맞게 재구성하세요.\n\n"
            f"[참고: 오행 흐름]\n{ELEMENT_FLOW}"
        )
        mbti_in_topic = next((m for m in MBTI_TYPES if m in topic.upper()), None)
        if mbti_in_topic:
            brief += f"\nMBTI {mbti_in_topic}({MBTI_KEYWORDS[mbti_in_topic][0]})와의 교차 포인트도 한 장 포함하세요."
        return brief
    if series == "MBTI":
        mbti = context.get("mbti", "INFP")
        nick, t1, t2 = MBTI_KEYWORDS.get(mbti, ("", "", ""))
        return (
            f"[MBTI×사주 시리즈: {mbti} ({nick})]\n핵심: {t1}, {t2}{_topic_block(context)}\n"
            "MBTI 성향을 어울리는 천간·십신(예: 식신/상관=표현력, 정관=책임감)과 매칭해 교차 분석하고 솔루션으로 마무리\n\n"
            + general_brief()
        )
    if series in ("DAILY", "ELEMENT"):
        el = context.get("element", "목(木)")
        info = FIVE_ELEMENTS.get(el, {})
        return (
            f"[오늘의 오행 운세: {el.split('(')[0]}]\n색상: {info.get('color', '')} | 기운: {info.get('booster', '')}{_topic_block(context)}\n"
            "해당 오행에 속한 두 천간(양/음)의 차이까지 설명 → 상생·상극 관계로 오늘의 실생활 팁\n\n"
            + general_brief()
        )
    label = DOMAIN_LABELS.get(series)
    if label:
        extra = ("\n\n" + general_brief()) if series == "SAJU" else ""
        return f"[{label} 시리즈]\n주제: {topic or f'{label} 특성 TOP 랭킹'}\n{label} 핵심 포인트 해석 → 현실 조언{extra}"
    return f"주제: {topic or '운세 캐러셀'}\n\n{general_brief()}"


def generate_carousel_script(series: str, context: Optional[dict] = None, model_name: Optional[str] = None) -> CarouselScript:
    context = context or {}

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

    last_err = None
    for attempt in (1, 2):
        try:
            return _call_llm(model_name, system_prompt, user_prompt)
        except Exception as e:
            last_err = e
            print(f"[WARN] 캐러셀 대본 생성 시도 {attempt}/2 실패: {e}")
    print(f"[WARNING] 캐러셀 대본 생성 실패 ({last_err}). 폴백 대본 사용.")
    return _fallback(series, context)


def _call_llm(model_name: Optional[str], system_prompt: str, user_prompt: str) -> CarouselScript:
    script = generate_json(system_prompt, user_prompt, CarouselScript, temperature=0.8, model_name=model_name)
    return _normalize(script)


def _normalize(script: CarouselScript) -> CarouselScript:
    """슬라이드 수를 인스타 캐러셀 제한(2~10)과 설계 범위(5~8)에 맞춥니다."""
    if len(script.slides) > MAX_SLIDES:
        # 마지막 CTA 슬라이드는 반드시 보존
        script.slides = script.slides[: MAX_SLIDES - 1] + [script.slides[-1]]
    return script


def _stem_fallback(stem: str, topic: str) -> CarouselScript:
    s = STEMS[stem]
    first = lambda t: t.split(",")[0].split("/")[0].strip()
    return CarouselScript(
        title=f"{topic}, 알고 보면 이런 사람",
        cover_visual_prompt="Horizontal 16:9 landscape, mystical glowing constellations over ancient Korean fortune book, candlelight, cinematic, no text, no letters, no watermark",
        slides=[
            CarouselSlide(headline=f"{topic}, 진짜 속마음은 따로 있다", body=""),
            CarouselSlide(headline=f"{stem}, {first(s['image'])}", body=f"{s['yy']}{s['el']} 기운. {s['core']}이에요."),
            CarouselSlide(headline="이게 매력 포인트", body=s["strength"]),
            CarouselSlide(headline="연애할 때 이런 모습", body=s["love"]),
            CarouselSlide(headline="약점도 알아야 해요", body=s["weak"]),
            CarouselSlide(headline="궁합: 잘 맞는 기운", body=f"{s['match'].split(' / ')[0]} 조심할 조합은 {s['caution'].split(':')[0].split(' / ')[0]}."),
            CarouselSlide(headline="오늘 바로 할 행동 하나", body=s["tip"]),
            CarouselSlide(headline="저장해두고 다시 보기", body="도움이 됐다면 저장하고 팔로우해 주세요. 매일 새로운 사주 포인트를 알려드려요."),
        ],
        instagram_caption=f"{topic}, 겉으로 보이는 모습과 속마음은 달라요. 천간으로 풀어본 연애 패턴, 저장해두고 꺼내 보세요.\n\n#{stem} #사주 #천간 #일간 #연애운세",
    )


def _fallback(series: str, context: dict) -> CarouselScript:
    stem = detect_stem(context.get("topic", ""))
    if stem:
        return _stem_fallback(stem, context["topic"])
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
