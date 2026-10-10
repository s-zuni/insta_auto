"""
콘텐츠 주제별 CTA 매핑 (서비스: MBTIJU / mbtiju.com — 서비스 코드 기준으로 확인된 상품만 언급).

확인된 사실(MBTI-Saju 코드 기준)
- 메인 상품: '3년 심층 사주 리포트' (/premium). 올해 남은 기간 + 내년부터 3개년, 월별 좋은 달·조심할 달, 36개월 운의 지도,
  A4 20장 내외 PDF, 비회원 결제 가능. 결제 전 신청 화면에서 생년월일+성별만 넣으면 분야별(재물·커리어·인연·건강) 점수표 무료 미리보기.
  신청 시 '상대방 정보 포함(궁합 분석)' 옵션, MBTI 융합 선택 가능.
- 가입 없이 30초 무료 체험(일간·오행 요약), 가입 시 크레딧 지급, MBTI x 사주 첫 분석 무료(로그인).
- 크레딧 서비스: 연인 궁합, 재물/취직/이직 사주, 행운 여행지 분석, 타로, 자미두수('나의 수호별 찾기'), KBO 팬궁합.

원칙
- 인스타(릴스/캐러셀)는 '프로필 링크'로만 유도 (URL/가격을 영상·캡션에 쓰지 않음).
- 콘텐츠가 던진 궁금증의 '다음 단계'로 연결: 가벼운 콘텐츠 -> 무료 체험(진입장벽 낮음), 심화 콘텐츠 -> 3년 리포트.
- 코드로 확인되지 않은 문구는 쓰지 않는다: '1,000만 건 데이터', '전문가 수기 점검', 'A4 25장 이상'(현재 랜딩은 20장 내외), '이메일 자동 전달',
  '50% 할인', 이용자 수/만족도. (서비스 랜딩의 표시광고 이슈 소지 -> 운영자 확인 필요)
- narration(음성)에는 한자 금지 — 아래 문구는 모두 한글.
"""
import random
from typing import Tuple

# kind -> [(릴스 마지막 씬 나레이션, 인스타 캡션 CTA, Threads 답글 CTA 템플릿({url}))]
# Threads 템플릿의 {url}은 kind에 따라 premium 또는 메인 주소로 채워진다(pick_threads_cta).
CTA_PLANS = {
    "report3y": [
        ("올해 남은 기간부터 3년 뒤까지 내 운의 점수표는 프로필 링크에서 무료로 먼저 확인해보세요!",
         "👉 프로필 링크에서 올해 남은 기간 + 3개년 점수표를 무료로 먼저 확인하세요! (재물·커리어·인연·건강)",
         "특징만 알면 반쪽이에요\n올해 남은 기간부터 3년 치 재물·커리어·인연·건강 점수표는 신청 화면에서 무료로 볼 수 있어요\n👉 {url}"),
        ("내 앞으로 3년 흐름은 프로필 링크의 3년 심층 사주 리포트에서 확인해보세요!",
         "👉 프로필 링크에서 내 앞으로 3년 흐름, 3년 심층 사주 리포트를 확인하세요!",
         "특징만 알면 반쪽이고, 앞으로 3년 흐름까지 봐야 계획이 서요\n좋은 달 조심할 달까지 담은 3년 심층 사주 리포트\n👉 {url}"),
        ("내 일간이 궁금하면 프로필 링크에서 가입 없이 30초 만에 무료로 확인해보세요!",
         "👉 프로필 링크에서 가입 없이 30초 무료 체험, 내 일간부터 확인하세요!",
         "내 일간이 뭔지부터 궁금하다면\n가입 없이 30초 무료 체험으로 먼저 확인해보세요\n👉 {url}"),
    ],
    "couple": [
        ("우리 둘의 궁합이 궁금하면 프로필 링크에서 연인 궁합을 확인해보세요!",
         "👉 프로필 링크에서 우리 둘의 연인 궁합을 확인하세요!",
         "우리 둘의 궁합이 궁금하다면\n연인 궁합과 상대 정보를 넣는 3년 리포트에서 볼 수 있어요\n👉 {url}"),
    ],
    "career": [
        ("내 일에 맞는 선택과 타이밍은 프로필 링크에서 직업 사주로 확인해보세요!",
         "👉 프로필 링크에서 재물·취직·이직 사주를 확인하세요!",
         "이직이나 일 고민이 있다면\n재물·취직·이직 사주와 3년 흐름에서 확인할 수 있어요\n👉 {url}"),
    ],
    "travel": [
        ("내 사주에 맞는 행운의 여행지는 프로필 링크에서 확인해보세요!",
         "👉 프로필 링크에서 내 행운의 여행지를 확인하세요!",
         "내 사주에 맞는 행운의 여행지가 궁금하다면\n여행지 분석에서 확인할 수 있어요\n👉 {url}"),
    ],
    "mbti_saju": [
        ("내 사주와 MBTI를 겹쳐 본 분석은 프로필 링크에서 첫 분석 무료로 확인해보세요!",
         "👉 프로필 링크에서 내 사주 x MBTI 첫 분석을 무료로 확인하세요! (가입 필요)",
         "사주만 봐도, MBTI만 봐도 반쪽이에요\n두 가지를 겹쳐 보는 분석, 첫 분석은 무료예요 (가입 필요)\n👉 {url}"),
    ],
    "jamidosu": [
        ("내 수호별이 궁금하면 프로필 링크에서 자미두수를 확인해보세요!",
         "👉 프로필 링크에서 내 수호별, 자미두수를 확인하세요!",
         "내 수호별이 궁금하다면\n자미두수 풀이에서 확인할 수 있어요\n👉 {url}"),
    ],
    "tarot": [
        ("지금 내 고민의 답이 궁금하면 프로필 링크에서 타로를 확인해보세요!",
         "👉 프로필 링크에서 내 타로 리딩을 확인하세요!",
         "지금 고민의 답이 궁금하다면\n타로에서 연애·이직 고민별 카드를 뽑아볼 수 있어요\n👉 {url}"),
    ],
}

