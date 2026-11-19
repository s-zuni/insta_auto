"""한국어 금지어 규칙(core/copy_rules.py) 테스트. 네트워크·API 키 없이 동작."""
import pytest
from fastapi.testclient import TestClient

from apps.agent.core.config import settings
from apps.agent.core.copy_rules import find_violations, prompt_rules
from apps.agent.main import app


@pytest.mark.parametrize(("text", "category"), [
    ("원두 보관에 대해 알려드릴게요", "번역투"),
    ("앱을 통해 예약하세요", "번역투"),
    ("주차가 가능한 것이 가능합니다", "번역투"),
    ("관리하는 것이 중요합니다", "번역투"),
    ("매장이 리뉴얼되어졌습니다", "번역투"),
    ("업계 1위 미용실", "과장광고"),
    ("역대급 할인", "과장광고"),
    ("100% 만족 보장", "과장광고"),
    ("두피가 치료됩니다", "효능단정"),
    ("한 달이면 살이 빠집니다", "효능단정"),
    ("부작용 없는 시술", "효능단정"),
])
def test_detects_banned(text: str, category: str) -> None:
    hits = find_violations(text)
    assert hits, f"못 잡음: {text}"
    assert hits[0].category == category


@pytest.mark.parametrize("text", [
    "원두는 밀폐 용기에 넣어 서늘한 곳에 두세요.",
    "이번 주 금요일까지 아메리카노 1+1이에요.",
    "펌 하고 이틀은 머리 감지 마세요.",
    "매일 아침 직접 로스팅해요.",
])
def test_clean_copy_passes(text: str) -> None:
    assert find_violations(text) == []


def test_line_numbers() -> None:
    hits = find_violations("첫 줄은 괜찮아요\n둘째 줄은 최고의 맛")
    assert [v.line for v in hits] == [2]


def test_prompt_rules_mentions_all_categories() -> None:
    rules = prompt_rules()
    for word in ("번역투", "과장", "효능"):
        assert word in rules


@pytest.mark.parametrize("style", ["info", "story", "review", "promo", "empathy"])
def test_mock_output_has_no_banned_phrases(monkeypatch: pytest.MonkeyPatch, style: str) -> None:
    """Mock 콘텐츠(데모 시연에 그대로 노출됨)부터 금지어가 없어야 한다."""
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    monkeypatch.setattr(settings, "license_enforce", False)
    body = TestClient(app).post("/api/generate", json={
        "business_type": "미용실", "topic": "손상모 관리 루틴", "style": style, "render_video": False,
    }).json()
    c = body["content"]
    texts = [c["blog"]["title"], c["blog"]["body_markdown"], *c["threads"]["posts"],
             *(s["narration"] for s in c["shorts"]["scenes"]), c["shorts"]["caption"]]
    hits = [v for t in texts for v in find_violations(t)]
    assert hits == [], hits
