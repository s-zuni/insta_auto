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
MIN_POSTS, MAX_POSTS = 2, 5  # 본문 1 + 답글 1~4
CTA_URL = "https://mbtiju.com/premium"
DEFAULT_THREADS_MODEL = "gemini-3.1-pro-preview"

# ─────────────────────────────────────────────────────────────
# 카테고리 비중 & 세부 포맷
# ─────────────────────────────────────────────────────────────
CATEGORY_WEIGHTS = {"사주": 60, "MBTI": 20, "운세": 20}

CATEGORY_FORMATS = {
    "사주": [
        "일간(갑목~계수) 조합 케미: 누가 누구에게 끌리는지/상극·상생 관계를 10개 안팎 리스트 → 번호별 한 줄 상황 해설",
        "신살(도화살·현침살·귀문관살·백호대살·역마살·화개살 등) 중 1~3개를 골라 '이 살이 있는 사람의 일상 행동' 해설",
        "십성(비겁·식상·재성·관성·인성) 중 하나가 많거나 없는 사람의 증상 체크리스트 → 원인 → 대처",
        "오행 개운법: 부족/과다한 오행별로 오늘부터 할 수 있는 구체적 행동·소비·방향·시간대 처방",
        "직장/인간관계/재물 상황에서 '이런 사주는 이게 맞다/이러면 안 된다' 선언형 리스트",
        "이번 달 월운·절기 시의성을 활용한 '이번 달 이런 사주는 이것 조심/이것 하세요'",
    ],
    "MBTI": [
        "반전 포맷: '~인 줄 알았는데 친해지면 ~' 16유형 중 8개 이상 (본문 8 + 답글 8로 분할 가능)",
        "상황별 16유형 반응: 연애/썸/이별/회식/카톡 등 한 상황 고정, 유형별 한 줄 행동",
        "MBTI × 사주 교차: 같은 MBTI라도 일간/오행이 다르면 달라지는 점 (사주 서비스 정체성 강조)",
    ],
    "운세": [
        "타로: 오늘의 카드 3장 중 하나 고르기(선택형) → 답글에 카드별 해석",
        "자미두수: 명궁/궁위(재백궁·관록궁·부처궁) 중 하나를 쉬운 말로 풀어 '이런 사람은 이렇다'",
        "신점/직감 계열: 촉·꿈·징조 체크리스트 → 해석",
        "띠별 운세: 12띠 중 이번 주 포인트 한 줄씩 (본문 6 + 답글 6)",
    ],
}

SLOT_HINTS = {
    "morning": "아침 7시반 글: 출근/등교 전 가볍게 읽히는 '오늘 하루 행동 지침·개운' 톤. 짧고 실용적.",
    "afternoon": "오후 2시 글: 직장/인간관계/돈 같은 현실 고민 공감 톤. 점심 후 잠깐 보는 정보형.",
    "evening": "저녁 6시 글: 퇴근 후 감성/연애/나 자신 탐구 톤. 공유·태그하고 싶어지는 내용.",
}

# 레퍼런스에서 추출한 구조·후킹 규칙 (원문이 아닌 추상 패턴)
STYLE_GUIDE = f"""[Threads 타래 작법 - 인기글 분석 결과]
■ 구조 (타래)
- 본문(1번째 글): 제목 + 결론 또는 리스트 '티저'. 전부 알려주지 말고 궁금하게 끊는다 ("자세한 건 댓글", "어떤 사주냐면,").
- 답글(2~4개): 번호별 상세 해설. 한 답글에 하나의 묶음만. 각 글 {MAX_LEN}자 이내.
- 마지막 답글: 현실 조언 한 줄 또는 단서(※ 예외 케이스, 재미로 보는 해석) 또는 댓글을 부르는 질문 ("너는 어떤 유형이야?").
■ 후킹 (본문 첫 1~2줄) - 매번 아래 중 다른 방식을 고른다
1. 대상 지정 제목: <~한 사주>, <~하면 안 되는 사람>, <~할 수밖에 없는 사주>
2. 반직관 단언: 흔한 믿음을 한 문장으로 뒤집기 (예: '비싼 걸 안 해도 된다')
3. 공감 체크리스트: 일상 상황 3~5개 나열 → "어떤 사주냐면," 으로 원인 공개
4. 반전 포맷: "~인 줄 알았는데 ~"
5. 이어읽기 지시: 읽는 사람 증상을 짚고 "끝까지 보세요"
■ 내용 규칙
- 추상어 대신 일상의 구체 장면(회의, 카톡, 남편/친구 변명, 월급날 등)으로 설명한다.
- 리스트는 번호를 매기고 항목당 1~2문장. 오행/신살/십성 용어는 정확하게 쓰되 바로 뒤에 쉬운 말로 풀어쓴다.
- 처방은 오늘 바로 할 수 있는 행동 수준으로 구체화한다 (방향, 시간대, 소비 품목, 습관).
- 예외 케이스를 한 번은 짚는다 ("단, ~한 사주는 오히려 반대"). 단정적 공포 조장·의학/투자 단정은 금지.
- 시의성: 아래 [오늘 날짜/절기]를 참고해 '이번 달' 한 번 언급 가능. 확실하지 않은 간지/절기는 쓰지 않는다.
- ★줄바꿈 필수★ 모바일 가독성을 위해 한 줄은 25자 안팎, 문장이 끝나면 줄을 바꾼다. 리스트 항목은 항목마다 줄을 바꾸고,
  항목 사이/문단 사이는 빈 줄 한 줄로 구분한다. 줄글 덩어리(3문장 이상을 한 줄로 이어 쓰기)는 절대 금지.
  예) 번호 리스트는 제목 줄 + ': 설명' 줄 두 줄 구조 (제목 줄 "1. 갑목 ← 신금", 다음 줄 ": 신금은 갑목만 보면 자꾸 챙김").
- "끝까지 보세요"는 5가지 후킹 중 하나일 뿐이다. 그 표현에 의존하지 말고 후킹을 다양하게 쓴다.
- 댓글 유도는 투표/선택형 질문("너는 A야 B야?")만 쓴다. "댓글로 물어봐 주세요/알려드릴게요"처럼 답변을 약속하는 문구는 금지.
- 어투: 친구에게 말하듯 구어체(~해요/~임/~거든요 혼용). AI 말투(과한 대시, 상투적 맺음, "~해보세요!" 남발) 금지.
- 이모지는 전체에서 최대 2개. 본문에 해시태그(#) 금지. 한자는 쓰지 않고 한글로만 쓴다.
■ 금지
- 레퍼런스의 주제·문장·항목을 그대로 옮기기 금지. 구조/후킹만 차용하고 소재와 항목은 새로 만든다.
- 홍보·서비스 언급·링크 금지 (CTA는 시스템이 따로 붙인다).
- 특정 계정/인물 언급 금지."""


