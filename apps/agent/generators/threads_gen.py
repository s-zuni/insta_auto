"""쓰레드 반말/친근한 사장님 말투 체인 생성기. 글당 500자 이내(Threads 제한)."""
from __future__ import annotations

from ..core import llm
from ..core.schemas import ThreadsContent
from .matrix_prompt import KOREAN_RULES, Brief

MAX_LEN = 500


def _clamp(posts: list[str]) -> list[str]:
    return [p.strip()[:MAX_LEN] for p in posts if p and p.strip()]


def _mock(brief: Brief) -> ThreadsContent:
    posts = [brief.hook, *[f"{i}. {p}" for i, p in enumerate(brief.key_points, 1)], brief.cta]
    return ThreadsContent(posts=_clamp(posts))


async def generate(brief: Brief) -> ThreadsContent:
    if brief.mock:
        return _mock(brief)
    system = (
        "당신은 동네 가게 사장님 계정의 쓰레드 작가입니다. 반말에 가까운 친근한 말투, "
        "이모지 거의 없이, 첫 글은 스크롤을 멈추게 하는 한 줄 훅, 이어지는 글은 한 글당 한 가지 내용. "
        f"총 4~6개 글, 각 {MAX_LEN}자 이내, 마지막 글은 부담 없는 CTA.\n" + KOREAN_RULES
    )
    user = (
        f"훅: {brief.hook}\n핵심: {brief.key_points}\nCTA: {brief.cta}\n"
        'JSON 스키마: {"posts": [str]}'
    )
    data = await llm.complete_json(system, user)
    posts = _clamp([str(p) for p in (data or {}).get("posts", [])])
    return ThreadsContent(posts=posts) if posts else _mock(brief)
