"""
콘텐츠 주제별 바이럴 알고리즘 트리거 + 고전환 CTA 매핑 (서비스: MBTIJU / mbtiju.com — 서비스 코드 기준으로 확인된 상품만 언급).

확인된 사실(MBTI-Saju 코드 기준)
- 메인 상품: '3년 심층 사주 리포트' (/premium). 올해 남은 기간 + 내년부터 3개년, 월별 좋은 달·조심할 달, 36개월 운의 지도,
  A4 20장 내외 PDF, 비회원 결제 가능. 결제 전 신청 화면에서 생년월일+성별만 넣으면 분야별(재물·커리어·인연·건강) 점수표 무료 미리보기.
  신청 시 '상대방 정보 포함(궁합 분석)' 옵션, MBTI 융합 선택 가능.
- 가입 없이 30초 무료 체험(일간·오행 요약), 가입 시 크레딧 지급, MBTI x 사주 첫 분석 무료(로그인).
- 크레딧 서비스: 연인 궁합, 재물/취직/이직 사주, 행운 여행지 분석, 타로, 자미두수('나의 수호별 찾기'), KBO 팬궁합.
- 신규 상품: 카카오톡 채널 1:1 사주·MBTI 상담
  - 상품: 한 가지 고민 상담 9,900원 (질문 1개) / 3문항 상담 19,900원
  - 채널 주소: https://pf.kakao.com/_xcdXJX/chat (환경변수 KAKAO_CHAT_URL로 덮어쓰기 가능)
  - 진행: 채널 채팅방에서 접수 양식 작성 -> 계좌이체 -> 입금 확인 후 평일 기준 24시간 이내 답변을 채팅방으로 전달
  - 접수는 24시간 가능, 회원가입 불필요
  - 답변 발송 전에는 전액 환불
  - 답변 방식: "AI 분석을 바탕으로 운세 서비스 전문가가 직접 검수" (이 표현만 사용)
  - 실시간/예약 상담은 준비 중이므로 언급 금지

100만 바이럴 CTA 3중 트리거 원칙
1. 공유/저장 트리거 (DM sends & Saves): "주변에 딱 떠오르는 친구한테 바로 보내주세요" -> 인스타 도달 알고리즘 1순위 신호
2. 댓글 키워드 트리거 (Comment Velocity): "댓글에 사주 남기거나..." -> 비팔로워 탐색탭/릴스탭 확산 가속 (단, 자동 전송/발송 약속 금지)
3. 프로필 링크 직결 (Conversion): "...급하신 분은 프로필 링크에서 30초 만에 무료로 먼저 확인해보세요!"
- 인스타(릴스/캐러셀)에는 URL/가격을 직접 쓰지 않음 (프로필 링크로만 안내).
- 코드로 확인되지 않은 과장 문구('1,000만 건 데이터', '전문가 수기 점검', 'A4 25장 이상', '50% 할인', '즉시 답변' 등) 절대 금지.
- narration(음성)에는 한자 금지 — 아래 문구는 모두 순수 한글.
"""
import os
import random
import re
from typing import Optional, Tuple

# 카카오톡 채널 1:1 상담 주소 (환경변수로 덮어쓰기 가능)
KAKAO_CHAT_URL = os.getenv("KAKAO_CHAT_URL", "https://pf.kakao.com/_xcdXJX/chat")

