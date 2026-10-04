"""
운세 콘텐츠 전용 실시간 토픽 크롤러.
막연한 범용 핫이슈(정치/연예/스포츠 등)가 아니라, 사주/MBTI/신점/자미두수/타로 등
"운세" 카테고리에 직접 속한 실시간 뉴스 헤드라인만 수집하여 릴스 주제를 기획합니다.
"""
import os
import sys
import random
import xml.etree.ElementTree as ET
from typing import Any, Dict, List
import requests
from dotenv import load_dotenv

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

load_dotenv()

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# 크롤링 대상을 "운세" 카테고리로 한정하는 검색 키워드 -> 파이프라인 series 매핑
# ("사주"는 드라마 등에서 '사주하다(교사하다)'는 동음이의 오탐이 잦고, "타로"는 인명(하카세 타로 등)과
#  겹치는 경우가 많아 "운세/카드"를 덧붙여 오탐을 줄임.
FORTUNE_DOMAINS: Dict[str, str] = {
    "사주 운세": "SAJU",
    "MBTI 운세": "MBTI",
    "신점": "SHINJEOM",
    "자미두수": "JAMIDOSU",
    "타로 카드 운세": "TAROT",
}

MBTI_TYPES = [
    "INTJ", "INTP", "ENTJ", "ENTP", "INFJ", "INFP", "ENFJ", "ENFP",
    "ISTJ", "ISFJ", "ESTJ", "ESFJ", "ISTP", "ISFP", "ESTP", "ESFP",
]

# 실시간 크롤링이 완전히 실패할 때(네트워크 차단 등) 사용할 도메인별 백업 시드
FALLBACK_TOPICS: Dict[str, List[str]] = {
    "SAJU": ["2026 병오년 신년운세 화제", "사주로 본 재물운 급상승 시기", "요즘 뜨는 사주 신조어 총정리"],
    "MBTI": ["MBTI별 스트레스 해소법 화제", "요즘 유행하는 MBTI 밈 총정리", "MBTI 궁합 논쟁 재점화"],
    "SHINJEOM": ["신점으로 본 인생 전환점 화두", "요즘 신점 후기 화제", "신점과 사주 차이 궁금증 확산"],
    "JAMIDOSU": ["자미두수 명반으로 본 대운 화제", "자미두수 초심자 관심 급증", "자미두수 궁위 풀이 화제"],
    "TAROT": ["오늘의 타로 카드 화제", "타로로 본 연애운 인기", "타로 카드 상징 해석 화제"],
}


def fetch_domain_topics(query: str, limit: int = 5) -> List[str]:
    """구글 뉴스 한국 RSS에서 특정 검색어(query)로 한정된 헤드라인만 수집합니다."""
    url = f"https://news.google.com/rss/search?q={requests.utils.quote(query)}&hl=ko&gl=KR&ceid=KR:ko"
    topics: List[str] = []
    try:
        res = requests.get(url, headers=HEADERS, timeout=8)
        if res.status_code == 200:
            root = ET.fromstring(res.content)
            for item in root.findall(".//item")[:limit]:
                title_elem = item.find("title")
                if title_elem is not None and title_elem.text:
                    clean_title = title_elem.text.rsplit(" - ", 1)[0].strip()
                    if clean_title and len(clean_title) > 4:
                        topics.append(clean_title)
    except Exception as e:
        print(f"[CRAWLER][WARN] '{query}' 검색 수집 실패: {e}")
    return topics


def get_crawled_fortune_topics() -> Dict[str, List[str]]:
    """
    운세 5개 도메인(사주/MBTI/신점/자미두수/타로) 각각에 대해 실시간 뉴스 검색 결과를 수집합니다.
    반환값 키는 파이프라인 series 이름(SAJU/MBTI/SHINJEOM/JAMIDOSU/TAROT).
    """
    result: Dict[str, List[str]] = {}
    for keyword, series in FORTUNE_DOMAINS.items():
        found = fetch_domain_topics(keyword, limit=5)
        if found:
            result[series] = found
    return result


