"""
100만 바이럴 릴스 주제 기획기 (투트랙: 대중 확장 80% + 사주 코어 20%).

[왜 투트랙인가?]
- 기존 승자 공식("을목 여자 특징? 이거 모르면", 조회 1,300+)은 본인이 '을목'인 줄 아는 상위 5%에게는 강력하지만,
  인스타 릴스 피드의 일반 대중 95%는 자기 일간을 몰라 1초 만에 스와이프합니다.
- 100만 뷰를 터뜨리려면:
  1. [대중 확장 트랙 (80%)] 첫 3초는 누구나 즉시 자기 대입할 수 있는 '일상 증상·연애 행동·체크리스트·밸런스 게임·페이크아웃(통념 반박)·POV 카톡 상황'으로 100% 대중의 스크롤을 멈추고,
     본문 중반(씬 4~6)에서 "사실 이게 사주에 OO(일간/도화살/홍염살/십성)이 있는 사람들의 소름 돋는 특징인데"로 풀어야 합니다.
  2. [사주 코어 트랙 (20%)] 기존처럼 일간/궁합/MBTI를 전면에 내세워 코어 타겟의 전환율을 극대화합니다.
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
DAY_MASTER_WEIGHTS = {"을목": 3, "갑목": 2, "병화": 2, "정화": 2, "신금": 2, "임수": 2}
GENDERS = ["여자", "남자"]
GENDER_WEIGHTS = [68, 32]  # 주요 타겟층 2030 여성 중심

# ── [mbtiju 초개인화 타겟 재료: 출생연도 & 12간지] ─────────────────────
BIRTH_YEARS = [
    "94년생", "95년생", "96년생", "97년생", "98년생",
    "99년생", "00년생", "01년생", "02년생", "03년생", "04년생"
]
YEAR_ZODIAC_MAP = {
    "94년생": "개띠",
    "95년생": "돼지띠",
    "96년생": "쥐띠",
    "97년생": "소띠",
    "98년생": "호랑이띠",
    "99년생": "토끼띠",
    "00년생": "용띠",
    "01년생": "뱀띠",
    "02년생": "말띠",
    "03년생": "양띠",
    "04년생": "원숭이띠",
}

# 2030 핵심 고민 카테고리 (연애 45% / 재물·커리어 35% / 본성·관계 20%)
CONCERNS_LOVE = [
    "결혼운", "연애운", "썸 속마음", "이별 후 심리", "천생연분 궁합", "인연 타이밍", "연애할 때 고장 나는 이유"
]
CONCERNS_CAREER = [
    "이직운", "재물 대운", "직장 내 포지션", "대운 전환 신호", "번아웃 극복", "퇴사 고민"
]
CONCERNS_TRAITS = [
    "특징 3가지", "손절 기준", "인간관계 정리하는 법", "남들이 모르는 본성"
]

SINSALS = ["도화살", "홍염살", "역마살", "화개살", "백호살", "귀문관살"]
SINSAL_TRAIT = {
    "도화살": "가만히 있어도 시선이 모이는 묘한 매력",
    "홍염살": "일대일로 눈 마주치면 상대를 무장해제시키는 매력",
    "역마살": "한곳에 묶이면 병나고 움직여야 돈과 운이 트이는 기운",
    "화개살": "혼자만의 깊은 몰입과 예술적 감수성, 고독한 매력",
    "백호살": "한 번 꽂히면 끝장을 보는 폭발적인 프로페셔널 에너지",
    "귀문관살": "남들이 못 보는 디테일과 촉이 소름 돋게 발달한 기질",
}

# ── [트랙 1] 100만 대중 확장용 바이럴 포맷 (스레드 30가지 바이럴 포맷을 사주xMBTI 도메인으로 재해석) ──
VIRAL_MASS_FORMATS: List[Tuple[str, str, str]] = [
    # (포맷코드, 훅/제목 패턴, 연출 지침)
    (
        "checklist",
        "여기서 3개 이상 맞으면 {sinsal} 있는 {g}",
        "체크리스트형: 씬 1에서 '5개 중 3개 이상 해당되면 100%입니다'로 시작해 누구나 손가락 접으며 세어보게 만든 뒤, 중반에 {sinsal}({dm}) 사주 특징으로 반전 풀이.",
    ),
    (
        "checklist_symptom",
        "{sit} 이 행동 하면 소름 돋는 사주 특징",
        "일상 증상 체크형: 씬 1~3에서 '{sit}' 누구나 겪는 구체적 행동 3가지를 먼저 폭격해 '헐 내 얘긴데' 공감을 유도하고, 씬 4에서 사실 이게 '{dm} {g}'의 대표 기질임을 공개.",
    ),
    (
        "fakeout",
        "착한 줄 알았는데 손절 제일 칼같은 사람 특징",
        "페이크아웃(통념 반박)형: 흔한 통념을 뒤집는 문장으로 시작('연락 잘 안 한다고 무심한 게 아닙니다' / '겉은 순한데 속은 제일 냉정한 이유') 후 사주 '{dm}'과 '{ss}' 기질로 원인 해부.",
    ),
    (
        "balance_game",
        "다정한 무토 남친 vs 설레는 병화 남친",
        "밸런스 게임(A vs B)형: 극단적으로 매력과 단점이 갈리는 두 성향(예: 안정형 vs 도파민형, 또는 {dm} vs 상대 일간)을 동시에 비교해 댓글 논쟁과 친구 태그를 유도.",
    ),
    (
        "pov_chat",
        "썸 타는데 {sit} 이러면 100% 이 심리",
        "POV·카톡 속마음 해부형: 1인칭 시점이나 실제 카톡 답장 상황('{sit}')으로 시작해 겉말투와 진짜 속마음의 괴리를 사주 '{dm}'과 '{mbti}' 심리로 콕 집어줌.",
    ),
    (
        "mystery_drop",
        "대운 터지기 직전인 사람이 갑자기 끊는 것",
        "떡밥·미스터리(징조)형: 첫 문장에서 핵심 대상을 바로 공개하지 않고('인생 풀리기 직전엔 갑자기 이것부터 정리합니다') 끝까지 보게 만든 뒤 3년 운의 흐름과 '{dm}' 기질로 연결.",
    ),
    (
        "top3_ranking",
        "겉은 순한데 건드리면 제일 무서운 유형 TOP 3",
        "순위 매기기(리스티클)형: 3위 -> 2위 -> 대망의 1위('{dm} {g}' 또는 '{mbti}') 순으로 빠르게 치고 나가 시청 지속 시간을 끝까지 붙잡음.",
    ),
]

# ── [트랙 2] 사주 코어 정체성 포맷 (기존 승자 공식 고도화) ──
SAJU_FORMATS: List[Tuple[str, str]] = [
    ("trait", "{dm} {g} 특징? 이거 모르면"),
    ("love", "{dm} {g}가 끌리는 일간, 이거 모르면 연애 꼬임"),
    ("money", "{dm} {g} 돈 새는 이유, 이거 모르면"),
    ("fight", "{dm} {g}랑 싸우면 절대 안 되는 이유"),
    ("sinsal", "{dm} {g}에 {sinsal} 있으면 생기는 일"),
    ("pair", "{dm} {g}한테 최악인 일간 vs 최고인 일간"),
    ("secret", "{dm} {g}가 겉으로 말 못 하는 속마음"),
    ("situation", "{dm} {g}가 {sit} 하는 행동, 이거 모르면"),
    ("season", "{season}에 태어난 {dm} {g} 특징, 이거 모르면"),
    ("warning", "{dm} {g}가 제일 잘 속는 말 한마디"),
    ("exlove", "{dm} {g}가 헤어지고 나서 하는 행동"),
    ("hidden", "{dm} {g}를 처음 보면 오해하는 것, 진짜는 따로"),
]

# 콘텐츠 필라(기둥). 가중치 = 제작 비율.
# mbtiju 3대 하이브리드 축(초타겟팅 40% : 사주 심층 융합 30% : 시의성 랭킹 30%) 중심 편성
PILLAR_WEIGHTS = {
    "pillar_target_zodiac": 38,  # [Track A - 초타겟팅 핀셋형 40%] 출생연도/띠 + MBTI + 2030 현실 고민
    "pillar_deep_saju": 28,       # [Track B - 사주 심층 융합형 30%] 출생연도 + 일간 + MBTI + 미래 예측
    "pillar_season_rank": 28,     # [Track C - 시의성 랭킹/총운형 30%] 하반기/병오년 대박 사주xMBTI 조합 TOP 3
    "identity": 2,                # [사주 코어형] 일간+성별 특징
    "relation": 2,                # [사주 코어형] 관계 속 나
    "habit": 1,                   # [사주 코어형] 일상 습관
    "sipsin": 1,                  # [사주 코어형] 십성/신살 특징
}

# ── 다양성/디테일 재료 ──────────────────────────────────────────────
SITUATIONS = [
    "카톡 답장 늦을 때", "퇴근하고 집에 오자마자", "월급 들어온 날", "썸 타는 사람한테 연락 안 올 때", "회식 끝나고 혼자 남았을 때",
    "새벽 2시에 잠 안 올 때", "첫 데이트 전날 밤", "이직 고민이 터지는 일요일 밤", "친구한테 서운한데 말 못 할 때", "헤어진 다음 날",
    "연인이 약속에 늦었을 때", "상사한테 부당한 말을 들었을 때", "택배 뜯는 순간", "다이어트 결심한 날", "소개팅 끝나고 집 가는 길",
    "단톡방에서 혼자 조용할 때", "충동구매 장바구니 앞에서", "연락 끊긴 친구 생각날 때", "면접 전날 밤", "비 오는 날 약속 취소됐을 때",
    "고백하려다 말았을 때", "인스타 스토리 염탐하다 현타 올 때", "혼자 여행 가고 싶어지는 순간", "사과해야 하는데 자존심 상할 때",
]
SEASONS = ["봄", "여름", "가을", "겨울"]
RELATIONS = ["직장 상사", "후배", "동기", "엄마", "절친", "썸 상대", "전 애인", "룸메이트", "팀장", "동업 파트너"]
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
    "올해 하반기부터 3년 동안 운 터지는 사람 징조", "{dm} {g} 앞으로 3년 흐름, 이거 모르면",
    "{dm} {g}가 앞으로 3년 안에 꼭 겪는 변화", "3년 동안 막혔던 운이 갑자기 풀릴 때 나타나는 신호",
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
    ("cross", "{mbti}인데 {dm}이면 생기는 소름 돋는 특징"),
    ("trait", "겉은 {mbti}인데 속이 완전히 다른 진짜 이유"),
    ("love", "{mbti} {g}가 연애에서 꼭 참다가 터지는 순간"),
]

# 필라별 LLM 지시 (사주 지식으로만 구성, 서비스 홍보는 CTA가 따로 담당)
PILLAR_GUIDE = {
    "pillar_target_zodiac": "[mbtiju Track A - 초타겟팅 핀셋형 40%] 출생연도(예: 00년생) + 띠(예: 용띠) + MBTI를 직격 호명하여 시청자 0.5초 스크롤 정지. 씬 2~3에서 MBTI 현실 행동/고민 묘사 -> 씬 4~5에서 띠와 사주 기운의 근본 원인 해부 -> 씬 6~7에서 미래 운세 예측 및 개운 솔루션 제공.",
    "pillar_deep_saju": "[mbtiju Track B - 사주 심층 융합형 30%] 출생연도(예: 98년생) + 사주 일간(예: 임수) + MBTI를 융합하여 mbtiju의 전문성 부각. MBTI로 드러나는 겉성향 뒤에 숨겨진 사주 일간의 오행 에너지를 심층 분석하고, 올해/내년 구체적인 운의 흐름 예측과 맞춤 처방 제공.",
    "pillar_season_rank": "[mbtiju Track C - 시의성 랭킹/총운형 30%] 특정 연도에 한정되지 않고 대중 전체의 호기심을 폭발시키는 시의성(올해 하반기/2026 병오년/앞으로 3년) 사주xMBTI 랭킹 TOP 3. 순차적으로 3위 -> 2위 -> 1위를 공개하며 높은 완독률과 바이럴 확산 달성.",
    "viral_checklist": "[100만 대중 확장 - 체크리스트형] 첫 3초는 어려운 사주 용어 없이 누구나 즉시 손가락 접으며 세어볼 수 있는 일상 행동 4~5가지 체크리스트('5개 중 3개 이상 맞으면...')로 시작하고, 중반에 이게 사주 신살/일간 특징임을 밝혀 저장과 친구 공유를 폭발시킨다.",
    "viral_fakeout": "[100만 대중 확장 - 페이크아웃 반전형] 첫 3초에서 사람들의 흔한 통념을 정면 반박('연락 안 한다고 관심 없는 게 아닙니다' / '다 퍼주는 사람이 손절할 땐 제일 무섭습니다')해 호기심을 극대화한 뒤, 사주 오행/십성 근거로 속마음을 해부한다.",
    "viral_pov": "[100만 대중 확장 - 일상/카톡 POV형] 첫 3초를 누구나 겪어본 생생한 장면(카톡 읽씹, 퇴근길 지하철, 새벽 감성)으로 열어 100% 공감을 얻은 뒤, 왜 그런 행동을 하는지 사주 일간과 MBTI 심리로 명쾌하게 풀어준다.",
    "viral_mystery": "[100만 대중 확장 - 떡밥·징조 미스터리형] 첫 3초에서 결론을 숨긴 강렬한 징조('운이 크게 바뀌기 직전엔 갑자기 이것부터 멀어집니다')를 던져 끝까지 보게 만들고, 앞으로 3년 운의 흐름과 연결한다.",
    "viral_balance": "[100만 대중 확장 - A vs B 밸런스 게임형] 상반된 두 가지 연애/인간관계/돈 스타일을 동시에 대비시켜 시청자가 '나는 무조건 전자/후자'라고 댓글을 달고 싶게 만든다.",
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
    "pillar_target_zodiac": lambda t: any(y in t for y in BIRTH_YEARS) or any(z in t for z in YEAR_ZODIAC_MAP.values()),
    "pillar_deep_saju": lambda t: any(dm in t for dm in DAY_MASTERS) and any(m in t for m in MBTI_TYPES),
    "pillar_season_rank": lambda t: "TOP" in t.upper() or "조합" in t or "남은 기간" in t or "병오년" in t,
    "viral_checklist": lambda t: "3개" in t or "체크" in t or "해당" in t,
    "viral_fakeout": lambda t: "인 줄 알았는데" in t or "오해" in t or "칼같은" in t,
    "viral_pov": lambda t: "카톡" in t or "썸" in t or "속마음" in t,
    "viral_mystery": lambda t: "징조" in t or "직전" in t or "신호" in t,
    "viral_balance": lambda t: "vs" in t.lower() or "VS" in t,
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


def _pick_pillar(recent: List[str], track_filter: str = "") -> str:
    """
    제작 비율대로 뽑되, 최근 게시와 같은 필라가 연속되지 않도록 가중치를 낮춘다.
    track_filter='mass' 이면 100만 대중 확장 필라만, 'core' 이면 사주/MBTI 코어 필라만 선택.
    """
    names = list(PILLAR_WEIGHTS)
    if track_filter == "mass":
        names = [n for n in names if n.startswith("viral_")]
    elif track_filter == "core":
        names = [n for n in names if not n.startswith("viral_")]

    weights = []
    for n in names:
        marker_fn = _PILLAR_MARKERS.get(n, lambda _: False)
        used = sum(1 for t in recent[:6] if marker_fn(t))
        weights.append(PILLAR_WEIGHTS[n] / (1 + 2 * used))
    return random.choices(names, weights=weights, k=1)[0]


def _seed_spec(kind: str, recent: List[str], exclude_dm: str = "", pillar: str = "", track_filter: str = "") -> Dict[str, str]:
    """기획안 1개분의 씨앗(필라/시리즈/일간/성별/포맷)을 만든다. LLM은 이걸 다듬기만 한다."""
    pillar = pillar or _pick_pillar(recent, track_filter=track_filter)
    gender = random.choices(GENDERS, weights=GENDER_WEIGHTS, k=1)[0]
    for _ in range(10):
        dm = _weighted_pick_dm(recent)
        if dm != exclude_dm:
            break
    sinsal = _pick_fresh(SINSALS, recent)
    detail = {
        "sit": _pick_fresh(SITUATIONS, recent),
        "season": _pick_fresh(SEASONS, recent),
        "rel": _pick_fresh(RELATIONS, recent),
        "habit": _pick_fresh(HABITS, recent),
        "ss": _pick_fresh(SIPSIN, recent),
        "sinsal": sinsal,
    }
    base = {"pillar": pillar, "series": "SAJU", "mbti": "", "dm": dm, "gender": gender, "format": pillar, "detail": ""}

    def fmt(tpl: str, **kw) -> str:
        return tpl.format(dm=dm, g=gender, **detail, **kw)

    if pillar == "pillar_target_zodiac":
        year = random.choice(BIRTH_YEARS)
        zodiac = YEAR_ZODIAC_MAP[year]
        mbti = random.choice(MBTI_TYPES)
        concern_cat = random.choices(["love", "career", "traits"], weights=[45, 35, 20], k=1)[0]
        if concern_cat == "love":
            concern = random.choice(CONCERNS_LOVE)
            pat = random.choice([
                f"{year} {zodiac} {mbti}의 {concern}, 이거 모르면 꼬임",
                f"{year} {zodiac} {mbti}가 연애할 때 고장 나는 진짜 이유",
                f"{year} {zodiac} {mbti}와 천생연분인 사주 궁합",
            ])
        elif concern_cat == "career":
            concern = random.choice(CONCERNS_CAREER)
            pat = random.choice([
                f"{year} {zodiac} {mbti}, 직장 이직 대운 터지는 신호",
                f"{year} {zodiac} {mbti}한테 맞는 직업과 돈복 환경",
                f"{year} {zodiac} {mbti}의 {concern}, 3년 흐름",
            ])
        else:
            concern = random.choice(CONCERNS_TRAITS)
            pat = random.choice([
                f"{year} {zodiac} {mbti} 특징 3가지, 이거 모르면 오해함",
                f"{year} {zodiac} {mbti}가 인간관계에서 손절하는 기준",
                f"{year} {zodiac} {mbti}의 숨겨진 소름 돋는 본성",
            ])
        base.update(
            series="MBTI",
            mbti=mbti,
            pattern=pat,
            detail=f"포맷: [Track A] 연도/띠 + MBTI 초타겟팅 | 대상: {year} {zodiac} + {mbti} | 고민: {concern} | 장면: {detail['sit']}",
        )
    elif pillar == "pillar_deep_saju":
        year = random.choice(BIRTH_YEARS)
        mbti = random.choice(MBTI_TYPES)
        concern_cat = random.choices(["love", "career", "traits"], weights=[45, 35, 20], k=1)[0]
        if concern_cat == "love":
            concern = random.choice(CONCERNS_LOVE)
            pat = random.choice([
                f"{year} {dm} + {mbti}의 {concern}, 올해 인연 타이밍",
                f"{year} {dm} + {mbti}, 겉은 순한데 연애할 때 손절 빠른 이유",
                f"{year} {dm} + {mbti}와 최악인 궁합 vs 최고인 궁합",
            ])
        elif concern_cat == "career":
            concern = random.choice(CONCERNS_CAREER)
            pat = random.choice([
                f"{year} {dm} + {mbti}, 2026년에 이직 대박 나는 징조",
                f"{year} {dm} + {mbti}한테 돈이 줄줄 새는 치명적 이유",
                f"{year} {dm} + {mbti} 앞으로 3년 대운 흐름",
            ])
        else:
            concern = random.choice(CONCERNS_TRAITS)
            pat = random.choice([
                f"{year} {dm} + {mbti}, 겉은 강한데 속으로 번아웃 온 진짜 원인",
                f"{year} {dm} + {mbti}가 올해 꼭 조심해야 할 사람 유형",
                f"{year} {dm} + {mbti} 특징 3가지, 남들은 절대 모름",
            ])
        base.update(
            series="MBTI",
            mbti=mbti,
            pattern=pat,
            detail=f"포맷: [Track B] 연도/일간 + MBTI 사주 심층 융합 | 대상: {year} {dm} + {mbti} | 고민: {concern} | 사주 근거: {dm} 기운과 {detail['ss']}",
        )
    elif pillar == "pillar_season_rank":
        season_time = random.choice(["올해 남은 기간", "2026년 병오년", "앞으로 3년 대운", "올해 하반기"])
        goal = random.choice(["제일 운 좋은", "돈복 터질", "결혼·연애 대박 날", "이직운 폭발할", "인생 역전할"])
        pat = random.choice([
            f"{season_time} {goal} MBTI&사주 조합 TOP 3",
            f"겉은 삐걱대는데 사주 까보면 천생연분인 MBTI 조합 3쌍",
            f"{season_time} 대운 터지기 직전인 사주xMBTI 신호 3가지",
        ])
        mbti = random.choice(MBTI_TYPES)
        base.update(
            series="MBTI",
            mbti=mbti,
            pattern=pat,
            detail=f"포맷: [Track C] 시의성 랭킹 & 총운 | 시점: {season_time} | 테마: {goal} | 사주 조합: {dm} 및 주요 오행 융합",
        )
    elif pillar == "viral_checklist":
        pat = random.choice([
            f"여기서 3개 이상 맞으면 {sinsal} 있는 {gender}",
            f"{detail['sit']} 이 3가지 다 하면 {dm} 기질",
            f"평생 돈 안 마르는 사주 체크리스트 4가지",
        ])
        base.update(
            pattern=pat,
            detail=f"포맷: 체크리스트형 | 신살/일간 연결: {sinsal}({SINSAL_TRAIT[sinsal]}) 또는 {dm} {gender} | 일상 장면: {detail['sit']}",
        )
    elif pillar == "viral_fakeout":
        pat = random.choice([
            f"겉은 다정한데 손절 제일 칼같은 사람 특징",
            f"연락 먼저 안 하는 {gender}가 오히려 연애 갑인 이유",
            f"참다가 한 번에 끝내는 사람들의 소름 돋는 사주",
        ])
        base.update(
            pattern=pat,
            detail=f"포맷: 페이크아웃(통념 반박)형 | 중반 사주 반전 근거: {dm} 일간과 {detail['ss']}({SIPSIN_TRAIT[detail['ss']]}) | 장면: {detail['sit']}",
        )
    elif pillar == "viral_pov":
        mbti = random.choice(MBTI_TYPES)
        pat = random.choice([
            f"{detail['sit']} 연락 없는 사람의 진짜 속마음",
            f"퇴근하고 집 오자마자 알림부터 끄는 사람의 심리",
            f"싸울 때 갑자기 입 닫아버리는 {mbti} 속마음",
        ])
        base.update(
            series="MBTI" if mbti in pat else "SAJU",
            mbti=mbti if mbti in pat else "",
            pattern=pat,
            detail=f"포맷: 일상/카톡 POV 속마음 해부형 | 상황: {detail['sit']} | 사주 근거: {dm} {gender} + {detail['habit']}",
        )
    elif pillar == "viral_mystery":
        pat = random.choice([
            f"대운 터지기 직전인 사람이 갑자기 끊는 것 3가지",
            f"올해 하반기 돈복 터질 사주에 나타나는 징조",
            f"인간관계 정리될 때 나타나는 소름 돋는 운세 신호",
        ])
        base.update(
            pattern=pat,
            detail=f"포맷: 떡밥·징조 미스터리형 | 핵심 반전: 앞으로 3년 운의 전환기 신호 + {dm} 기질 | 장면: {detail['sit']}",
        )
    elif pillar == "viral_balance":
        other_dm = _weighted_pick_dm([dm])
        pat = random.choice([
            f"나만 보는 {dm} 연인 vs 숨만 쉬어도 설레는 {other_dm}",
            f"혼자 일해야 대박 나는 사주 vs 팀으로 돈 버는 사주",
            f"칼답인데 무뚝뚝 vs 답장 느린데 다정, 내 사주 짝은?",
        ])
        base.update(
            pattern=pat,
            detail=f"포맷: A vs B 밸런스 비교형 | 비교 대상: {dm} vs {other_dm} | 상황: {detail['sit']}",
        )
    elif pillar == "couple_dm":
        a, b = dm, _weighted_pick_dm(recent)
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


def _fit_title(text: str, limit: int = 22) -> str:
    """한자 제거 및 MBTI 영문 정규화 후, 큰 글씨 2줄(최대 20~22자)에 최적화된 완성된 훅 문장으로 다듬는다."""
    from pipeline.text_utils import sanitize_title, normalize_mbti_to_english
    t = sanitize_title(text.replace("\n", " ").strip())
    t = normalize_mbti_to_english(t)
    if len(t) <= limit:
        return t

    # limit 초과 시 어절 경계에서 자르되, 끝이 불완전하게 끊어지지 않도록 보정
    cut = t[:limit]
    if " " in cut and t[limit] != " ":
        cut = cut[: cut.rfind(" ")]
    cut = cut.strip(" ,?!")

    # 불완전한 어미로 끝나면 자연스러운 종결형으로 보정
    if re.search(r"(벽치는|선긋는|손절하는|피하는|끌리는|헤어지는|놓치는|터지는|외로운)$", cut):
        cut += " 이유"
    elif re.search(r"(이래서|왜|진짜)$", cut):
        cut = re.sub(r"(이래서|왜|진짜)$", "", cut).strip(" ,?!")
        if cut and not cut.endswith("이유"):
            cut += " 이유"
    elif re.search(r"(알면|모르면)$", cut):
        cut += " 평생 후회"

    return cut


def _fallback_option(seed: Dict[str, str]) -> Dict[str, str]:
    pat = seed["pattern"]
    first = pat.split(",")[0].strip()
    title = _fit_title(first if len(first) <= 16 else re.sub(r"[?,]", "", pat))
    who = " ".join(x for x in (seed["dm"], seed["gender"]) if x) or seed["mbti"] or "나"
    return {
        "series": seed["series"], "mbti": seed["mbti"],
        "topic": f"{pat} ({seed.get('detail', '')})", "trend_hint": "",
        "title": title,
        "hook": f"솔직히 {first}, 이거 내 얘기다 싶으면 끝까지 보세요.",
        "summary": f"{pat} ({seed['pillar']} 포맷)",
    }


def get_planned_reels_proposals() -> Dict[str, Any]:
    """
    mbtiju.com 3대 하이브리드 축으로 서로 다른 2개 기획안(A/B)을 만든다:
    - Track A: [초타겟팅 핀셋형 40%] 출생연도/띠 + MBTI + 2030 현실 고민
    - Track B: [사주 심층 융합형 30%] 출생연도 + 사주 일간 + MBTI + 미래 예측
    - Track C: [시의성 랭킹/총운형 30%] 시기별 대박 사주xMBTI 조합 TOP 3
    """
    from pipeline.script_gen import generate_json

    recent = _recent_topics()
    seed_a = _seed_spec("MBTI", recent)
    seed_b = _seed_spec("MBTI" if random.random() < 0.6 else "SAJU", recent, exclude_dm=seed_a.get("dm", ""))
    for _ in range(5):
        if seed_b["pillar"] != seed_a["pillar"]:
            break
        seed_b = _seed_spec("MBTI", recent, exclude_dm=seed_a.get("dm", ""))

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
        return (f'{label}: 필라={s["pillar"]} | series={s["series"]}{extra} | 핵심 사주열쇠={s["dm"]} {s["gender"]}'
                f' | 훅 뼈대="{s["pattern"]}" | 구체화 재료: {s.get("detail", "")} | 작성 지침: {PILLAR_GUIDE[s["pillar"]]}')

    prompt = f"""{examples_block}