# kind -> [(릴스 마지막 씬 나레이션, 인스타 캡션 CTA, Threads 답글 CTA 템플릿({url}))]
# Threads 템플릿의 {url}은 kind에 따라 kakao chat, premium 또는 메인 주소로 채워진다(pick_threads_cta).
CTA_PLANS = {
    "consult": [
        ("혼자 끙끙 앓던 고민의 답이 궁금하면 댓글에 상담 남기거나 프로필 링크에서 카톡 일대일 상담을 확인해보세요!",
         "💬 댓글에 [상담] 남겨주세요!\n👉 프로필 링크에서 카톡 1:1 상담으로 내 고민을 바로 물어보세요!",
         "혼자 끙끙 앓던 고민 하나, 사주랑 MBTI로 바로 풀어봐\n카톡 1:1 상담 (한 가지 고민 9,900원부터)\nAI 분석을 바탕으로 운세 서비스 전문가가 직접 검수해 평일 기준 24시간 이내 답변해줌\n{url}"),
        ("내 연애와 이직 고민의 진짜 해답은 댓글에 상담 남기거나 프로필 링크에서 카톡 일대일 상담으로 확인해보세요!",
         "💬 댓글에 [상담] 남기거나\n👉 혼자 끙끙 앓지 말고, 프로필 링크에서 카톡 1:1 상담으로 바로 확인하세요!",
         "지금 제일 답답한 그 고민 하나만 짚어서 물어봐\n카톡 채널 1:1 사주·MBTI 상담 (9,900원부터)\nAI 분석을 바탕으로 운세 서비스 전문가가 직접 검수해 평일 기준 24시간 이내 전달 (24시간 접수 가능, 회원가입 불필요)\n{url}"),
        ("지금 내 고민의 결정적 타이밍이 궁금하면 댓글에 상담 남기거나 프로필 링크에서 카톡 일대일 상담으로 물어보세요!",
         "💬 댓글에 [상담] 남겨주세요!\n👉 프로필 링크에서 카톡 1:1 사주·MBTI 상담으로 답답한 고민의 답을 찾아보세요!",
         "재회, 썸, 이직... 답답한 고민 있다면\n카톡 1:1 상담으로 물어봐 (질문 1개 9,900원 / 3문항 19,900원)\nAI 분석을 바탕으로 운세 서비스 전문가가 직접 검수한 답변을 평일 24시간 이내 채팅방으로 보내줌\n{url}"),
    ],
    "report3y": [
        ("댓글에 사주라고 남기거나 프로필 링크에서 올해부터 삼 년 치 내 운의 점수표를 무료로 먼저 확인해보세요!",
         "💬 댓글에 [사주] 남겨주세요!\n👉 급하신 분은 프로필 링크에서 올해 남은 기간 + 3개년 점수표를 무료로 먼저 확인하세요! (재물·커리어·인연·건강)",
         "성격 특징만 알면 반쪽임\n올해 남은 기간부터 3년 치 재물·커리어·인연·건강 점수표는 신청 화면에서 무료로 볼 수 있음\n{url}"),
        ("댓글에 사주 남기거나 프로필 링크의 삼 년 심층 사주 리포트에서 내 앞으로 삼 년 흐름을 확인해보세요!",
         "💬 댓글에 [사주] 남기거나\n👉 프로필 링크에서 내 앞으로 3년 흐름, 3년 심층 사주 리포트를 바로 확인하세요!",
         "특징만 알면 반쪽이고 앞으로 3년 흐름까지 봐야 계획이 섬\n좋은 달 조심할 달까지 담은 3년 심층 사주 리포트\n{url}"),
        ("내 일간이 뭔지 궁금하면 댓글에 사주 남기거나 프로필 링크에서 가입 없이 삼십 초 만에 무료로 확인해보세요!",
         "💬 댓글에 [사주] 남겨주세요!\n👉 프로필 링크에서 가입 없이 30초 무료 체험으로 내 일간부터 확인하세요!",
         "내 일간이 뭔지부터 궁금하면\n가입 없이 30초 무료 체험으로 먼저 확인해봐\n{url}"),
    ],
    "couple": [
        ("우리 둘의 진짜 궁합이 궁금하면 댓글에 궁합 남기거나 프로필 링크에서 연인 궁합을 확인해보세요!",
         "💬 댓글에 [궁합] 남기거나\n👉 프로필 링크에서 우리 둘의 연인 궁합을 바로 확인하세요!",
         "우리 둘 궁합이 진짜 궁금하면\n연인 궁합이랑 상대 정보 넣는 3년 리포트에서 볼 수 있음\n{url}"),
    ],
    "career": [
        ("내 일과 돈이 풀리는 타이밍은 댓글에 사주 남기거나 프로필 링크에서 직업 사주로 확인해보세요!",
         "💬 댓글에 [사주] 남기거나\n👉 프로필 링크에서 재물·취직·이직 사주를 바로 확인하세요!",
         "이직이나 일 고민 있으면\n재물·취직·이직 사주랑 3년 흐름에서 확인할 수 있음\n{url}"),
    ],
    "travel": [
        ("내 사주에 맞는 행운의 여행지는 댓글에 사주 남기거나 프로필 링크에서 확인해보세요!",
         "💬 댓글에 [사주] 남기거나\n👉 프로필 링크에서 내 행운의 여행지를 바로 확인하세요!",
         "내 사주에 맞는 행운의 여행지가 궁금하면\n여행지 분석에서 확인할 수 있음\n{url}"),
    ],
    "mbti_saju": [
        ("내 생년월일과 MBTI 조합의 삼 년 운세와 솔루션은 댓글에 분석 남기거나 프로필 링크에서 확인해보세요!",
         "💬 댓글에 [분석] 남겨주세요!\n👉 프로필 링크에서 내 생년월일 x MBTI 조합의 3년 운세와 솔루션을 무료로 확인하세요!",
         "내 생년월일이랑 MBTI를 결합한 진짜 사주 분석\n앞으로 3년 운의 흐름과 맞춤 솔루션을 지금 확인해봐\n{url}"),
        ("내 사주와 MBTI를 겹쳐 본 분석은 댓글에 분석 남기거나 프로필 링크에서 첫 분석 무료로 확인해보세요!",
         "💬 댓글에 [분석] 남기거나\n👉 프로필 링크에서 내 사주 x MBTI 첫 분석을 무료로 확인하세요!",
         "사주만 봐도, MBTI만 봐도 반쪽임\n두 가지를 겹쳐 보는 분석, 앞으로 3년 운세와 솔루션\n{url}"),
    ],
    "jamidosu": [
        ("내 수호별이 궁금하면 댓글에 사주 남기거나 프로필 링크에서 자미두수를 확인해보세요!",
         "💬 댓글에 [사주] 남기거나\n👉 프로필 링크에서 내 수호별, 자미두수를 바로 확인하세요!",
         "내 수호별이 궁금하면\n자미두수 풀이에서 확인할 수 있음\n{url}"),
    ],
    "tarot": [
        ("지금 내 고민의 답이 궁금하면 댓글에 타로 남기거나 프로필 링크에서 타로를 확인해보세요!",
         "💬 댓글에 [타로] 남기거나\n👉 프로필 링크에서 내 타로 리딩을 바로 확인하세요!",
         "지금 고민의 답이 궁금하면\n타로에서 연애·이직 고민별 카드를 뽑아볼 수 있음\n{url}"),
    ],
}