def _pick_two_series(available: List[str]) -> List[str]:
    """서로 다른 운세 도메인 2개를 선택 (가능하면 실시간 수집분에서, 부족하면 고정 후보로 보강)."""
    pool = list(dict.fromkeys(available))  # 순서 보존 중복 제거
    random.shuffle(pool)
    if len(pool) >= 2:
        return pool[:2]
    fallback_pool = [s for s in ("MBTI", "SAJU", "TAROT", "SHINJEOM", "JAMIDOSU") if s not in pool]
    pool.extend(fallback_pool)
    return pool[:2]


def get_crawled_reels_proposals() -> Dict[str, Any]:
    """
    사주/MBTI/신점/자미두수/타로 등 '운세' 도메인에서만 실시간 트렌드 헤드라인을 크롤링하고,
    서로 다른 2개 도메인을 뽑아 Gemini로 릴스 기획안(A안/B안)을 생성합니다.
    (범용 핫이슈를 억지로 MBTI/사주 틀에 끼워 맞추던 기존 방식과 달리, 애초에 운세 콘텐츠와
    직접 관련된 실시간 화제만 대상으로 합니다.)
    """
    from pipeline.script_gen import get_gemini_client
    from google.genai import types

    crawled = get_crawled_fortune_topics()
    for series, seeds in FALLBACK_TOPICS.items():
        if not crawled.get(series):
            crawled[series] = seeds

    series_a, series_b = _pick_two_series(list(crawled.keys()))
    topic_a = random.choice(crawled.get(series_a, FALLBACK_TOPICS[series_a]))
    topic_b = random.choice(crawled.get(series_b, FALLBACK_TOPICS[series_b]))

    mbti_a = random.choice(MBTI_TYPES) if series_a == "MBTI" else ""
    mbti_b = random.choice(MBTI_TYPES) if series_b == "MBTI" else ""

    def _label(series: str) -> str:
        return {"SAJU": "사주", "MBTI": "MBTI", "SHINJEOM": "신점", "JAMIDOSU": "자미두수", "TAROT": "타로"}.get(series, series)

    # 성과 피드백: 반응이 좋았던 과거 게시물을 '참고 예시'로만 제공 (도메인 선택은 계속 무작위)
    examples_block = ""
    try:
        from pipeline.insights import get_top_examples, format_examples_for_prompt
        examples_block = format_examples_for_prompt(get_top_examples(n=3))
    except Exception as e:
        print(f"[CRAWLER][WARN] 성과 예시 로드 실패(무시): {e}")

    prompt = f"""{examples_block}


다음은 운세(사주/MBTI/신점/자미두수/타로) 카테고리에서만 수집한 실시간 트렌드 헤드라인입니다:
- [{_label(series_a)}] 관련: "{topic_a}"
- [{_label(series_b)}] 관련: "{topic_b}"

이 두 트렌드 헤드라인을 각각 반영하여 인스타그램 릴스/유튜브 숏츠용 기획안 2개(A안, B안)를 기획하세요.
반드시 위에 주어진 카테고리와 헤드라인 내용에 직접 연결되는 구체적 주제여야 하며,
관련 없는 범용 이슈(정치/스포츠/연예 가십 등)로 새지 않도록 하세요.

[요구사항]
- '오늘의 운세' 같은 일일 운세 주제는 금지. 순위(1위/TOP)와 특성을 활용한 주제로 기획하세요.
  예: "슬프면 무조건 눈물 흘리는 MBTI 1위", "올해 남은 3개월 잘되는 사주 특성", "잘 어울리는 MBTI 궁합", "잘 어울리는 사주&MBTI 조합 1위"
- A안: series="{series_a}" ({_label(series_a)}) {"| MBTI 유형: " + mbti_a if mbti_a else ""} — 제목 16자 이내(큰 글씨 2줄 표시), 초반 3초 후킹 대사, 1줄 요약
- B안: series="{series_b}" ({_label(series_b)}) {"| MBTI 유형: " + mbti_b if mbti_b else ""} — 제목 16자 이내(큰 글씨 2줄 표시), 초반 3초 후킹 대사, 1줄 요약

JSON 포맷 예시:
{{
  "option_a": {{"series": "{series_a}", "mbti": "{mbti_a}", "topic": "구체적 주제", "trend_hint": "{topic_a}", "title": "제목", "hook": "후킹 대사", "summary": "1줄 요약"}},
  "option_b": {{"series": "{series_b}", "mbti": "{mbti_b}", "topic": "구체적 주제", "trend_hint": "{topic_b}", "title": "제목", "hook": "후킹 대사", "summary": "1줄 요약"}}
}}
"""

    model_name = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
    client = get_gemini_client()

    try:
        res = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.8,
            )
        )
        raw_text = res.text.strip()
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        if raw_text.startswith("```"):
            raw_text = raw_text[3:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]

        import json
        data = json.loads(raw_text.strip())
        if "option_a" in data and "option_b" in data:
            return data
    except Exception as e:
        print(f"[CRAWLER][WARN] Gemini 크롤링 기획안 생성 에러: {e}")

    # Fallback: Gemini 호출 실패 시 크롤링된 헤드라인을 그대로 주제로 사용
    return {
        "option_a": {
            "series": series_a, "mbti": mbti_a, "topic": topic_a, "trend_hint": topic_a,
            "title": f"{_label(series_a)}로 본 {topic_a[:10]}"[:15],
            "hook": f"요즘 화제인 '{topic_a}', {_label(series_a)}로 풀어드립니다!",
            "summary": f"{_label(series_a)} 관점에서 본 최신 화제 '{topic_a}' 심층 분석",
        },
        "option_b": {
            "series": series_b, "mbti": mbti_b, "topic": topic_b, "trend_hint": topic_b,
            "title": f"{_label(series_b)}로 본 {topic_b[:10]}"[:15],
            "hook": f"요즘 화제인 '{topic_b}', {_label(series_b)}로 풀어드립니다!",
            "summary": f"{_label(series_b)} 관점에서 본 최신 화제 '{topic_b}' 심층 분석",
        },
    }


