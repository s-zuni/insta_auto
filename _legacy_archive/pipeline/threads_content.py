"""
Threads 전용 타래(본문 + 답글) 생성. 릴스/캐러셀 주제와 무관한 독립 콘텐츠.

레퍼런스 인기글(사주/MBTI/운세 계정 8건) 분석에서 뽑은 구조·후킹·CTA 패턴을 STYLE_GUIDE에 담아
Gemini에 추상화된 '패턴'으로만 전달합니다 (원문 문장/주제를 그대로 따라하지 않도록 금지).

비중: 사주 60% / MBTI 20% / 기타 운세(타로·자미두수·신점·띠) 20%
CTA: 하루 3개 중 1개의 글에만, 타래 맨 끝 짧은 답글로 mbtiju.com/premium 안내.
"""
import datetime
import json
import os
import random
import re
import sys
from typing import List, Optional

from pydantic import BaseModel, Field

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from pipeline.script_gen import generate_json, get_llm_model
from pipeline.mbti_saju_content import MBTI_KEYWORDS

MAX_LEN = 480  # API 한도 500자에 여유
MIN_POSTS, MAX_POSTS = 1, 4  # 단독 글 1개가 기본, 필요할 때만 답글 1~3
CTA_URL = "https://mbtiju.com/premium"
DEFAULT_THREADS_MODEL = "gemini-3.1-pro-preview"

# ─────────────────────────────────────────────────────────────
# 카테고리 비중 & 세부 포맷
# ─────────────────────────────────────────────────────────────
CATEGORY_WEIGHTS = {"사주": 60, "MBTI": 20, "운세": 20}

