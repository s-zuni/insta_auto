"""
릴스 주제 기획기 (크롤링 대체).

외부 뉴스/타사 상품을 긁어오지 않고, 우리 계정에서 실제로 터진 공식을 재료로 주제를 만듭니다.

[검증된 공식] "을목 여자 특징? 이거 모르면" (게시 1일 만에 조회 1,300+, 타 콘텐츠 대비 6배 이상)
  = [내 정체성 타겟: 일간(오행+음양) + 성별] + [궁금증 갭: "이거 모르면"]
  - 보는 사람이 "이거 내 얘기네"라고 즉시 자기 대입할 수 있는 좁은 대상 지정
  - 결론을 숨긴 미완결 문장(손실 회피 + 호기심)
  - 일간은 10개 x 성별 2 = 20칸의 '내 칸'이 있어 반복 제작해도 소재가 마르지 않음

주제 선정: 최근 게시 이력과 겹치지 않게 (일간, 성별, 포맷) 조합을 로테이션하고, 승자 공식 계열(을목/목 오행)은 가중치를 준다.
"""
import random
import re
import sys
from typing import Any, Dict, List, Tuple

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

MBTI_TYPES = [
    "INTJ", "INTP", "ENTJ", "ENTP", "INFJ", "INFP", "ENFJ", "ENFP",
    "ISTJ", "ISFJ", "ESTJ", "ESFJ", "ISTP", "ISFP", "ESTP", "ESFP",
]

# 일간 10종 (한글 표기만 사용: 나레이션 한자 금지 규칙)
DAY_MASTERS = ["갑목", "을목", "병화", "정화", "무토", "기토", "경금", "신금", "임수", "계수"]
# 승자 공식(을목)과 가까운 일간을 조금 더 자주 뽑는다 (같은 목 오행 + 인접 음양 짝)
DAY_MASTER_WEIGHTS = {"을목": 3, "갑목": 2, "병화": 2, "정화": 2}
GENDERS = ["여자", "남자"]
GENDER_WEIGHTS = [65, 35]  # 현재 팔로워/시청층이 2030 여성 중심

# 포맷(훅 구조). {dm}=일간, {g}=성별. 전부 '정체성 타겟 + 결론 숨김' 구조.
SAJU_FORMATS: List[Tuple[str, str]] = [
    ("trait", "{dm} {g} 특징? 이거 모르면"),
    ("love", "{dm} {g}가 끌리는 일간, 이거 모르면 연애 꼬임"),
    ("money", "{dm} {g} 돈 새는 이유, 이거 모르면"),
    ("fight", "{dm} {g}랑 싸우면 절대 안 되는 이유"),
    ("sinsal", "{dm} {g}에 이 신살 있으면 생기는 일"),
    ("pair", "{dm} {g}한테 최악인 일간 vs 최고인 일간"),
    ("secret", "{dm} {g}가 겉으로 말 못 하는 속마음"),
    ("situation", "{dm} {g}가 {sit} 하는 행동, 이거 모르면"),
    ("season", "{season}에 태어난 {dm} {g} 특징, 이거 모르면"),
    ("warning", "{dm} {g}가 제일 잘 속는 말 한마디"),
    ("exlove", "{dm} {g}가 헤어지고 나서 하는 행동"),
    ("hidden", "{dm} {g}를 처음 보면 오해하는 것, 진짜는 따로"),
]

# 콘텐츠 필라(기둥). 가중치 = 제작 비율. 모두 '내 칸 찾기' 구조라 서비스(3년 사주 리포트)로 자연스럽게 이어진다.
PILLAR_WEIGHTS = {
    "identity": 20,     # 일간+성별 특징 (검증된 승자 공식)
    "couple_dm": 14,    # 남자 신금 x 여자 임수 식 일간 궁합
    "mbti_couple": 11,  # MBTI 남녀 궁합
    "job": 9,           # 일간별 직업 추천
    "travel": 6,        # 일간별 여행지 추천
    "flow3y": 8,        # 앞으로 3년 흐름 티저 (메인 상품 직결)
    "relation": 10,     # 상사/친구/부모/동료 등 '관계 속 나' (일간 x 관계 대상)
    "habit": 9,         # 카톡/소비/스트레스 등 일상 습관 (일간 x 상황)
    "sipsin": 7,        # 십성(식신·상관·편재 등) 많은 사주 특징
    "etc": 6,           # 자미두수/타로 (해당 서비스 노출)
}

