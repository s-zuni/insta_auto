"""주제 × 스타일 매트릭스 기반 3종 콘텐츠 동시 기획 엔진.

흐름: GenerateRequest → plan_brief() (공통 기획안) → [shorts / threads / blog] 병렬 생성
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from ..core import llm
from ..core.schemas import (
    BlogContent,
    GeneratedContent,
    GenerateRequest,
    Scene,
    ShortsContent,
    ThreadsContent,
)

# 스타일 프리셋 (Web `lib/presets.ts` 의 STYLES 와 id 를 맞출 것)
STYLE_MATRIX: dict[str, dict[str, str]] = {
    "info": {
        "label": "꿀팁·정보형",
        "angle": "손님이 몰랐던 유용한 정보를 3가지 이내로 압축해서 알려준다",
        "hook": "숫자/반전 질문으로 시작 (예: '이거 모르면 손해예요')",
        "tone": "또렷하고 믿음 가는 전문가 사장님",
    },
    "story": {
        "label": "스토리텔링형",
        "angle": "가게를 시작한 이유·단골과의 일화처럼 짧은 이야기로 공감을 얻는다",
        "hook": "구체적 장면 한 컷으로 시작",
        "tone": "담백하고 따뜻한 1인칭",
    },
    "review": {
        "label": "후기·사례형",
        "angle": "실제 손님 변화/후기를 근거로 신뢰를 만든다 (과장·허위 금지)",
        "hook": "결과부터 보여주기",
        "tone": "차분하고 사실 중심",
    },
    "promo": {
        "label": "프로모션형",
        "angle": "기간·혜택·대상을 명확히 하고 행동(예약/방문)을 유도한다",
        "hook": "혜택/마감을 첫 문장에",
        "tone": "활기차지만 과하지 않게",
    },
    "empathy": {
        "label": "고민공감형",
        "angle": "손님의 흔한 고민을 먼저 말해주고 해결책으로 연결한다",
        "hook": "'~해서 고민이죠?' 공감 질문",
        "tone": "친구 같은 편안한 말투",
    },
}

KOREAN_RULES = (
    "한국어 품질 규칙: 번역투('~에 대해', '~것이 가능하다', '~를 통해') 금지, 피동 남발 금지, "
    "한 문장 40자 안팎, 과장·허위·의학적 효능 단정 표현 금지, 이모지는 채널 규칙에 맞게만."
)


@dataclass
class Brief:
    hook: str
    key_points: list[str]
    cta: str
    hashtags: list[str] = field(default_factory=list)
    req: GenerateRequest | None = None
    mock: bool = False


def _mock_brief(req: GenerateRequest) -> Brief:
    s = STYLE_MATRIX[req.style]
    name = req.brand_name or f"우리 {req.business_type}"
    return Brief(
        hook=f"{req.topic}, 아직도 모르세요?",
        key_points=[
            f"{req.business_type} 사장님이 직접 알려주는 {req.topic} 핵심",
            f"{s['label']}로 풀어낸 현장 경험",
            f"{name}에서 바로 해볼 수 있는 방법",
        ],
        cta=f"더 궁금하면 {name}으로 문의 주세요",
        hashtags=[req.business_type, req.topic.replace(" ", ""), "소상공인", "사장님꿀팁"],
        req=req,
        mock=True,
    )


async def plan_brief(req: GenerateRequest) -> Brief:
    s = STYLE_MATRIX[req.style]
    system = (
        "당신은 소상공인 전문 마케팅 기획자입니다. 한 가지 주제로 숏폼·쓰레드·블로그가 "
        "같은 메시지를 공유하도록 공통 기획안을 만듭니다.\n" + KOREAN_RULES
    )
    user = (
        f"업종: {req.business_type}\n브랜드: {req.brand_name or '미정'}\n주제: {req.topic}\n"
        f"스타일: {s['label']} / 각도: {s['angle']} / 훅: {s['hook']} / 톤: {s['tone']}\n"
        f"추가정보: {req.extra_context or '없음'}\n\n"
        'JSON 스키마: {"hook": str, "key_points": [str, str, str], "cta": str, "hashtags": [str x5]}'
    )
    data = await llm.complete_json(system, user)
    if not data or not data.get("key_points"):
        return _mock_brief(req)
    return Brief(
        hook=str(data.get("hook", "")),
        key_points=[str(x) for x in data["key_points"]][:5],
        cta=str(data.get("cta", "")),
        hashtags=[str(x).lstrip("#") for x in data.get("hashtags", [])][:8],
        req=req,
    )


async def generate_shorts_script(brief: Brief) -> ShortsContent:
    req = brief.req
    assert req is not None
    s = STYLE_MATRIX[req.style]
    if brief.mock:
        points = brief.key_points
        scenes = [Scene(narration=brief.hook, on_screen_text=brief.hook)]
        scenes += [Scene(narration=p, on_screen_text=f"POINT {i}") for i, p in enumerate(points, 1)]
        scenes.append(Scene(narration=brief.cta, on_screen_text="문의 · 예약"))
        return ShortsContent(
            title=brief.hook, scenes=scenes, caption=f"{brief.hook}\n{brief.cta}",
            hashtags=brief.hashtags,
        )
    system = (
        "당신은 15~30초 세로 숏폼 대본 작가입니다. 장면 4~6개, 장면당 narration 1~2문장(40자 안팎).\n"
        + KOREAN_RULES
    )
    user = (
        f"훅: {brief.hook}\n핵심: {brief.key_points}\nCTA: {brief.cta}\n톤: {s['tone']}\n"
        'JSON 스키마: {"title": str, "scenes": [{"narration": str, "on_screen_text": str, '
        '"image_prompt": str}], "caption": str}'
    )
    data = await llm.complete_json(system, user)
    if not data or not data.get("scenes"):
        brief.mock = True
        return await generate_shorts_script(brief)
    return ShortsContent(
        title=str(data.get("title") or brief.hook),
        scenes=[Scene(**{k: str(v) for k, v in sc.items() if k in Scene.model_fields}) for sc in data["scenes"]],
        caption=str(data.get("caption", "")),
        hashtags=brief.hashtags,
    )


async def generate_all(req: GenerateRequest) -> tuple[GeneratedContent, bool]:
    """3종 콘텐츠를 동시에 기획·생성. 반환: (콘텐츠, mock 여부)"""
    from . import blog_gen, threads_gen

    brief = await plan_brief(req)
    shorts, threads, blog = await asyncio.gather(
        generate_shorts_script(brief),
        threads_gen.generate(brief),
        blog_gen.generate(brief),
    )
    assert isinstance(threads, ThreadsContent) and isinstance(blog, BlogContent)
    return GeneratedContent(shorts=shorts, threads=threads, blog=blog), brief.mock
