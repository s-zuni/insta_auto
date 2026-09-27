"""
Real-time Internet Topic Scraper & Proposal Generator.
Crawls Google News KR, Google Trends KR, and popular Korean portals to generate fresh, viral MBTI x Saju topics.
"""
import os
import sys
import xml.etree.ElementTree as ET
import requests
import random
from typing import List, Dict, Any
from dotenv import load_dotenv

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def fetch_google_news_topics(limit: int = 8) -> List[str]:
    """구글 뉴스 한국 RSS에서 최신 헤드라인 수집"""
    url = "https://news.google.com/rss?hl=ko&gl=KR&ceid=KR:ko"
    topics = []
    try:
        res = requests.get(url, headers=HEADERS, timeout=8)
        if res.status_code == 200:
            root = ET.fromstring(res.content)
            for item in root.findall(".//item")[:limit]:
                title_elem = item.find("title")
                if title_elem is not None and title_elem.text:
                    clean_title = title_elem.text.rsplit(" - ", 1)[0].strip()
                    if clean_title and len(clean_title) > 5:
                        topics.append(clean_title)
    except Exception as e:
        print(f"[CRAWLER][WARN] Google News 수집 실패: {e}")
    return topics


def fetch_google_trends_topics(limit: int = 8) -> List[str]:
    """구글 트렌드 한국 RSS에서 실시간 트렌드 키워드 수집"""
    url = "https://trends.google.com/trending/rss?geo=KR"
    topics = []
    try:
        res = requests.get(url, headers=HEADERS, timeout=8)
        if res.status_code == 200:
            root = ET.fromstring(res.content)
            for item in root.findall(".//item")[:limit]:
                title_elem = item.find("title")
                if title_elem is not None and title_elem.text:
                    kw = title_elem.text.strip()
                    if kw:
                        topics.append(kw)
    except Exception as e:
        print(f"[CRAWLER][WARN] Google Trends 수집 실패: {e}")
    return topics


def get_crawled_keywords() -> List[str]:
    """실시간 뉴스 및 트렌드 키워드를 통합 수집"""
    news = fetch_google_news_topics(limit=6)
    trends = fetch_google_trends_topics(limit=6)

    combined = news + trends
    if not combined:
        # 크롤링 실패 시 다양성을 보장하는 백업 트렌드 키워드
        combined = [
            "2026 병오년 재물운 대박 조짐",
            "직장인 스트레스 극복 심리",
            "MBTI별 연애 이탈 신호",
            "인간관계 피로도 줄이는 법",
            "소울메이트 사주 오행 궁합",
            "2026년 하반기 터지는 운세"
        ]
    random.shuffle(combined)
    return combined[:10]


def get_crawled_reels_proposals() -> Dict[str, Any]:
    """
    실시간 인터넷 트렌드 키워드를 바탕으로 Gemini를 통해
    2가지(A안: MBTI 트렌드, B안: 사주/운세 트렌드) 맞춤 기획안을 수집/생성합니다.
    """
    from pipeline.script_gen import get_gemini_client
    from google.genai import types

    keywords = get_crawled_keywords()
    keywords_str = ", ".join([f"'{k}'" for k in keywords])

    mbti_types = ["INTJ", "INTP", "ENTJ", "ENTP", "INFJ", "INFP", "ENFJ", "ENFP",
                  "ISTJ", "ISFJ", "ESTJ", "ESFJ", "ISTP", "ISFP", "ESTP", "ESFP"]
    elements = ["목(木)", "화(火)", "토(土)", "금(金)", "수(水)"]

    selected_mbti = random.choice(mbti_types)
    selected_element = random.choice(elements)

    prompt = f"""
다음은 인터넷에서 최근 수집된 실시간 핫 트렌드/뉴스 키워드 리스트입니다:
[{keywords_str}]

이 트렌드 주제들과 시청자의 호기심을 접목하여 인스타그램 릴스/유튜브 숏츠용 기획안 2개(A안, B안)를 기획하세요.

[요구사항]
- A안: {selected_mbti} MBTI와 실시간 트렌드/심리를 결합한 주제 (제목 15자이내, 초반 3초 후킹, 1줄 요약)
- B안: {selected_element} 오행/사주 운세와 실시간 트렌드/재물/연애를 결합한 주제 (제목 15자이내, 초반 3초 후킹, 1줄 요약)

JSON 포맷 예시:
{{
  "option_a": {{
    "series": "MBTI",
    "mbti": "{selected_mbti}",
    "element": "",
    "title": "제목 15자이내",
    "hook": "초반 3초 후킹 대사",
    "summary": "1줄 요약"
  }},
  "option_b": {{
    "series": "DAILY",
    "mbti": "",
    "element": "{selected_element}",
    "title": "제목 15자이내",
    "hook": "초반 3초 후킹 대사",
    "summary": "1줄 요약"
  }}
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

    # Fallback
    return {
        "option_a": {
            "series": "MBTI",
            "mbti": selected_mbti,
            "element": "",
            "title": f"트렌드로 본 {selected_mbti} 심리",
            "hook": f"{selected_mbti}라면 이 트렌드 꼭 확인하세요!",
            "summary": f"최신 이슈로 풀어보는 {selected_mbti}의 솔직한 반응"
        },
        "option_b": {
            "series": "DAILY",
            "mbti": "",
            "element": selected_element,
            "title": f"2026 {selected_element} 기운 트렌드 운세",
            "hook": f"오늘 {selected_element} 기운이 강한 당신의 대박 운세!",
            "summary": f"{selected_element} 오행 흐름과 실시간 재물/연애 꿀팁"
        }
    }


if __name__ == "__main__":
    print("[TEST] 트렌드 키워드 크롤링 테스트:")
    kw_list = get_crawled_keywords()
    for idx, kw in enumerate(kw_list, 1):
        print(f"  {idx}. {kw}")

    print("\n[TEST] 트렌드 기반 Gemini 기획안 생성:")
    proposals = get_crawled_reels_proposals()
    import json
    print(json.dumps(proposals, ensure_ascii=False, indent=2))