{recent_block}

[mbtiju.com 사주 분석 기반 MBTI 맞춤 조언 & 미래 예측 전략]
우리 서비스 mbtiju.com은 단순 성격 테스트가 아닌, 사주 원국과 대운을 깊이 분석하고 MBTI 성향과 결합하여 인생의 결정적 타이밍(연애·이직·결혼 등)에 제대로 된 조언과 예측을 제공합니다.
1. 초타겟팅 핀셋형: 출생연도/띠 + MBTI를 호명하여 '00년생 용띠 ESFJ 특징'처럼 직격 공감 유도.
2. 사주 심층 융합형: 출생연도 + 사주 일간 + MBTI를 융합하여 '98년생 임수 + INFP의 결혼운'처럼 겉성향 뒤 사주 기운 해부.
3. 시의성 랭킹형: '올해 남은 기간 제일 운 좋은 MBTI&사주 조합 TOP 3'처럼 바이럴 확산 극대화.

전개 구조(3단 입체 진단):
- (1) MBTI 겉행동 및 일상 고민 묘사 (공감 200%)
- (2) 사주 오행/일간/십성 에너지 근본 원인 분석 (mbtiju 핵심 전문성)
- (3) 앞으로의 시기별 운세 예측 및 구체적 실천 솔루션

아래 두 씨앗을 바탕으로 100만 뷰가 터질 수 있는 릴스 기획안 2개(A안, B안)로 다듬으세요.
{_desc("A안", seed_a)}
{_desc("B안", seed_b)}