CATEGORY_FORMATS = {
    "사주": [
        "사찰급 인간 해부 단독 글: '겉으론 다 맞춰주는데 속으론 이미 손절 끝낸 사람 특징'처럼 누구나 찔리는 행동 3~4가지를 팩폭하고, 사실 이게 특정 일간(예: 을목·신금·임수 등, 태어난 계절/성향 단서 함께 제시)의 무서운 본성임을 폭로 + 마지막에 '본인 몇 개 해당됨?' 질문 (답글 없이 완결)",
        "현실 고민 처방 단독 글: '재회 연락 기다리는 사람', '이직/퇴사 타이밍 고민', '썸 타는데 연락 뜸해진 속마음' 등 구체적 고민 상황 1개 집중 → 사주 흐름과 기질 관점에서 지금 절대 하면 안 되는 행동 2가지 + 양자택일 질문 (답글 없이 완결)",
        "역발상 통념 파괴 단독 글: '착해서 호구 잡히는 게 아니라 사실 남한테 관심이 없는 사주임', '연락 잘 안 한다고 마음 식은 게 아닌 유형'처럼 흔한 오해를 한 줄로 뒤집고 일상 증거 3가지 + 사주 원인 해부 (답글 없이 완결)",
        "남녀 극단 케미/악연 단독 글: '만나면 서로 피 말리는데 죽어도 못 헤어지는 남녀 조합' 또는 '처음엔 설레는데 사귀면 기 빨리는 조합' → 싸우는 구체적 장면과 풀리는 법 + '주변에 꼭 이런 커플 있지 않음?' 질문 (답글 없이 완결)",
        "신살(도화살·홍염살·역마살·화개살·백호살·귀문관살) 무의식 행동 폭로: 첫 줄은 신살 이름 대신 '가만히 있어도 이상하게 사람 꼬이는 애들 특징'이나 '촉이 너무 좋아서 피곤한 사람 특징'으로 훅을 던지고, 중반에 신살 원리와 현실 처방 공개 (답글 없이 완결)",
        "태어난 계절(봄·여름·가을·겨울생) × 사주 기질 팩폭: 누구나 아는 태어난 달(계절)로 대상을 좁혀 연애할 때/돈 쓸 때/화났을 때 나오는 소름 돋는 공통점 3가지 해부 + '너 몇 월생임?' 질문 (답글 없이 완결)",
        "돈복/커리어 팩폭 단독 글: '평생 통장에 돈 안 마르는 인간들 사주 공통점' 또는 '회사 다니면 병나고 내 일 해야 대박 나는 팔자 특징' → 일상 습관 3가지와 오행/십성 근거 + 반박/인정 유도 질문 (답글 없이 완결)",
        "대운 전환기 징조 단독 글: '인생 크게 풀리기 직전인 사람한테 무조건 나타나는 이상한 징조 3가지'(갑자기 인간관계 정리됨, 잠이 쏟아짐, 이유 없이 이사/이직 충동 등) → 사주 흐름 풀이 (답글 없이 완결)",
        "이번 달 월운·절기 급소 경고: '이번 달 유독 멘탈 갈리고 사람한테 지치는 애들 봐라' → 지금 시기 기운 때문임을 짚어주고 당장 끊어야 할 것 1가지 + 해야 할 행동 1가지 처방 (답글 없이 완결)",
    ],
    "MBTI": [
        "[연생/띠 × MBTI 핀셋 저격] '<95~03년생 중 택1> + <MBTI>가 연애할 때 제일 무서운 순간' 또는 '인간관계 현타 오는 이유' → 겉으로 보이는 MBTI 행동 2가지 + 속에 숨겨진 사주/띠 기운 반전 2가지 + 질문 (답글 없이 완결)",
        "연애/관계 고민 단독 글: '이별 후 연락할까 말까 밤마다 고민하는 <MBTI>', '짝사랑 포기 직전인 <MBTI>가 지금 착각하고 있는 것' 등 현실 고민 1개 집중 → 속마음 해부와 뼈 때리는 조언 + 질문 (답글 없이 완결)",
        "[겉과 속 반전 해부] '사람들이 <MBTI>에 대해 제일 크게 착각하는 거' → 흔한 편견을 부수고 사주 기운(오행/일간)에 따라 완전히 갈리는 두 가지 본성 비교 + '너는 전자임 후자임?' 질문 (답글 없이 완결)",
        "[시의성 랭킹 팩폭] '올해 남은 기간 대운 제대로 터지는 MBTI × 태어난 계절 조합 TOP 3' → 3위부터 1위까지 이유와 조심할 점까지 압축 공개 (답글 없이 완결)",
        "MBTI 남녀 극단 궁합: '남자 <유형> × 여자 <유형>이 만나면 맨날 똑같은 이유로 싸우는 이유' → 카톡/대화 속 숨 막히는 리얼 장면 묘사 + 해결책 한 줄 + 질문 (답글 없이 완결)",
        "상황별 극단 반응 비교: '정 떨어졌을 때', '썸남썸녀가 읽씹했을 때', '퇴사 마려울 때' 중 한 상황 고정 → 유형별 소름 돋는 속마음과 행동 한 줄씩 날카롭게 비교",
        "같은 MBTI인데 사주 달랐을 때 차이: '같은 INFP인데 누구는 멘탈 강철이고 누구는 유리멘탈인 진짜 이유'처럼 MBTI만으로 설명 안 되는 부분을 사주 기질로 명쾌하게 해부 (답글 없이 완결)",
    ],
    "운세": [
        "고민별 직감/타로 선택형: 재회·연락·이직 고민 중 하나를 던지고 '지금 딱 눈에 들어오는 번호 하나 골라라 (1번 / 2번 / 3번)' → 답글에 번호별 소름 돋는 현 상태와 조언 공개",
        "촉·징조 팩폭 체크리스트: '요즘 유독 이 3가지 증상 나타나면 운의 흐름 바뀌는 중임' → 꿈·인간관계·컨디션 징조 해부와 행동 지침 (답글 없이 완결)",
        "자미두수 인간 유형 해부: 어려운 용어는 뒤에 숨기고 '평생 내 편 들어줄 귀인이 끊이지 않는 사람 특징' 또는 '연애만 하면 이상한 사람 꼬이는 명궁 특징'을 일상 장면으로 풀이 (답글 없이 완결)",
        "태어난 연도 끝자리/띠별 현실 팩폭: 이번 달 유독 돈이 새거나 사람이 꼬이는 띠/연생 3~4개를 콕 집어 원인과 피해야 할 행동 처방",
    ],
}