# ── 다양성/디테일 재료 ──────────────────────────────────────────────
# 같은 '일간 특징'이라도 상황·계절·관계를 바꿔 끼우면 제목이 전혀 다른 영상이 된다.
SITUATIONS = [
    "카톡 답장 늦을 때", "퇴근하고 집에 오자마자", "월급 들어온 날", "썸 타는 사람한테 연락 안 올 때", "회식 끝나고 혼자 남았을 때",
    "새벽 3시에 잠 안 올 때", "첫 데이트 전날 밤", "이직 고민이 터지는 일요일 밤", "친구한테 서운한데 말 못 할 때", "헤어진 다음 날",
    "연인이 약속에 늦었을 때", "상사한테 부당한 말을 들었을 때", "택배 뜯는 순간", "다이어트 결심한 날", "소개팅 끝나고 집 가는 길",
    "단톡방에서 혼자 조용할 때", "충동구매 장바구니 앞에서", "연락 끊긴 친구 생각날 때", "시험·면접 전날", "비 오는 날 약속 취소됐을 때",
    "고백하려다 말았을 때", "SNS 염탐하다 현타 올 때", "혼자 여행 가고 싶어지는 순간", "부모님이랑 통화 끝나고", "사과해야 하는데 자존심 상할 때",
]
SEASONS = ["봄", "여름", "가을", "겨울"]  # 태어난 계절(월령): 같은 일간도 계절에 따라 성질이 크게 달라진다
RELATIONS = ["직장 상사", "후배", "동기", "엄마", "아빠", "절친", "썸 상대", "전 애인", "룸메이트", "팀장", "동업 파트너", "시어머니"]
SIPSIN = ["식신", "상관", "편재", "정재", "편관", "정관", "편인", "정인", "비견", "겁재"]
SIPSIN_TRAIT = {
    "식신": "먹고 즐기고 표현하는 복", "상관": "말 한마디가 칼이 되는 재능", "편재": "큰돈과 사람을 굴리는 기질", "정재": "꾸준히 모으는 안정 기질",
    "편관": "압박 속에서 터지는 승부욕", "정관": "규칙과 책임을 지키는 기질", "편인": "혼자 파고드는 독특한 사고", "정인": "받아들이고 배우는 힘",
    "비견": "내 방식 고집, 동료 같은 힘", "겁재": "경쟁심과 승부 근성",
}
HABITS = ["돈 쓰는 방식", "카톡 말투", "스트레스 푸는 법", "연애 시작할 때 습관", "싸울 때 말투", "아침 루틴", "인간관계 정리하는 방식", "사과하는 방식"]

COUPLE_FORMATS = [
    "남자 {a} x 여자 {b} 궁합, 이거 모르면",
    "남자 {a}가 여자 {b}한테 빠지면 생기는 일",
    "여자 {b}가 남자 {a}한테 참다가 터지는 순간",
]
MBTI_COUPLE_FORMATS = [
    "남자 {m1} x 여자 {m2} 궁합, 이거 모르면",
    "여자 {m2}가 남자 {m1}한테 끌리는 진짜 이유",
    "남자 {m1} x 여자 {m2}, 사귀면 제일 많이 싸우는 이유",
]
JOB_FORMATS = [
    "{dm} {g}한테 맞는 직업, 이거 모르면 이직만 반복", "{dm} {g}가 직장에서 빛나는 자리 vs 말라 죽는 자리",
    "{season}생 {dm} {g}한테 맞는 일, 이거 모르면", "{dm} {g}가 퇴사 충동 오는 진짜 이유", "{dm} {g}는 프리랜서 vs 회사, 이게 갈린다",
]
TRAVEL_FORMATS = [
    "{dm}한테 맞는 여행지, 이거 모르면 돈만 쓰고 옴", "{dm}이 충전되는 여행 vs 기 빨리는 여행",
    "{season}에 {dm}이 가야 하는 곳, 이거 모르면", "{dm} 혼자 여행 vs 같이 여행, 이게 맞다",
]
FLOW_FORMATS = [
    "{dm} {g} 앞으로 3년 흐름, 이거 모르면", "{dm} {g}가 앞으로 3년 안에 꼭 겪는 변화",
    "{dm} {g} 올해 남은 기간, 돈·연애·일 중 뭐가 먼저 풀리나", "{dm} {g}가 지금 준비해야 3년 뒤 달라지는 것",
]
RELATION_FORMATS = [
    "{dm} {g}가 {rel}이랑 부딪히는 진짜 이유", "{rel}이 {dm} {g}한테 절대 하면 안 되는 말", "{dm} {g}가 {rel} 앞에서만 작아지는 이유",
    "{rel}한테 {dm} {g}가 꼭 알아야 할 한 가지",
]
HABIT_FORMATS = [
    "{dm} {g}의 {habit}, 이거 모르면 계속 같은 실수", "{dm} {g}가 {sit} 하는 행동", "{dm} {g}는 {habit}만 봐도 티가 난다",
]
SIPSIN_FORMATS = [
    "{ss} 많은 {g}, 이거 모르면 연애가 꼬인다", "{ss} 강한 사람이 직장에서 겪는 일", "사주에 {ss} 있는 {g} 특징? 이게 소름인 이유",
    "{ss} 많은 {dm} {g}, 매력인데 아픈 점",
]
ETC_TOPICS = [
    ("JAMIDOSU", "명궁이 이런 사람은 평생 이게 숙제, 이거 모르면"),
    ("JAMIDOSU", "자미두수 재백궁으로 보는 돈 모이는 사람 특징"),
    ("TAROT", "타로 3장 중 하나 고르세요, 지금 나한테 필요한 한마디"),
    ("TAROT", "썸 타는 그 사람 속마음 타로, 카드 1장 고르기"),
]

