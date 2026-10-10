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
]

# 콘텐츠 필라(기둥). 가중치 = 제작 비율. 모두 '내 칸 찾기' 구조라 서비스(3년 사주 리포트)로 자연스럽게 이어진다.
PILLAR_WEIGHTS = {
    "identity": 25,     # 일간+성별 특징 (검증된 승자 공식)
    "couple_dm": 20,    # 남자 신금 x 여자 임수 식 일간 궁합
    "mbti_couple": 15,  # MBTI 남녀 궁합
    "job": 15,          # 일간별 직업 추천
    "travel": 10,       # 일간별 여행지 추천
    "flow3y": 10,       # 앞으로 3년 흐름 티저 (메인 상품 직결)
    "etc": 5,           # 자미두수/타로 (해당 서비스 노출)
}

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
JOB_FORMATS = ["{dm} {g}한테 맞는 직업, 이거 모르면 이직만 반복", "{dm} {g}가 직장에서 빛나는 자리 vs 말라 죽는 자리"]
TRAVEL_FORMATS = ["{dm}한테 맞는 여행지, 이거 모르면 돈만 쓰고 옴", "{dm}이 충전되는 여행 vs 기 빨리는 여행"]
FLOW_FORMATS = ["{dm} {g} 앞으로 3년 흐름, 이거 모르면", "{dm} {g}가 앞으로 3년 안에 꼭 겪는 변화"]
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
    base = {"pillar": pillar, "series": "SAJU", "mbti": "", "dm": dm, "gender": gender, "format": pillar}

    if pillar == "couple_dm":
        a, b = dm, _weighted_pick_dm(recent)  # 같은 일간끼리도 허용(비견 궁합)
        base.update(dm=f"남자 {a} x 여자 {b}", gender="", pattern=random.choice(COUPLE_FORMATS).format(a=a, b=b))
    elif pillar == "mbti_couple":
        m1, m2 = random.sample(MBTI_TYPES, 2)
        base.update(series="MBTI", mbti=m1, dm="", gender="",
                    pattern=random.choice(MBTI_COUPLE_FORMATS).format(m1=m1, m2=m2))
    elif pillar == "job":
        base["pattern"] = random.choice(JOB_FORMATS).format(dm=dm, g=gender)
    elif pillar == "travel":
        base.update(gender="", pattern=random.choice(TRAVEL_FORMATS).format(dm=dm))
    elif pillar == "flow3y":
        base["pattern"] = random.choice(FLOW_FORMATS).format(dm=dm, g=gender)
    elif pillar == "etc":
        series, pat = random.choice(ETC_TOPICS)
        base.update(series=series, dm="", gender="", pattern=pat)
    else:  # identity (+ 일부 MBTI x 일간 교차)
        if kind == "MBTI":
            mbti = random.choice(MBTI_TYPES)
            fid, tpl = random.choice(MBTI_FORMATS)
            base.update(series="MBTI", mbti=mbti, format=fid, pattern=tpl.format(mbti=mbti, dm=dm, g=gender))
        else:
            fid, tpl = random.choice(SAJU_FORMATS)
            base.update(format=fid, pattern=tpl.format(dm=dm, g=gender))
    return base


def _fallback_option(seed: Dict[str, str]) -> Dict[str, str]:
    pat = seed["pattern"]
    first = pat.split(",")[0].strip()
    title = (first if len(first) <= 16 else re.sub(r"[?,]", "", pat)[:16]).strip()
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
        recent_block = "[최근 게시 주제 - 겹치지 않게]\n" + "\n".join(f"- {t.strip()[:50]}" for t in recent[:10])

    def _desc(label: str, s: Dict[str, str]) -> str:
        extra = f" | MBTI: {s['mbti']}" if s["mbti"] else ""
        return (f'{label}: 필라={s["pillar"]} | series={s["series"]}{extra} | 일간/대상={s["dm"]} {s["gender"]}'
                f' | 훅 뼈대="{s["pattern"]}" | 작성 지침: {PILLAR_GUIDE[s["pillar"]]}')

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
- 한자 사용 금지(한글 표기만).

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
                opt["title"] = str(opt.get("title", "")).replace("\n", " ")[:16]
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