SLOT_HINTS = {
    "morning": "아침 7시반 글: 출근·등교 지하철에서 스크롤 멈추게 만드는 짧고 매운 '인간관계 손절 기준 / 돈·직장 팩폭 / 오늘 조심할 인간 유형'. 첫 줄부터 정신 번쩍 들게 작성.",
    "afternoon": "오후 2시 글: 점심 먹고 나른할 때 댓글 논쟁 터지는 '연애 속마음 해부 / 겉과 속 다른 유형 폭로 / 사찰급 특징 체크리스트'. 본문 읽고 자기 얘기라 댓글 안 달고는 못 배기게 작성.",
    "evening": "저녁 6시 글: 퇴근길~밤 감성 터지는 시간대. '재회·이별 미련·썸 연락 고민·회피형 심리·퇴사/이직 타이밍·인생 전환기 신호'처럼 지금 당장 내 고민 같아서 저장하고 공유하게 만드는 깊고 날카로운 글.",
}

# 레퍼런스 및 쓰레드 알고리즘(체류시간·더보기 클릭·댓글 논쟁·인용/리포스트) 최적화 작법
STYLE_GUIDE = """[Threads 10배 조회수 폭발 작법 - 반말·노이모지·도파민 극대화]
■ 1. 말투 & 표기 절대 규칙 (어기면 즉시 노출 하락)
- ★100% 반말(음슴체 + 구어체 반말)만 사용한다.★ (~함, ~임, ~거든, ~잖아, ~다, ~야, ~지, ~더라 자연스럽게 혼용).
- 존댓말(~해요, ~어요, ~입니다, ~습니다, ~세요, ~까요, ~죠)은 단 한 문장도 절대 쓰지 마라.
- ★이모티콘/이모지 완전 금지(0개).★ 불꽃, 반짝이, 화살표, 눈물 등 모든 그림 이모지를 본문과 답글에서 완전히 빼라. 쓰레드에서 이모지 들어가면 AI 봇·광고글로 보여서 0.1초 만에 스킵당한다.
- 마크다운 별표(**), 해시태그(#), 한자 병기(甲木 등) 절대 금지. 오직 순수 한글 텍스트와 줄바꿈의 리듬감으로만 승부한다.
- AI 특유의 상투적 표현("알아보겠습니다", "살펴볼까요", "~해보세요", "도움이 되기를", 과한 하이픈 '-') 절대 금지. 사주와 인간 심리를 꿰뚫어 보는 날카롭고 시니컬하지만 속정 있는 친구가 새벽에 팩폭 날리는 톤으로 써라.

■ 2. 구조 (체류시간 & '더보기' 클릭 극대화)
- 기본은 '단독 글 1개 완결'(필요할 때만 반전/해석 답글 1개). 억지로 목록을 쪼개 답글을 늘리지 않는다.
- 분량은 7~12줄, 공백 포함 220~340자 내외.
- ★첫 줄이 조회수의 90%를 결정한다★:
  - 첫 줄은 반드시 공백 포함 15~28자 이내의 강렬한 한 문장으로 쓰고, 바로 빈 줄(엔터 2번)을 넣어 시각적으로 분리해라.
  - 첫 줄에 사주를 모르는 95%의 일반인이 못 알아듣는 어려운 한자어(재백궁, 상관견관 등)만 덩그러니 쓰지 마라.
  - 첫 줄은 누구나 읽자마자 "어? 이거 내 얘긴데?" 또는 "헐 내 전 애인인데?" 하고 손가락이 멈추는 [구체적 행동 팩폭 / 통념 반박 / 태어난 계절·연생·MBTI 저격 / 현실 고민 급소]로 시작해라.

■ 3. 본문 첫 줄 후킹 공식 6선 (매번 가장 도파민 터지는 방식을 고를 것)
1. [사찰급 팩폭 호명]: "겉으론 다 맞춰주는데 속으론 이미 손절 끝낸 사람 특징", "연락 귀찮아하면서 좋아하는 사람 앞에선 호구 되는 인간"
2. [통념 박살/역발상]: "착해서 당하는 게 아니라 사실 남한테 관심이 없는 거임", "연애할 때 다정한 사람 만나면 오히려 빨리 지치는 유형"
3. [연생·계절·MBTI 핀셋 저격]: "겨울에 태어난 INFP가 연애할 때 제일 무서운 순간", "96~02년생 중에 유독 인복 없고 사람한테 데이는 애들 공통점"
4. [현실 고민 급소 타격]: "헤어지고 연락 올까 말까 기다리는 사람, 딱 이것만 봐라", "이직할까 퇴사할까 고민 중인 사람이 이번 달 조심할 것"
5. [운세/대운 징조]: "인생 대운 바뀌기 직전인 사람한테 무조건 나타나는 이상한 증상 3가지"
6. [극단 비교 논쟁]: "잠수이별하는 인간 vs 환승이별하는 인간, 사주로 보면 누가 더 최악이냐면"

■ 4. 본문 전개 (사찰 디테일 → 사주/MBTI 원인 해부 → 현실 처방)
- 추상적인 성격 묘사("감수성이 풍부함", "배려심이 깊음") 금지. 무조건 눈에 그려지는 일상 장면으로 폭로해라.
  (예: "카톡 알림 떠도 미리보기로만 읽고 3시간 뒤에 답장함", "싸울 때 화 안 내고 갑자기 말수 줄어들면 이미 마음 정리 끝난 거임", "돈 모일 만하면 꼭 가족이나 주변 일로 목돈 나감")
- 번호 리스트(1, 2, 3)를 쓸 때는 항목마다 빈 줄로 구분하고, 한 줄은 25자 안팎으로 짧게 끊어 모바일 가독성을 극대화해라.
- 중반부에 "이게 왜 그러냐면 사주에 ~기운(또는 ~일간/신살/MBTI 구조)이 있어서 그럼"으로 명리학적 근거를 쉬운 일상어로 찰지게 풀어줘라. 이때 태어난 계절(봄·여름·가을·겨울생)이나 겉성향 단서를 같이 줘서 사주를 모르는 사람도 자기에게 대입할 수 있게 만들어라.
- 단정적 공포 조장이나 의학·법률·투자 단정은 금지하되, 인간관계와 심리 묘사는 소름 돋을 만큼 직설적으로 써라.

■ 5. 마지막 줄 (댓글 & 인용 폭발 유도)
- "댓글로 물어봐/봐줄게/풀이해줄게"처럼 개인 답변을 약속하는 문구는 절대 금지.
- 대신 독자가 자존심이 건드려져서 반박하거나, "나 왜 사찰당함?" 하고 자수하거나, 친구를 소환할 수밖에 없는 날카로운 반말 질문 한 줄로 끝내라.
  (예: "솔직히 여기서 3개 이상 맞으면 인정해라", "너네는 1번임 2번임?", "본인 태어난 달이랑 MBTI 뭐임? 유독 심한 조합 있음", "주변에 꼭 이런 인간 하나씩 있지 않냐")

■ 6. 절대 금지
- 홍보·서비스 언급·외부 링크 본문 삽입 금지 (CTA는 시스템이 별도 답글로 붙임).
- 특정 타 계정/실존 인물 언급 금지."""