MBTI_FORMATS: List[Tuple[str, str]] = [
    ("cross", "{mbti}인데 {dm}이면 생기는 일"),
    ("trait", "{mbti} {g} 특징? 사주로 보면 이게 진짜 이유"),
    ("love", "{mbti} {g}가 연애에서 꼭 망하는 순간"),
]

# 필라별 LLM 지시 (사주 지식으로만 구성, 서비스 홍보는 CTA가 따로 담당)
PILLAR_GUIDE = {
    "identity": "일상 장면 3가지로 공감을 쌓고, 좋은 점 1 : 아픈 점 2 비율로 쓴다.",
    "couple_dm": "남녀 일간의 천간 합·충·상생·상극에 근거한 궁합. 둘이 싸우는 장면과 화해하는 법을 구체적으로. 단정적 이별/불행 예언 금지.",
    "mbti_couple": "두 유형의 소통 방식 차이(대화, 갈등, 사과 방식)를 장면 중심으로. 사주 한 줄을 곁들여 서비스(MBTI x 사주) 정체성을 드러낸다.",
    "job": "일간의 성질(자연물 비유)에 맞는 업무 환경/직무/일하는 방식. 구체 직업 3개 + 피해야 할 환경 1개.",
    "travel": "일간의 오행 성질에 맞는 여행 환경(바다/숲/도시/온천 등) 비유 중심. 특정 상호/가격/실시간 정보 언급 금지.",
    "flow3y": "앞으로 3년을 '준비기-확장기-정리기' 같은 큰 틀로만 설명. 특정 연도의 간지·운세를 단정하지 말 것.",
    "relation": "일간의 성질이 그 관계에서 어떻게 부딪히는지 실제 대화/장면 1~2개로 보여주고, 풀어내는 말투·행동 팁 하나로 끝낸다. 상대 비난 금지.",
    "habit": "한 가지 습관/상황만 깊게 판다. 그 순간의 속마음 대사를 따옴표 없이 구어체로 보여주고, 사주 근거(오행 성질) 한 줄.",
    "sipsin": "십성 이름을 쉬운 말로 풀어(예: 식신=표현으로 먹고사는 복) 장점 1 : 아픈 점 2. 십성 용어는 한글로 정확히.",
    "etc": "자미두수는 궁위를, 타로는 선택형 3장을 쉬운 말로. 영상 끝에서 해당 서비스로 이어지게 호기심을 남긴다.",
}


def _recent_topics(limit: int = 30) -> List[str]:
    """최근 게시 주제/제목 (중복 로테이션 방지용). DB가 없거나 실패하면 빈 리스트."""
    try:
        from pipeline.insights import _conn
        conn = _conn()
        try:
            rows = conn.execute(
                "SELECT topic, title FROM published_posts ORDER BY published_at DESC LIMIT ?", (limit,)
            ).fetchall()
        finally:
            conn.close()
        return [f"{r['topic'] or ''} {r['title'] or ''}" for r in rows]
    except Exception:
        return []


