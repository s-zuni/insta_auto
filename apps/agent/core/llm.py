"""Claude API 얇은 래퍼. 키가 없으면 None 을 돌려주고, 호출부가 Mock 으로 폴백한다."""
from __future__ import annotations

import asyncio
import json
import re

from .config import settings


def is_configured() -> bool:
    return bool(settings.anthropic_api_key)


async def complete_text(system: str, user: str, max_tokens: int = 2500) -> str | None:
    if not is_configured():
        return None
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    resp = await asyncio.to_thread(
        client.messages.create,
        model=settings.ai_model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")


async def complete_json(system: str, user: str, max_tokens: int = 2500) -> dict | None:
    """JSON 객체 하나를 기대하는 호출. 파싱 실패 시 None (→ 호출부 Mock 폴백)."""
    text = await complete_text(
        system + "\n\n반드시 설명 없이 유효한 JSON 객체 하나만 출력하세요.", user, max_tokens
    )
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