class ThreadsThread(BaseModel):
    topic_tag: str = Field("", description="토픽 태그 1개 (# 없이, 마침표/&/@ 없이, 예: 사주, MBTI, 타로)")
    posts: List[str] = Field(
        ...,
        description=f"타래. 첫 요소=본문(티저), 이후=답글. 총 {MIN_POSTS}~{MAX_POSTS}개, 각 {MAX_LEN}자 이내. 해시태그/링크/서비스 홍보 금지",
    )


class GeneratedThread(BaseModel):
    category: str
    topic_tag: str
    posts: List[str]  # CTA 답글 포함 최종 게시 목록
    has_cta: bool = False


# ─────────────────────────────────────────────────────────────
# CTA (고정 문구 - 서비스 주장 내용을 모델이 지어내지 않도록 템플릿으로만 사용)
# ─────────────────────────────────────────────────────────────
CTA_VARIANTS = [
    "내 사주를 MBTI와 함께 제대로 분석받고 싶다면\n1,000만 건의 데이터로 도출하고, 사람이 하나하나 검토한 결과를 드려요\n👉 {url}",
    "사주만 봐도, MBTI만 봐도 반쪽이에요\n두 가지를 겹쳐서 나만의 조언과 전략을 뽑아드려요 (1,000만 건 데이터 분석 + 사람이 직접 검토)\n👉 {url}",
    "내 사주 × MBTI 맞춤 분석은 여기서 받아볼 수 있어요\n데이터 분석 후 사람이 하나하나 검토해서 정리해드려요\n👉 {url}",
    "내 팔자와 성향을 같이 봐야 진짜 조언이 나와요\n1,000만 건 데이터 기반 분석, 최종은 사람이 검토합니다\n👉 {url}",
]


def build_cta() -> str:
    return random.choice(CTA_VARIANTS).format(url=CTA_URL)


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
# 생성
# ─────────────────────────────────────────────────────────────
def _sanitize_tag(tag: str) -> str:
    return re.sub(r"[#.&@\s]", "", (tag or "")).strip()[:50]


def _trim(text: str) -> str:
    text = text.strip()
    if len(text) <= MAX_LEN:
        return text
    cut = text[:MAX_LEN]
    for sep in ("\n", ". ", "? ", "! ", "요 ", "다 "):
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
        f"Threads 타래를 JSON으로 작성하세요.\n"
        f"카테고리: {category}\n포맷 힌트: {fmt}\n"
        f"본문 후킹 방식은 위 5가지 중 이 포맷에 가장 잘 맞는 것을 고르세요."
    )
    if category == "MBTI":
        user_prompt += f"\n(참고 유형 풀: {', '.join(MBTI_KEYWORDS.keys())})"
    if recent_posts:
        joined = "\n---\n".join(p[:100] for p in recent_posts[:10])
        user_prompt += f"\n\n[최근 올린 글 - 주제/항목/문장 겹치지 않게]\n{joined}"

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
        if _is_well_formatted(cand.posts):
            break
        print(f"[WARNING] 줄바꿈이 부족한 결과 (시도 {attempt + 1}/3), 재생성합니다.")

    if thread is None or len(thread.posts) < MIN_POSTS:
        raise RuntimeError("Threads 타래 생성 실패: 유효한 결과가 없습니다.")

    posts = [_trim(p) for p in thread.posts if p and p.strip()][:MAX_POSTS]
    if len(posts) < MIN_POSTS:
        raise RuntimeError("Threads 타래 생성 실패: 답글이 비어 있습니다.")
    tag = _sanitize_tag(thread.topic_tag) or category

    if with_cta:
        posts.append(build_cta())
    return GeneratedThread(category=category, topic_tag=tag, posts=posts, has_cta=with_cta)


if __name__ == "__main__":
    # 미리보기: python -m pipeline.threads_content [사주|MBTI|운세] [cta]
    cat = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in CATEGORY_WEIGHTS else None
    t = generate_threads_thread(category=cat, with_cta="cta" in sys.argv)
    print(f"[{t.category}] 태그: {t.topic_tag} | CTA: {t.has_cta}")
    for i, p in enumerate(t.posts):
        print(f"\n--- {'본문' if i == 0 else f'답글 {i}'} ({len(p)}자) ---\n{p}")