def _weighted_pick_dm(recent: List[str]) -> str:
    """최근에 쓴 일간은 가중치를 크게 낮춰 로테이션."""
    weights = []
    for dm in DAY_MASTERS:
        w = DAY_MASTER_WEIGHTS.get(dm, 1)
        used = sum(1 for t in recent[:12] if dm in t)
        weights.append(max(w / (1 + 2 * used), 0.05))
    return random.choices(DAY_MASTERS, weights=weights, k=1)[0]


_MBTI_RE = re.compile(r"[IE][NS][TF][JP]")

_PILLAR_MARKERS = {
    "identity": lambda t: "특징" in t,
    "couple_dm": lambda t: "남자" in t and "여자" in t and not _MBTI_RE.search(t.upper()),
    "mbti_couple": lambda t: bool(_MBTI_RE.search(t.upper())) and "궁합" in t,
    "job": lambda t: "직업" in t or "직장" in t,
    "travel": lambda t: "여행" in t,
    "flow3y": lambda t: "3년" in t,
    "relation": lambda t: any(r in t for r in RELATIONS),
    "habit": lambda t: any(h in t for h in ("카톡", "스트레스", "돈 쓰는", "싸울 때", "사과")),
    "sipsin": lambda t: any(x in t for x in SIPSIN),
    "etc": lambda t: "자미두수" in t or "타로" in t,
}


def _pick_pillar(recent: List[str]) -> str:
    """제작 비율대로 뽑되, 최근 게시와 같은 필라가 연속되지 않도록 가중치를 낮춘다."""
    names = list(PILLAR_WEIGHTS)
    weights = []
    for n in names:
        used = sum(1 for t in recent[:6] if _PILLAR_MARKERS[n](t))
        weights.append(PILLAR_WEIGHTS[n] / (1 + 2 * used))
    return random.choices(names, weights=weights, k=1)[0]


def _seed_spec(kind: str, recent: List[str], exclude_dm: str = "", pillar: str = "") -> Dict[str, str]:
    """기획안 1개분의 씨앗(필라/시리즈/일간/성별/포맷)을 만든다. LLM은 이걸 다듬기만 한다."""
    pillar = pillar or _pick_pillar(recent)
    gender = random.choices(GENDERS, weights=GENDER_WEIGHTS, k=1)[0]
    for _ in range(10):
        dm = _weighted_pick_dm(recent)
        if dm != exclude_dm:
            break
    # 제목/훅을 구체화할 재료(상황·계절·관계·습관·십성). 최근에 안 쓴 것을 우선 뽑는다.
    detail = {
        "sit": _pick_fresh(SITUATIONS, recent), "season": _pick_fresh(SEASONS, recent), "rel": _pick_fresh(RELATIONS, recent),
        "habit": _pick_fresh(HABITS, recent), "ss": _pick_fresh(SIPSIN, recent),
    }
    base = {"pillar": pillar, "series": "SAJU", "mbti": "", "dm": dm, "gender": gender, "format": pillar, "detail": ""}

    def fmt(tpl: str, **kw) -> str:
        return tpl.format(dm=dm, g=gender, **detail, **kw)

    if pillar == "couple_dm":
        a, b = dm, _weighted_pick_dm(recent)  # 같은 일간끼리도 허용(비견 궁합)
        base.update(dm=f"남자 {a} x 여자 {b}", gender="", pattern=random.choice(COUPLE_FORMATS).format(a=a, b=b),
                    detail=f"장면 힌트: {detail['sit']}")
    elif pillar == "mbti_couple":
        m1, m2 = random.sample(MBTI_TYPES, 2)
        base.update(series="MBTI", mbti=m1, dm="", gender="",
                    pattern=random.choice(MBTI_COUPLE_FORMATS).format(m1=m1, m2=m2), detail=f"장면 힌트: {detail['sit']}")
    elif pillar == "job":
        base.update(pattern=fmt(random.choice(JOB_FORMATS)), detail=f"태어난 계절: {detail['season']}")
    elif pillar == "travel":
        base.update(gender="", pattern=fmt(random.choice(TRAVEL_FORMATS)), detail=f"계절: {detail['season']}")
    elif pillar == "flow3y":
        base["pattern"] = fmt(random.choice(FLOW_FORMATS))
    elif pillar == "relation":
        base.update(pattern=fmt(random.choice(RELATION_FORMATS)), detail=f"관계 대상: {detail['rel']}")
    elif pillar == "habit":
        base.update(pattern=fmt(random.choice(HABIT_FORMATS)), detail=f"습관/상황: {detail['habit']} / {detail['sit']}")
    elif pillar == "sipsin":
        base.update(pattern=fmt(random.choice(SIPSIN_FORMATS)), detail=f"십성: {detail['ss']} = {SIPSIN_TRAIT[detail['ss']]}")
    elif pillar == "etc":
        series, pat = random.choice(ETC_TOPICS)
        base.update(series=series, dm="", gender="", pattern=pat)
    else:  # identity (+ 일부 MBTI x 일간 교차)
        if kind == "MBTI":
            mbti = random.choice(MBTI_TYPES)
            fid, tpl = random.choice(MBTI_FORMATS)
            base.update(series="MBTI", mbti=mbti, format=fid, pattern=fmt(tpl, mbti=mbti), detail=f"장면 힌트: {detail['sit']}")
        else:
            fid, tpl = random.choice(SAJU_FORMATS)
            base.update(format=fid, pattern=fmt(tpl), detail=f"장면 힌트: {detail['sit']} / 계절: {detail['season']}")
    return base