# 3년 리포트 상세 페이지로 보낼 종류 (나머지는 메인 주소: 무료 체험/각 서비스 진입점, consult는 카톡 채널)
_PREMIUM_KINDS = {"report3y", "couple", "career"}

# 고민형 주제 판별 키워드 (재회, 이별, 썸, 연락, 짝사랑, 결혼 고민, 이직/퇴사 고민, 어떡해 등)
_CONSULT_WORDS = ("재회", "이별", "헤어", "썸", "연락", "답장", "짝사랑", "고민", "퇴사", "어떡해", "미련", "속마음")

_COUPLE_WORDS = ("궁합", "어울", "케미")
_CAREER_WORDS = ("직업", "직장", "커리어", "이직", "적성", "취직", "재물", "돈")
_TRAVEL_WORDS = ("여행",)
_FLOW_WORDS = ("3년", "삼년", "흐름", "대운")


def _consult_ratio() -> float:
    """고민형 주제에서 상담 CTA를 붙일 확률(0~1). A/B 실험용으로 CONSULT_CTA_RATIO 환경변수(기본 1.0 = 항상)로 조절한다."""
    try:
        return min(max(float(os.getenv("CONSULT_CTA_RATIO", "1.0")), 0.0), 1.0)
    except ValueError:
        return 1.0


def _is_consult_topic(series: str = "", topic: str = "", category: str = "") -> bool:
    """주제가 구체적 고민형(재회, 이별, 썸, 연락, 짝사랑, 이직/퇴사/결혼 고민 등)인지 판별."""
    s = (series or "").upper()
    t = f"{topic or ''}"
    if s == "CONSULT":
        return True
    return any(w in t for w in _CONSULT_WORDS)


def infer_cta_kind(series: str = "", topic: str = "", category: str = "",
                   use_consult: Optional[bool] = None) -> str:
    """주제/시리즈에서 CTA 종류를 추론. (기획안 DB에 pillar 컬럼이 없어도 동작하도록 텍스트 기반)"""
    s = (series or "").upper()
    t = f"{topic or ''}"
    if s == "JAMIDOSU" or "자미두수" in t:
        return "jamidosu"
    if s == "TAROT" or "타로" in t:
        return "tarot"

    # 고민형 주제(재회, 이별, 썸, 연락, 짝사랑, 결혼 고민, 이직/퇴사 고민 등)는 카톡 1:1 상담으로 연결
    if _is_consult_topic(series, topic, category):
        if use_consult is None:
            use_consult = (random.random() < _consult_ratio())
        if use_consult:
            return "consult"

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


