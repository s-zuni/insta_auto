"""네이버 블로그 SEO/체류시간 최적화 원고 생성기."""
from __future__ import annotations

from ..core import llm
from ..core.schemas import BlogContent
from .matrix_prompt import KOREAN_RULES, Brief


def _mock(brief: Brief) -> BlogContent:
    req = brief.req
    assert req is not None
    title = f"{req.topic} | {req.business_type} 사장님이 알려주는 핵심 정리"
    body = [f"# {title}", "", f"{brief.hook}", "", "## 먼저 결론부터"]
    body += [f"- {p}" for p in brief.key_points]
    for i, p in enumerate(brief.key_points, 1):
        body += ["", f"## {i}. {p}", "(여기에 사진 1장과 현장 경험 2~3문장을 추가하세요.)"]
    body += ["", "## 마무리", brief.cta]
    return BlogContent(
        title=title, body_markdown="\n".join(body), tags=brief.hashtags,
        meta_description=f"{req.topic} 핵심을 {req.business_type} 사장님이 정리했어요.",
    )


async def generate(brief: Brief) -> BlogContent:
    if brief.mock:
        return _mock(brief)
    req = brief.req
    assert req is not None
    system = (
        "당신은 네이버 블로그 SEO 전문 작가입니다. 구조: 제목(핵심 키워드를 앞쪽에) → 결론 요약 → "
        "소제목(##) 3~4개 → 마무리/CTA. 1,200~1,800자, 짧은 문단(2~3문장), 체류시간을 늘리는 "
        "체크리스트/비교 포인트 포함, 사진이 들어갈 자리는 '(사진: 설명)'으로 표시. "
        "키워드 도배 금지.\n" + KOREAN_RULES
    )
    user = (
        f"업종: {req.business_type}\n주제: {req.topic}\n훅: {brief.hook}\n핵심: {brief.key_points}\n"
        f"CTA: {brief.cta}\n추가정보: {req.extra_context or '없음'}\n"
        'JSON 스키마: {"title": str, "body_markdown": str, "tags": [str x8], "meta_description": str}'
    )
    data = await llm.complete_json(system, user, max_tokens=4000)
    if not data or not data.get("body_markdown"):
        return _mock(brief)
    return BlogContent(
        title=str(data.get("title") or req.topic),
        body_markdown=str(data["body_markdown"]),
        tags=[str(t).lstrip("#") for t in data.get("tags", [])][:10],
        meta_description=str(data.get("meta_description", "")),
    )