def _pick_fresh(pool: List[str], recent: List[str]) -> str:
    """최근 게시 텍스트에 안 나온 항목을 우선 뽑는다(전부 나왔으면 무작위)."""
    fresh = [x for x in pool if not any(x in t for t in recent[:20])]
    return random.choice(fresh or pool)


def _fit_title(text: str, limit: int = 16) -> str:
    """한자 제거 후 16자(큰 글씨 2줄) 이내로 맞춘다. 가능하면 어절 경계에서 자른다."""
    from pipeline.text_utils import sanitize_title
    t = sanitize_title(text.replace("\n", " "))
    if len(t) <= limit:
        return t
    cut = t[:limit]
    if " " in cut and t[limit] != " ":
        cut = cut[: cut.rfind(" ")]
    return cut.strip(" ,")


def _fallback_option(seed: Dict[str, str]) -> Dict[str, str]:
    pat = seed["pattern"]
    first = pat.split(",")[0].strip()
    title = _fit_title(first if len(first) <= 16 else re.sub(r"[?,]", "", pat))
    who = " ".join(x for x in (seed["dm"], seed["gender"]) if x) or seed["mbti"] or "나"
    return {
        "series": seed["series"], "mbti": seed["mbti"],
        "topic": pat, "trend_hint": "",
        "title": title,
        "hook": f"{who}라면 이 영상 끝까지 보세요. 모르면 계속 같은 데서 넘어져요.",
        "summary": f"{pat} ({seed['pillar']} 필라)",
    }


