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
# 크롤링 검색 키워드 -> 파이프라인 series 매핑
# '오늘의 운세' 같은 일일 운세를 피하고, 순위/특성/궁합/대운 중심 키워드로 검색합니다.
FORTUNE_DOMAINS: Dict[str, str] = {
    "MBTI 순위": "MBTI",
    "MBTI 특징": "MBTI",
    "MBTI 궁합": "MBTI",
    "사주 특징": "SAJU",
    "사주 궁합": "SAJU",
    "사주 대운": "SAJU",
}

MBTI_TYPES = [
    "INTJ", "INTP", "ENTJ", "ENTP", "INFJ", "INFP", "ENFJ", "ENFP",
    "ISTJ", "ISFJ", "ESTJ", "ESFJ", "ISTP", "ISFP", "ESTP", "ESFP",
]

# '오늘의 운세' 등 일일 운세성 기사를 걸러내기 위한 금지어 목록
FORBIDDEN_KEYWORDS = [
    "오늘의", "일진", "띠별", "운세 보기", "일일", "오늘의운세", "내일의", "주간운세", "월간운세", "오늘 운세", "10월"
]

# 실시간 크롤링 실패 또는 필터링 시 사용할 엄선된 시드 (순위 / 특성 / 궁합 위주)
FALLBACK_TOPICS: Dict[str, List[str]] = {
    "MBTI": [
        "슬프면 무조건 눈물 흘리는 MBTI 1위",
        "잘 어울리는 MBTI 궁합 TOP 3",
        "화나면 뒤도 안 돌아보는 MBTI 순위",
        "겉은 차가운데 속은 여린 반전 MBTI",
        "멘탈 가장 단단한 MBTI 순위",
        "좋아하는 사람 앞에서 삐걱대는 MBTI 1위",
    ],
    "SAJU": [
        "올해 남은 3개월 잘되는 사주 특성",
        "잘 어울리는 사주&MBTI 조합 1위",
        "재물운 터지는 사주 오행 특징",
        "귀인 복 타고난 사주 일주 특징",
        "하반기 운세 확 풀리는 사주 유형",
        "돈 복 타고났는데 잘 모르는 사주 특징",
    ],
}


def fetch_domain_topics(query: str, limit: int = 5) -> List[str]:
    """구글 뉴스 한국 RSS에서 특정 검색어(query)로 한정된 헤드라인을 수집하며, '오늘의 운세'류는 제외합니다."""
    url = f"https://news.google.com/rss/search?q={requests.utils.quote(query)}&hl=ko&gl=KR&ceid=KR:ko"
    topics: List[str] = []
    try:
        res = requests.get(url, headers=HEADERS, timeout=8)
        if res.status_code == 200:
            root = ET.fromstring(res.content)
            for item in root.findall(".//item"):
                title_elem = item.find("title")
                if title_elem is not None and title_elem.text:
                    clean_title = title_elem.text.rsplit(" - ", 1)[0].strip()
                    if not clean_title or len(clean_title) < 5:
                        continue
                    # 금지어 포함 시 제외
                    if any(bad in clean_title for bad in FORBIDDEN_KEYWORDS):
                        continue
                    topics.append(clean_title)
                    if len(topics) >= limit:
                        break
    except Exception as e:
        print(f"[CRAWLER][WARN] '{query}' 검색 수집 실패: {e}")
    return topics


def get_crawled_fortune_topics() -> Dict[str, List[str]]:
    """
    MBTI 및 사주 도메인에 대해 실시간 뉴스 검색 결과를 수집합니다.
    """
    result: Dict[str, List[str]] = {}
    for keyword, series in FORTUNE_DOMAINS.items():
        found = fetch_domain_topics(keyword, limit=3)
        if found:
            result.setdefault(series, []).extend(found)
    return result