def classify_custom_topic(text: str) -> Dict[str, str]:
    """
    사용자가 직접 입력한 주제를 파이프라인 series/mbti/topic으로 분류합니다.
    - 텍스트 안의 MBTI 4글자 유형이 있으면 MBTI 시리즈(+해당 유형)
    - 타로/신점/자미두수 키워드가 있으면 해당 시리즈
    - 그 외는 SAJU 시리즈 (운세 도메인 제약 유지)
    """
    import re

    t = text.strip()
    upper = t.upper()
    found = next((m for m in MBTI_TYPES if re.search(rf"(?<![A-Z]){m}(?![A-Z])", upper)), "")
    if found:
        return {"series": "MBTI", "mbti": found, "topic": t}
    if "타로" in t:
        return {"series": "TAROT", "mbti": "", "topic": t}
    if "신점" in t:
        return {"series": "SHINJEOM", "mbti": "", "topic": t}
    if "자미두수" in t:
        return {"series": "JAMIDOSU", "mbti": "", "topic": t}
    if "MBTI" in upper or "엠비티아이" in t:
        return {"series": "MBTI", "mbti": random.choice(MBTI_TYPES), "topic": t}
    return {"series": "SAJU", "mbti": "", "topic": t}


if __name__ == "__main__":
    print("[TEST] 운세 도메인별 실시간 크롤링 테스트:")
    crawled = get_crawled_fortune_topics()
    for series, topics in crawled.items():
        print(f"  [{series}]")
        for t in topics:
            print(f"    - {t}")

    print("\n[TEST] 운세 트렌드 기반 Gemini 기획안 생성:")
    proposals = get_crawled_reels_proposals()
    import json
    print(json.dumps(proposals, ensure_ascii=False, indent=2))