class ThreadsThread(BaseModel):
    topic_tag: str = Field("", description="토픽 태그 1개 (# 없이, 마침표/&/@ 없이, 예: 사주, MBTI, 타로)")
    posts: List[str] = Field(
        ...,
        description=f"타래. 첫 요소=본문(강렬한 반말 후킹+핵심 팩폭), 이후=답글(선택). 총 {MIN_POSTS}~{MAX_POSTS}개, 각 {MAX_LEN}자 이내. 100% 반말 필수, 이모지/이모티콘/해시태그/링크/서비스 홍보 절대 금지",
    )


class GeneratedThread(BaseModel):
    category: str
    topic_tag: str
    posts: List[str]  # CTA 답글 포함 최종 게시 목록
    has_cta: bool = False


# ─────────────────────────────────────────────────────────────
# CTA (고정 문구 - 반말 & 이모지 0개, 서비스 주장 내용을 모델이 지어내지 않도록 템플릿으로만 사용)
# ─────────────────────────────────────────────────────────────
CTA_VARIANTS = [
    "내 생년월일이랑 MBTI 조합의 앞으로 3년 운세와 맞춤 솔루션\n프로필 링크(mbtiju.com)에서 무료 점수표부터 확인해봐\n{url}",
    "내 사주를 MBTI랑 같이 제대로 분석받고 싶다면\n올해 남은 기간부터 3년 치 점수표는 무료로 먼저 볼 수 있음\n{url}",
    "사주만 봐도, MBTI만 봐도 반쪽임\n두 가지를 겹쳐서 보는 3년 심층 사주 리포트\n{url}",
    "내 팔자랑 성향을 같이 봐야 진짜 조언이 나옴\n올해 남은 기간 + 앞으로 3년 흐름\n{url}",
    "혼자 끙끙 앓던 고민 하나, 사주랑 MBTI로 바로 풀어봐\n카톡 1:1 상담 (한 가지 고민 9,900원부터)\nAI 분석을 바탕으로 운세 서비스 전문가가 직접 검수해 평일 기준 24시간 이내 답변해줌\n{url}",
    "지금 제일 답답한 그 고민 하나만 짚어서 물어봐\n카톡 채널 1:1 사주·MBTI 상담 (9,900원부터)\nAI 분석을 바탕으로 운세 서비스 전문가가 직접 검수해 평일 기준 24시간 이내 전달\n{url}",
]


