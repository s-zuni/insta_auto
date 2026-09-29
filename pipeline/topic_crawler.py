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

# 크롤링 검색 키워드 -> 파이프라인 series 매핑
# 단순 "오늘의 운세"를 완전히 배제하고 순위/특성/궁합/조합 중심으로 크롤링
FORTUNE_DOMAINS: Dict[str, str] = {
    "MBTI 순위": "MBTI",
    "사주 특성 대박": "SAJU",
    "MBTI 궁합": "MBTI",
    "사주 MBTI 조합": "MBTI",
}

MBTI_TYPES = [
    "INTJ", "INTP", "ENTJ", "ENTP", "INFJ", "INFP", "ENFJ", "ENFP",
    "ISTJ", "ISFJ", "ESTJ", "ESFJ", "ISTP", "ISFP", "ESTP", "ESFP",
]

# 오늘의 운세 제거 -> 순위/특성/궁합/조합 중심의 시드 토픽
FALLBACK_TOPICS: Dict[str, List[str]] = {
    "MBTI": [
        "슬프면 무조건 눈물 흘리는 MBTI 1위",
        "화나면 손절 제일 빠른 MBTI 순위",
        "돈 제일 잘 모으는 MBTI TOP 3",
        "멘탈 절대 안 깨지는 MBTI 1위",
        "잘어울리는 MBTI 궁합",
        "잘 어울리는 사주&MBTI 조합 1위",
        "남 눈치 제일 안 보는 MBTI 순위"
    ],
    "SAJU": [
        "올해 남은 3개월 잘되는 사주 특성",
        "초년 고생 끝에 말년 대박 나는 사주 특징",
        "평생 재물복 마르지 않는 사주 특성",
        "2026 병오년 대운 들어오는 사주 오행",
        "인복 타고나서 귀인 끊이지 않는 사주 특성",
        "잘 어울리는 사주&MBTI 조합 1위"
    ],
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

    prompt = f"""
당신은 인스타그램 릴스와 유튜브 숏츠에서 폭발적인 조회수를 기록하는 바이럴 숏폼 기획 전문가입니다.
다음 수집 키워드를 참고하여, 시청자의 클릭을 유발하는 릴스 기획안 2개(A안, B안)를 작성하세요:
- A안 참고: "{topic_a}"
- B안 참고: "{topic_b}"

[핵심 규칙 - 절대 준수]
1. '오늘의 운세', '일일 운세', '오늘의 기운' 같은 밋밋한 일일 운세 주제는 완전히 금지합니다.
2. 반드시 아래 4가지 유형(순위, 특정 기간/상황 특성, 궁합, 사주&MBTI 조합) 중 하나로 기획하세요:
   - 순위: "슬프면 무조건 눈물 흘리는 MBTI 1위", "화나면 손절 제일 빠른 MBTI 순위", "멘탈 절대 안 깨지는 MBTI 1위", "돈 제일 잘 모으는 MBTI TOP 3"
   - 특성: "올해 남은 3개월 잘되는 사주 특성", "초년 고생 끝에 말년 대박 나는 사주 특징", "평생 재물복 마르지 않는 사주 특성"
   - 궁합: "잘어울리는 MBTI 궁합", "만나면 서로 인생 풀리는 MBTI 조합 TOP 3", "의외로 천생연분인 MBTI 궁합"
   - 조합: "잘 어울리는 사주&MBTI 조합 1위", "재물복 폭발하는 사주와 MBTI 찰떡 조합"
3. 제목(title): 15자 이내의 강력하고 직관적인 제목 (순위나 특성이 명확히 드러나야 함)
4. 후킹(hook): 초반 3초에 시청자를 사로잡는 강력한 후킹 멘트
5. 요약(summary): 1줄 핵심 요약

JSON 포맷:
{{
  "option_a": {{"series": "{series_a}", "mbti": "{mbti_a}", "topic": "구체적 주제", "trend_hint": "{topic_a}", "title": "제목(15자이내)", "hook": "후킹 대사", "summary": "1줄 요약"}},
  "option_b": {{"series": "{series_b}", "mbti": "{mbti_b}", "topic": "구체적 주제", "trend_hint": "{topic_b}", "title": "제목(15자이내)", "hook": "후킹 대사", "summary": "1줄 요약"}}
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