# 3년 리포트 상세 페이지로 보낼 종류 (나머지는 메인 주소: 무료 체험/각 서비스 진입점)
_PREMIUM_KINDS = {"report3y", "couple", "career"}

_COUPLE_WORDS = ("궁합", "어울", "케미")
_CAREER_WORDS = ("직업", "직장", "커리어", "이직", "적성", "취직", "재물", "돈")
_TRAVEL_WORDS = ("여행",)
_FLOW_WORDS = ("3년", "삼년", "흐름", "대운")


def infer_cta_kind(series: str = "", topic: str = "", category: str = "") -> str:
    """주제/시리즈에서 CTA 종류를 추론. (기획안 DB에 pillar 컬럼이 없어도 동작하도록 텍스트 기반)"""
    s = (series or "").upper()
    t = f"{topic or ''}"
    if s == "JAMIDOSU" or "자미두수" in t:
        return "jamidosu"
    if s == "TAROT" or "타로" in t:
        return "tarot"
    if any(w in t for w in _FLOW_WORDS):
        return "report3y"
    if any(w in t for w in _COUPLE_WORDS) or ("남자" in t and "여자" in t):
        return "mbti_saju" if (s == "MBTI" or "MBTI" in t.upper()) else "couple"
    if any(w in t for w in _TRAVEL_WORDS):
        return "travel"
    if any(w in t for w in _CAREER_WORDS):
        return "career"
    if s == "MBTI" or category == "MBTI":
        return "mbti_saju"
    return "report3y"


def pick_reel_cta(series: str = "", topic: str = "") -> Tuple[str, str]:
    """(나레이션 CTA, 캡션 CTA)"""
    narr, cap, _ = random.choice(CTA_PLANS[infer_cta_kind(series, topic)])
    return narr, cap


def pick_threads_cta(url: str, topic: str = "", category: str = "") -> str:
    """url은 premium 주소(CTA_URL). 3년 리포트 계열이 아니면 메인 주소로 보낸다."""
    series = {"MBTI": "MBTI", "운세": ""}.get(category, "")
    kind = infer_cta_kind(series, topic, category)
    _, _, tpl = random.choice(CTA_PLANS[kind])
    target = url if kind in _PREMIUM_KINDS else url.rsplit("/premium", 1)[0]
    return tpl.format(url=target)