def build_cta(topic: str = "", category: str = "") -> str:
    """주제별 CTA(카톡 상담/3년 사주 리포트/MBTI x 사주/자미두수/타로)를 우선 사용, 실패 시 기본 문구."""
    try:
        from pipeline.cta import pick_threads_cta
        return _strip_emojis(pick_threads_cta(CTA_URL, topic, category))
    except Exception:
        from pipeline.cta import infer_cta_kind, KAKAO_CHAT_URL
        kind = infer_cta_kind("", topic, category)
        target = KAKAO_CHAT_URL if kind == "consult" else CTA_URL
        return _strip_emojis(random.choice(CTA_VARIANTS).format(url=target))


# ─────────────────────────────────────────────────────────────
# 시의성: 오늘 날짜의 연주/월주 (절기 경계는 근사치. 경계일 ±1일은 모델에 쓰지 말라고 안내)
# ─────────────────────────────────────────────────────────────
_STEMS = "갑을병정무기경신임계"
_BRANCHES = "자축인묘진사오미신유술해"
# (월, 일, 월지 인덱스) - 절기 시작일
_SOLAR_TERMS = [
    (1, 6, 1), (2, 4, 2), (3, 6, 3), (4, 5, 4), (5, 6, 5), (6, 6, 6),
    (7, 7, 7), (8, 7, 8), (9, 8, 9), (10, 8, 10), (11, 7, 11), (12, 7, 0),
]


def saju_calendar_context(today: Optional[datetime.date] = None) -> str:
    today = today or datetime.date.today()
    y = today.year
    if (today.month, today.day) < (2, 4):  # 입춘 전은 전년도 간지
        y -= 1
    year_stem, year_branch = (y - 4) % 10, (y - 4) % 12

    term = None
    for m, d, branch in _SOLAR_TERMS:
        if (today.month, today.day) >= (m, d):
            term = (m, d, branch)
    if term is None:  # 1/6 이전 = 전년 12월 대설 이후(자월)
        term = (12, 7, 0)
    m, d, branch = term
    n = (branch - 2) % 12  # 인월=0
    first_stem = (year_stem * 2 + 2) % 10  # 인월 천간
    month_stem = (first_stem + n) % 10
    near_boundary = abs((today - datetime.date(today.year, m, d)).days) <= 1 if (m, d) != (12, 7) else False
    note = " (절기 경계 근처라 월주는 언급하지 말 것)" if near_boundary else ""
    return (
        f"오늘 {today.isoformat()} / 연주 {_STEMS[year_stem]}{_BRANCHES[year_branch]}년 / "
        f"월주 {_STEMS[month_stem]}{_BRANCHES[branch]}월(절기 {m}/{d}부터){note}"
    )


# ─────────────────────────────────────────────────────────────
# 생성 & 후처리 (이모지 완전 제거 + 반말 강제 + 줄바꿈 가드)
# ─────────────────────────────────────────────────────────────
_EMOJI_RE = re.compile(
    "["
    "\U0001F1E0-\U0001F1FF"
    "\U0001F300-\U0001F5FF"
    "\U0001F600-\U0001F64F"
    "\U0001F680-\U0001F6FF"
    "\U0001F700-\U0001F77F"
    "\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "\u2600-\u26FF"
    "\u2700-\u27BF"
    "\u2300-\u23FF"
    "\u2B50\u2B55\u2934\u2935\u25AA\u25AB\u25FE\u25FD\u25FB\u25FC"
    "\uFE0F\u200D"
    "]+",
    flags=re.UNICODE,
)