def _pick_two_series(available: List[str]) -> List[str]:
    """A안, B안으로 사용할 시리즈 2개를 선택합니다 (MBTI와 SAJU 조합 우선)."""
    pool = list(dict.fromkeys(available))
    if "MBTI" in pool and "SAJU" in pool:
        return ["MBTI", "SAJU"]
    if len(pool) >= 2:
        random.shuffle(pool)
        return pool[:2]
    return ["MBTI", "SAJU"]


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

    system_instruction = """당신은 대한민국 인스타그램 릴스 및 유튜브 숏츠 전문 숏폼 기획자입니다.
20~30대 여성이 클릭하지 않고는 못 배기는 호기심 유발형 숏폼 기획안(A안, B안)을 작성합니다.

[주제 규칙 - 필수 엄수]
1. '오늘의 운세', '일일 운세', 날짜(X월 X일), 일진, 띠별 운세는 절대 금지합니다.
2. 반드시 아래 4가지 유형 중 하나로만 기획하세요:
   - [순위형] 특정 상황/성격에서 극단적인 반응을 보이는 MBTI 1위 (예: "슬프면 무조건 눈물 흘리는 MBTI 1위")
   - [특성형] 특정 시기/대운에 잘 풀리는 사주 오행/십신/일주 특성 (예: "올해 남은 3개월 잘되는 사주 특성")
   - [궁합형] 환상의 호흡을 자랑하는 MBTI 궁합 (예: "잘 어울리는 MBTI 궁합")
   - [조합형] 사주와 MBTI가 만나 대박 나는 조합 (예: "잘 어울리는 사주&MBTI 조합 1위")
3. 제목(title): 공백 포함 16자 이내로 짧고 강렬하게. 줄바꿈(\\n)은 절대 넣지 마세요.
4. 후킹(hook): 초반 3초에 시청자를 붙잡는 강렬한 대사.
5. 요약(summary): 1줄 핵심 요약."""

    prompt = f"""{examples_block}

참고할 실시간 트렌드/화제 키워드:
- [{_label(series_a)}] 관련: "{topic_a}"
- [{_label(series_b)}] 관련: "{topic_b}"

위 트렌드를 참고하여 순위/특성/궁합/조합 유형의 숏폼 기획안 2개(A안, B안)를 작성하세요.
- A안: series="{series_a}" ({_label(series_a)}) {"| MBTI 유형: " + mbti_a if mbti_a else ""}
- B안: series="{series_b}" ({_label(series_b)}) {"| MBTI 유형: " + mbti_b if mbti_b else ""}

JSON 포맷:
{{
  "option_a": {{"series": "{series_a}", "mbti": "{mbti_a}", "topic": "구체적 주제(순위/특성/궁합/조합)", "trend_hint": "{topic_a}", "title": "16자이내제목", "hook": "초반3초 후킹 대사", "summary": "1줄 요약"}},
  "option_b": {{"series": "{series_b}", "mbti": "{mbti_b}", "topic": "구체적 주제(순위/특성/궁합/조합)", "trend_hint": "{topic_b}", "title": "16자이내제목", "hook": "초반3초 후킹 대사", "summary": "1줄 요약"}}
}}"""

    model_name = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
    client = get_gemini_client()

    def _sanitize_opt(opt: dict, default_series: str, default_mbti: str, default_topic: str) -> dict:
        title = str(opt.get("title", "")).replace("\n", " ").strip()
        topic = str(opt.get("topic", "")).replace("\n", " ").strip()
        hook = str(opt.get("hook", "")).strip()
        summary = str(opt.get("summary", "")).strip()
        series = opt.get("series") or default_series
        mbti = opt.get("mbti") or default_mbti

        # 금지어 포함 여부 검증
        if any(bad in title for bad in FORBIDDEN_KEYWORDS) or any(bad in topic for bad in FORBIDDEN_KEYWORDS) or not title:
            fb = random.choice(FALLBACK_TOPICS.get(series, FALLBACK_TOPICS["MBTI"]))
            title = fb[:16]
            topic = fb
            hook = f"{fb}, 여러분은 몇 위인가요?"
            summary = f"{fb}에 대한 심층 분석 및 대처법"

        if len(title) > 16:
            title = title[:16].strip()

        return {
            "series": series,
            "mbti": mbti,
            "topic": topic,
            "trend_hint": opt.get("trend_hint") or default_topic,
            "title": title,
            "hook": hook,
            "summary": summary,
        }

    try:
        res = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                temperature=0.6,
            )
        )
        raw_text = res.text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        import json
        data = json.loads(raw_text)
        if "option_a" in data and "option_b" in data:
            data["option_a"] = _sanitize_opt(data["option_a"], series_a, mbti_a, topic_a)
            data["option_b"] = _sanitize_opt(data["option_b"], series_b, mbti_b, topic_b)
            return data
    except Exception as e:
        print(f"[CRAWLER][WARN] Gemini 크롤링 기획안 생성 에러: {e}")

    # Fallback: 검증된 엄선 시드 템플릿 사용
    fb_a = random.choice(FALLBACK_TOPICS.get(series_a, FALLBACK_TOPICS["MBTI"]))
    fb_b = random.choice(FALLBACK_TOPICS.get(series_b, FALLBACK_TOPICS["SAJU"]))
    return {
        "option_a": {
            "series": series_a, "mbti": mbti_a, "topic": fb_a, "trend_hint": topic_a,
            "title": fb_a[:16],
            "hook": f"{fb_a}, 여러분은 어떻게 생각하시나요?",
            "summary": f"{fb_a}의 핵심 포인트와 현실 조언",
        },
        "option_b": {
            "series": series_b, "mbti": mbti_b, "topic": fb_b, "trend_hint": topic_b,
            "title": fb_b[:16],
            "hook": f"{fb_b}, 여러분은 어떻게 생각하시나요?",
            "summary": f"{fb_b}의 핵심 포인트와 현실 조언",
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