# kind -> [(나레이션 공유 유도, 캡션 공유 유도)]. 릴스는 공유(DM sends)와 저장이 확산 신호 1순위.
SHARE_LINES = {
    "consult": [
        ("요즘 혼자 고민 많은 친구한테 지금 바로 이 영상을 보내주세요.", "📩 요즘 혼자 고민 많은 친구한테 지금 바로 공유해보세요!"),
        ("이 고민으로 힘들어하는 친구가 떠올랐다면 바로 보내주세요.", "📩 딱 이런 고민 중인 친구한테 지금 바로 DM으로 보내주세요!"),
    ],
    "report3y": [
        ("주변에 딱 이런 친구 떠올랐다면 지금 바로 공유해보세요.", "📩 딱 이런 친구 떠오르면 지금 바로 DM으로 보내주세요!"),
        ("이거 내 얘기다 싶으면 저장해두고 그 친구한테도 보내주세요.", "📩 까먹기 전에 저장해두고 딱 맞는 친구한테 공유해보세요!"),
    ],
    "couple": [
        ("이 조합 커플이라면 상대한테 지금 바로 이 영상을 보내주세요.", "📩 이 조합인 내 연인·썸남썸녀한테 바로 보내주세요!"),
    ],
    "career": [
        ("요즘 이직이나 돈 고민 중인 친구한테 이 영상을 보내주세요.", "📩 일·이직 고민하는 친구한테 지금 바로 보내주세요!"),
    ],
    "travel": [
        ("이번에 같이 여행 갈 친구한테 이 영상을 보내주세요.", "📩 같이 여행 갈 친구 @태그하거나 공유해보세요!"),
    ],
    "mbti_saju": [
        ("이 MBTI 친구가 떠올랐다면 지금 바로 보내주세요.", "📩 이 MBTI 친구한테 지금 바로 보내주세요!"),
    ],
    "jamidosu": [
        ("내 명궁이 궁금한 친구한테 지금 바로 보내주세요.", "📩 별자리 말고 명궁이 궁금한 친구한테 보내주세요!"),
    ],
    "tarot": [
        ("지금 이 카드가 꼭 필요한 친구한테 보내주세요.", "📩 지금 이 말이 필요한 친구한테 보내주세요!"),
    ],
}


def pick_share_line(kind: str) -> Tuple[str, str]:
    """(나레이션 공유 유도, 캡션 공유 유도)"""
    return random.choice(SHARE_LINES.get(kind) or SHARE_LINES["report3y"])


def pick_reel_cta(series: str = "", topic: str = "", use_consult: Optional[bool] = None) -> Tuple[str, str]:
    """(나레이션 CTA, 캡션 CTA) = 공유 유도 한 줄 + 댓글/프로필 링크 CTA"""
    kind = infer_cta_kind(series, topic, use_consult=use_consult)
    narr, cap, _ = random.choice(CTA_PLANS[kind])
    share_narr, share_cap = pick_share_line(kind)
    return f"{share_narr} {narr}", f"{share_cap}{chr(10)}{cap}"


def pick_threads_cta(url: str, topic: str = "", category: str = "", kakao_url: Optional[str] = None) -> str:
    """Threads용 CTA. 상담 kind는 카톡 채널 주소를 쓰고, 3년 리포트 계열은 premium 주소, 나머지는 메인 주소를 쓴다."""
    series = {"MBTI": "MBTI", "운세": ""}.get(category, "")
    kind = infer_cta_kind(series, topic, category)
    _, _, tpl = random.choice(CTA_PLANS[kind])
    if kind == "consult":
        target = kakao_url or KAKAO_CHAT_URL
    elif kind in _PREMIUM_KINDS:
        target = url
    else:
        target = url.rsplit("/premium", 1)[0]
    return tpl.format(url=target)


def adapt_caption_for_youtube(caption: str, kakao_url: Optional[str] = None) -> str:
    """인스타그램용 캡션의 '프로필 링크' 및 댓글 키워드 유도를 유튜브 설명란에 맞게 실제 URL로 변환합니다."""
    if not caption:
        return caption
    k_url = kakao_url or KAKAO_CHAT_URL
    site_url = "https://mbtiju.com"
    site_premium = "https://mbtiju.com/premium"

    text = caption
    # 1. 카톡 1:1 상담 안내 변환
    if "카톡" in text or "상담" in text:
        text = re.sub(r"프로필\s*링크에서\s*카톡\s*1:1\s*상담", f"카톡 1:1 상담 링크({k_url})", text)
        text = re.sub(r"프로필\s*링크에서\s*카톡\s*일대일\s*상담", f"카톡 1:1 상담 링크({k_url})", text)
        text = re.sub(r"프로필\s*링크의\s*카톡", f"카톡 상담({k_url})", text)

    # 2. 3년 리포트 / 점수표 안내 변환
    if "3년" in text or "리포트" in text:
        text = re.sub(r"프로필\s*링크(?:의|에서)?\s*(내\s*앞으로\s*3년\s*흐름|삼\s*년\s*심층|3년\s*심층|올해\s*남은)",
                      rf"3년 심층 사주 리포트({site_premium}) \1", text)

    # 3. 그 외 남은 '프로필 링크'를 공식 사이트 주소로 대체
    text = re.sub(r"프로필\s*링크에서", f"공식 사이트({site_url})에서", text)
    text = re.sub(r"프로필\s*링크", f"공식 사이트 링크({site_url})", text)

    return text