_POLITE_LINE_RE = re.compile(
    r"(?:입니다|습니다|ㅂ니다|해요|어요|아요|여요|네요|군요|세요|까요|시죠|인가요|할까요|거든요|잖아요|더라고요|답니다|랍니다)[.?!~]*\s*$",
    re.MULTILINE,
)

_POLITE_REPLACEMENTS = [
    (r"거든요([.?!~]*)(?=\s|$)", r"거든\1"),
    (r"잖아요([.?!~]*)(?=\s|$)", r"잖아\1"),
    (r"더라고요([.?!~]*)(?=\s|$)", r"더라고\1"),
    (r"랍니다([.?!~]*)(?=\s|$)", r"다\1"),
    (r"답니다([.?!~]*)(?=\s|$)", r"다\1"),
    (r"입니다([.?!~]*)(?=\s|$)", r"임\1"),
    (r"습니다([.?!~]*)(?=\s|$)", r"음\1"),
    (r"해보세요([.?!~]*)(?=\s|$)", r"해봐\1"),
    (r"보세요([.?!~]*)(?=\s|$)", r"봐라\1"),
    (r"하세요([.?!~]*)(?=\s|$)", r"해라\1"),
    (r"인가요([.?!~]*)(?=\s|$)", r"임?\1"),
    (r"할까요([.?!~]*)(?=\s|$)", r"할까\1"),
    (r"까요([.?!~]*)(?=\s|$)", r"까\1"),
    (r"시죠([.?!~]*)(?=\s|$)", r"지\1"),
    (r"해요([.?!~]*)(?=\s|$)", r"함\1"),
    (r"네요([.?!~]*)(?=\s|$)", r"네\1"),
    (r"군요([.?!~]*)(?=\s|$)", r"군\1"),
    (r"([가-힣])어요([.?!~]*)(?=\s|$)", r"\1어\2"),
    (r"([가-힣])아요([.?!~]*)(?=\s|$)", r"\1아\2"),
    (r"([가-힣])여요([.?!~]*)(?=\s|$)", r"\1여\2"),
]


def _strip_emojis(text: str) -> str:
    """텍스트에서 모든 이모지/이모티콘 및 불필요한 마크다운 강조 기호를 제거합니다."""
    if not text:
        return ""
    cleaned = _EMOJI_RE.sub("", text)
    cleaned = cleaned.replace("**", "")
    # 줄 시작/끝의 불필요한 공백 정리 (줄바꿈 자체는 유지)
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in cleaned.splitlines()]
    res = "\n".join(lines)
    return re.sub(r"\n{3,}", "\n\n", res).strip()


def _convert_polite_to_banmal(text: str) -> str:
    """혹시라도 남아 있는 존댓말 어미를 자연스러운 반말로 치환합니다."""
    if not text:
        return ""
    out = text
    for pat, repl in _POLITE_REPLACEMENTS:
        out = re.sub(pat, repl, out)
    return out


def _has_polite_ending(posts: list) -> bool:
    """생성된 글에 존댓말 어미가 섞여 있는지 검사합니다."""
    return any(bool(_POLITE_LINE_RE.search(p or "")) for p in posts)


def _clean_post(text: str) -> str:
    """이모지 제거 + 반말 보정 + 길이 제한을 한 번에 수행합니다."""
    return _trim(_convert_polite_to_banmal(_strip_emojis(text)))


def _sanitize_tag(tag: str) -> str:
    return re.sub(r"[#.&@\s]", "", _strip_emojis(tag or "")).strip()[:50]


def _trim(text: str) -> str:
    text = text.strip()
    if len(text) <= MAX_LEN:
        return text
    cut = text[:MAX_LEN]
    for sep in ("\n", ". ", "? ", "! ", "다 ", "임 ", "함 ", "음 "):
        idx = cut.rfind(sep)
        if idx > MAX_LEN * 0.6:
            return cut[: idx + len(sep)].strip()
    return cut.strip()


def _is_well_formatted(posts: list) -> bool:
    """긴 글(80자 초과)의 대부분이 줄바꿈을 포함하는지 검사 (줄글 덩어리 방지)."""
    long_posts = [p for p in posts if len(p) > 80]
    if not long_posts:
        return True
    return sum(("\n" in p.strip()) for p in long_posts) / len(long_posts) >= 0.8