def get_planned_reels_proposals() -> Dict[str, Any]:
    """크롤링 없이 '승자 공식' 기반으로 서로 다른 2개 기획안(A/B)을 만든다."""
    from pipeline.script_gen import generate_json

    recent = _recent_topics()
    seed_a = _seed_spec("SAJU", recent)
    seed_b = _seed_spec("MBTI" if random.random() < 0.3 else "SAJU", recent, exclude_dm=seed_a["dm"])
    for _ in range(5):  # A/B는 서로 다른 필라로
        if seed_b["pillar"] != seed_a["pillar"]:
            break
        seed_b = _seed_spec("SAJU", recent, exclude_dm=seed_a["dm"])

    examples_block = ""
    try:
        from pipeline.insights import get_top_examples, format_examples_for_prompt
        examples_block = format_examples_for_prompt(get_top_examples(n=3))
    except Exception as e:
        print(f"[PLANNER][WARN] 성과 예시 로드 실패(무시): {e}")

    recent_block = ""
    if recent:
        recent_block = "[최근 게시 주제 - 겹치지 않게]\n" + "\n".join(f"- {t.strip()[:50]}" for t in recent[:15])

    def _desc(label: str, s: Dict[str, str]) -> str:
        extra = f" | MBTI: {s['mbti']}" if s["mbti"] else ""
        return (f'{label}: 필라={s["pillar"]} | series={s["series"]}{extra} | 일간/대상={s["dm"]} {s["gender"]}'
                f' | 훅 뼈대="{s["pattern"]}" | 구체화 재료: {s.get("detail", "")} | 작성 지침: {PILLAR_GUIDE[s["pillar"]]}')

    prompt = f"""{examples_block}

{recent_block}

[우리 계정의 검증된 공식]
"을목 여자 특징? 이거 모르면" 릴스가 하루도 안 돼 조회수 1,300+ (다른 콘텐츠 대비 6배 이상).
성공 요인: (1) 일간+성별로 대상을 아주 좁게 지정해 '내 얘기'로 느끼게 함 (2) 결론을 숨긴 미완결 문장으로 궁금증 유발
(3) 제목이 짧고 한눈에 읽힘.

아래 두 씨앗을 이 공식 그대로 살려서 릴스 기획안 2개(A안, B안)로 다듬으세요.
{_desc("A안", seed_a)}
{_desc("B안", seed_b)}

[규칙]
- 외부 뉴스/타사 서비스/상품/사이트 언급 절대 금지. 오직 사주(일간·오행·십성·신살)와 MBTI 지식으로만 구성.
- 대상(일간+성별, 또는 궁합 당사자)은 제목에 반드시 드러내고, 결론은 제목/훅에서 숨긴다("이거 모르면", "~하는 진짜 이유" 등).
- 훅 뼈대는 유지하되 어색하면 자연스럽게 다듬을 수 있음. 제목 16자 이내(큰 글씨 2줄 표시).
- '오늘의 운세' 같은 일일 운세 금지. 후킹은 초반 3초 안에 끝나는 한두 문장.
- 한자 사용 금지(한글 표기만). 제목에도 한자 금지.
- [디테일 규칙] 일반론("특징", "이유")만 쓰지 말고 '구체화 재료'의 상황/계절/관계/십성 중 하나 이상을 제목이나 topic에 녹여 구체적인 한 장면이 떠오르게 한다.
  topic에는 영상에서 다룰 장면 3개와 반전 한 줄까지 한 문장으로 요약해 적는다(summary와 별개).
- [다양성 규칙] 같은 문장 구조("~특징? 이거 모르면")를 A/B에서 반복하지 말고 어미·질문 형태·숫자 사용을 서로 다르게 쓴다.
  최근 게시 주제와 같은 대상·상황·단어를 재사용하지 않는다. 제목은 질문형, 경고형, 대비형(vs), 숫자형(3가지) 중 서로 다른 형태를 고른다.

JSON 포맷:
{{
  "option_a": {{"series": "{seed_a['series']}", "mbti": "{seed_a['mbti']}", "topic": "구체적 주제", "title": "제목", "hook": "후킹 대사", "summary": "1줄 요약"}},
  "option_b": {{"series": "{seed_b['series']}", "mbti": "{seed_b['mbti']}", "topic": "구체적 주제", "title": "제목", "hook": "후킹 대사", "summary": "1줄 요약"}}
}}
"""
    try:
        data = generate_json(None, prompt, temperature=0.85)
        if "option_a" in data and "option_b" in data:
            for key, seed in (("option_a", seed_a), ("option_b", seed_b)):
                opt = data[key]
                opt["series"], opt["mbti"] = seed["series"], seed["mbti"]  # 시리즈/유형은 씨앗 고정
                opt["trend_hint"] = ""
                opt["title"] = _fit_title(str(opt.get("title", "")) or seed["pattern"])
            return data
    except Exception as e:
        print(f"[PLANNER][WARN] 기획안 생성 에러: {e}")

    return {"option_a": _fallback_option(seed_a), "option_b": _fallback_option(seed_b)}


def classify_custom_topic(text: str) -> Dict[str, str]:
    """
    사용자가 직접 입력한 주제를 파이프라인 series/mbti/topic으로 분류합니다.
    - 텍스트 안의 MBTI 4글자 유형이 있으면 MBTI 시리즈(+해당 유형)
    - 타로/신점/자미두수 키워드가 있으면 해당 시리즈
    - 그 외는 SAJU 시리즈
    """
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
    import json
    print(json.dumps(get_planned_reels_proposals(), ensure_ascii=False, indent=2))