def _share_ratio() -> float:
    """공유 CTA를 붙일 확률(0~1). A/B 실험용으로 SHARE_CTA_RATIO 환경변수(기본 1.0 = 항상)로 조절한다."""
    try:
        return min(max(float(os.getenv("SHARE_CTA_RATIO", "1.0")), 0.0), 1.0)
    except ValueError:
        return 1.0


def has_share_line(scenes: list) -> bool:
    """씬 나레이션에 공유 유도 문구(SHARE_LINES)가 들어 있는지 (A/B 변형 기록용)."""
    texts = {n for lines in SHARE_LINES.values() for n, _ in lines}
    return any((getattr(sc, "narration", "") or "") in texts for sc in scenes)


def detect_cta_kind(scenes: list, default: str = "report3y") -> str:
    """씬 나레이션에서 실제 적용된 CTA kind를 찾는다 (A/B 변형 기록용)."""
    for sc in reversed(scenes):
        body = (getattr(sc, "narration", "") or "").strip()
        for kind, plans in CTA_PLANS.items():
            for narr, _, _ in plans:
                if narr == body or narr in body or body in narr:
                    return kind
    return default


def apply_reel_cta(scenes: list, caption: str, series: str = "", topic: str = "",
                   use_share: Optional[bool] = None,
                   use_consult: Optional[bool] = None) -> Tuple[str, str]:
    """릴스 끝에 [공유/저장 유도 씬] + [댓글 키워드 & 프로필 링크 씬]을 각각 짧은 별도 씬으로 붙인다(빠른 전개 유지).
    LLM이 쓴 마지막 씬(결론/반전)은 그대로 보존한다. 마지막 씬에 이미 '프로필' 안내가 있으면 그 문장만 걷어낸다.
    use_share=None이면 SHARE_CTA_RATIO 확률로 공유 씬을 붙인다(A/B). 반환: (CTA 나레이션 전체, CTA 캡션)."""
    kind = infer_cta_kind(series, topic, use_consult=use_consult)
    link_narr, link_cap, _ = random.choice(CTA_PLANS[kind])
    share_narr, share_cap = pick_share_line(kind)
    if use_share is None:
        use_share = random.random() < _share_ratio()
    parts = ([(share_narr, 3)] if use_share else []) + [(link_narr, 4)]
    if scenes:
        last = scenes[-1]
        body = (last.narration or "").strip()
        if "프로필" in body:
            head = body[: body.find("프로필")]
            ends = [m.end() for m in re.finditer(r"[.!?]", head)]
            body = head[: ends[-1]].strip() if ends else ""
        if body:
            last.narration = body
        else:  # 결론 씬이 CTA뿐이었다면 첫 CTA 문장이 그 씬을 대신한다
            last.narration, last.duration_estimate = parts[0]
            parts = parts[1:]
        nid = last.scene_id
        cta_visuals = [
            "Vertical 9:16 portrait candid shot of two young Korean women in their late 20s at a trendy Seoul cafe looking at a smartphone together with an amazed and relatable expression, natural daylight, no text, no watermark",
            "Vertical 9:16 portrait candid close-up of a young Korean woman in her late 20s holding a smartphone by a warm window with a subtle curious smile, different framing, shallow depth of field, natural lighting, no text, no watermark",
        ]
        for idx_p, (text, dur) in enumerate(parts):
            nid += 1
            vp = cta_visuals[idx_p % len(cta_visuals)]
            scenes.append(last.model_copy(update={
                "scene_id": nid, "narration": text, "duration_estimate": dur,
                "visual_prompt": vp, "media_type": "image",
            }))
    narr = f"{share_narr} {link_narr}" if use_share else link_narr
    cap = f"{share_cap}{chr(10)}{link_cap}" if use_share else link_cap
    return narr, cap