def pick_category() -> str:
    cats, weights = zip(*CATEGORY_WEIGHTS.items())
    return random.choices(cats, weights=weights, k=1)[0]


def generate_threads_thread(
    category: Optional[str] = None,
    slot: Optional[str] = None,
    with_cta: bool = False,
    recent_posts: Optional[list] = None,
    model_name: Optional[str] = None,
    today: Optional[datetime.date] = None,
) -> GeneratedThread:
    """category: '사주'|'MBTI'|'운세' (None이면 60/20/20 가중 무작위). slot: morning|afternoon|evening."""
    category = category if category in CATEGORY_WEIGHTS else pick_category()
    fmt = random.choice(CATEGORY_FORMATS[category])
    # THREADS_OPENAI_MODEL로 스레드 전용 모델을 지정할 수 있고, 실패하면 기본 모델로 대체
    models = [m for m in dict.fromkeys([
        model_name or os.getenv("THREADS_OPENAI_MODEL") or get_llm_model(),
        get_llm_model(),
    ]) if m]
    model_idx = 0

    system_prompt = f"{STYLE_GUIDE}\n\n[오늘 날짜/절기]\n{saju_calendar_context(today)}"
    if slot in SLOT_HINTS:
        system_prompt += f"\n\n[시간대]\n{SLOT_HINTS[slot]}"

    user_prompt = (
        f"Threads 타래를 JSON으로 작성해라.\n"
        f"카테고리: {category}\n포맷 힌트: {fmt}\n"
        f"작성 전 내부적으로 가장 스크롤을 멈추게 할 매운맛 반말 첫 줄 훅 3개를 생각한 뒤, 그중 제일 도파민 터지는 1개로 시작해라.\n"
        f"필수 조건: 100% 반말(~함, ~임, ~거든, ~다, ~잖아), 이모티콘/이모지 단 1개도 사용 금지, 첫 줄 작성 후 빈 줄 필수."
    )
    if category == "MBTI":
        user_prompt += f"\n(참고 유형 풀: {', '.join(MBTI_KEYWORDS.keys())})"
    if recent_posts:
        joined = "\n---\n".join(p[:100] for p in recent_posts[:10])
        user_prompt += f"\n\n[최근 올린 글 - 주제/첫 줄 훅/소재 절대 겹치지 않게]\n{joined}"

    thread: Optional[ThreadsThread] = None
    for attempt in range(3):
        try:
            cand = generate_json(system_prompt, user_prompt, ThreadsThread,
                                 temperature=0.95, model_name=models[model_idx])
        except Exception as e:
            print(f"[WARNING] Threads 타래 생성 실패 (모델 {models[model_idx]}, 시도 {attempt + 1}/3): {e}")
            model_idx = min(model_idx + 1, len(models) - 1)
            continue
        thread = cand
        well_formatted = _is_well_formatted(cand.posts)
        polite_detected = _has_polite_ending(cand.posts)
        if well_formatted and not polite_detected:
            break
        reason = "존댓말 감지" if polite_detected else "줄바꿈 부족"
        print(f"[WARNING] {reason} 결과 (시도 {attempt + 1}/3), 재생성합니다.")

    if thread is None or len(thread.posts) < MIN_POSTS:
        raise RuntimeError("Threads 타래 생성 실패: 유효한 결과가 없습니다.")

    posts = [_clean_post(p) for p in thread.posts if p and p.strip()]
    posts = [p for p in posts if p][:MAX_POSTS]
    if len(posts) < MIN_POSTS:
        raise RuntimeError("Threads 타래 생성 실패: 답글이 비어 있습니다.")
    tag = _sanitize_tag(thread.topic_tag) or category

    if with_cta:
        posts.append(build_cta(posts[0], category))
    return GeneratedThread(category=category, topic_tag=tag, posts=posts, has_cta=with_cta)


if __name__ == "__main__":
    # 미리보기: python -m pipeline.threads_content [사주|MBTI|운세] [cta]
    cat = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in CATEGORY_WEIGHTS else None
    t = generate_threads_thread(category=cat, with_cta="cta" in sys.argv)
    print(f"[{t.category}] 태그: {t.topic_tag} | CTA: {t.has_cta}")
    for i, p in enumerate(t.posts):
        print(f"\n--- {'본문' if i == 0 else f'답글 {i}'} ({len(p)}자) ---\n{p}")