[제목(title) 후킹 극대화 규칙 - 절대 엄수]
- 숏폼 피드(Reels/Shorts)에서 0.3초 만에 스크롤을 멈추게 하는 강력한 훅 제목을 작성하세요.
- 글자 수: 공백 포함 14~20자 내외 (화면에서 2줄로 시원하게 배치되는 길이).
- 어중간하게 끊기지 않는 '완성된 호기심 유발 문장'이어야 합니다. ('~이래서', '~벽치는' 처럼 말이 끊기면 절대 안 됨!)
- 클릭하지 않고는 못 배기는 4대 후킹 패턴 적극 활용:
  1) [반전/페이크아웃]: "겉은 다정한데 손절 제일 칼같은 이유", "착한 줄 알았는데 갑자기 선 긋는 이유"
  2) [결핍/고민 저격]: "00년생 용띠가 인간관계에 지치는 진짜 이유", "98년생 INFP, 연애할 때 고장 나는 이유"
  3) [시기/손실 회피]: "올해 하반기 이거 모르면 평생 엇갈린다", "2026년 대운 터지기 직전 나타나는 징조"
  4) [팩트/소름 주의]: "3개 이상 맞으면 사주에 도화살 낀 사람", "99%가 속는 내 사주의 진짜 본성"
- 한자 사용 절대 금지(순수 한글 표기만). MBTI는 반드시 영문 대문자(예: INFP, ESFJ).
- '오늘의 운세' 같은 일일 운세 금지. 후킹(hook)은 초반 2.5초 안에 끝나는 강렬한 한 문장.
- [디테일 규칙] topic에는 (1) 초반 3초 타겟 후킹 장면, (2) MBTI 겉행동 및 현실 고민 장면 2개, (3) 사주 명리학(일간·오행·십성) 원인 해부, (4) 운세 예측 및 솔루션을 구체적으로 요약해 적는다.
- [다양성 규칙] A안과 B안의 제목 어미와 포맷(특징형, 시기형, 비교형, 질문형)을 서로 완전히 다르게 쓴다.

JSON 포맷:
{{
  "option_a": {{"series": "{seed_a['series']}", "mbti": "{seed_a['mbti']}", "topic": "구체적 주제 및 사주 반전 설계", "title": "14~20자 완성된 훅 제목", "hook": "초반 2.5초 후킹 대사", "summary": "포맷 및 핵심 타겟 1줄 요약"}},
  "option_b": {{"series": "{seed_b['series']}", "mbti": "{seed_b['mbti']}", "topic": "구체적 주제 및 사주 반전 설계", "title": "14~20자 완성된 훅 제목", "hook": "초반 2.5초 후킹 대사", "summary": "포맷 및 핵심 타겟 1줄 요약"}}
}}
"""
    try:
        data = generate_json(None, prompt, temperature=0.85)
        if "option_a" in data and "option_b" in data:
            for key, seed in (("option_a", seed_a), ("option_b", seed_b)):
                opt = data[key]
                opt["series"], opt["mbti"] = seed["series"], seed["mbti"]
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
