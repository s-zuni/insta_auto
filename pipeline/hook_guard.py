"""
훅/제목 '전문 용어 금지' 가드.

[왜 필요한가 - ig-audit 실측, 릴스 5개, 표본 작음]
- 일간·신살·줄임말이 제목에 들어간 게시물: 119 / 130 / 189회 (도화살, 겉착속칼, INFJ)
- 같은 소재를 용어 없이 쓴 "착한 사람의 소름돋는 이중성": 1,510회 (조회 중앙값 대비 9.5배)
용어는 본문 씬 4~6에서 "사실 이게 ○○인데"로 푼다. 화면 제목, 스토리 훅(씬 1 나레이션), 기획 훅에서만 막는다.

규칙
- 막는 것: 일간 10종, 신살, 십성(상관 제외), 대운/원국 등 명리 용어, 자미두수 용어, 이미 쓴 줄임말('겉착속칼').
- 안 막는 것: '사주', 'MBTI'(기본), 출생연도/띠, 타로. MBTI까지 막으려면 HOOK_BAN_MBTI=true.
  (MBTI는 표본이 적어 용어 효과와 분리되지 않았고 서비스 정체성이라 기본은 허용)
- 출생연도/띠 호명("99년생 토끼띠 ...")은 기본 허용, 막으려면 HOOK_BAN_BIRTHYEAR=true.
- 끄려면 ALLOW_JARGON_HOOKS=true.
- '상관'은 '상관없다'와 겹치고 '정인/정관'은 이름·일상어와 겹칠 수 있어 정인만 포함, 상관은 제외.
"""
import os
import random
import re
from typing import Callable, Dict, List, Optional, Tuple

JARGON_TERMS: Tuple[str, ...] = (
    # 일간 10종 + 명리 기본 용어
    "갑목", "을목", "병화", "정화", "무토", "기토", "경금", "신금", "임수", "계수",
    "일간", "천간", "지지", "원국", "대운", "신살", "십성", "오행",
    # 신살
    "도화살", "홍염살", "역마살", "화개살", "백호살", "귀문관살", "원진살", "양인살", "괴강살", "공망",
    # 십성 (상관은 일상어와 겹쳐 제외)
    "식신", "편재", "정재", "편관", "정관", "편인", "정인", "비견", "겁재",
    # 자미두수 용어
    "자미두수", "명궁", "재백궁",
    # 기존에 쓴 줄임말
    "겉착속칼",
)

_MBTI_RE = re.compile(r"(?<![A-Za-z])[IE][NS][TF][JP](?![A-Za-z])")
_BIRTHYEAR_RE = re.compile(
    r"\d{2}년생|(?:쥐|소|호랑이|범|토끼|용|뱀|말|양|원숭이|닭|개|돼지)띠")

# 용어 없이도 이긴 공식("다 퍼주는 사람이 ..." 계열)에서 가져온 최후 대체안 (제목, 훅)
PLAIN_FALLBACKS: List[Tuple[str, str]] = [
    ("다 퍼주는 사람이 먼저 연락 끊는 이유", "다 퍼주는 사람이 제일 먼저 연락 끊는 진짜 이유."),
    ("착한 사람이 손절할 땐 말이 없는 이유", "착한 사람이 손절할 땐 왜 아무 말도 안 할까?"),
    ("화 안 내는 사람이 제일 무서운 이유", "화 안 내는 사람이 제일 무서운 이유, 알려줄게."),
    ("읽고 답 안 하는 사람의 진짜 속마음", "읽고도 답장 안 하는 사람, 속마음은 이래요."),
    ("썸 타는데 답장이 늦을 때 속마음", "썸 타는데 답장이 늦다면, 30초만 보세요."),
]


def allow_jargon() -> bool:
    return os.getenv("ALLOW_JARGON_HOOKS", "").strip().lower() in ("1", "true", "yes")


def ban_mbti() -> bool:
    return os.getenv("HOOK_BAN_MBTI", "").strip().lower() in ("1", "true", "yes")


def ban_birthyear() -> bool:
    return os.getenv("HOOK_BAN_BIRTHYEAR", "").strip().lower() in ("1", "true", "yes")


def find_jargon(text: str) -> List[str]:
    """text에 들어 있는 금지 용어 목록(없으면 빈 리스트). ALLOW_JARGON_HOOKS면 항상 빈 리스트."""
    if not text or allow_jargon():
        return []
    found = [t for t in JARGON_TERMS if t in text]
    if ban_mbti():
        found += _MBTI_RE.findall(text)
    if ban_birthyear():
        found += _BIRTHYEAR_RE.findall(text)
    return found


def plain_fallback() -> Tuple[str, str]:
    return random.choice(PLAIN_FALLBACKS)


def _default_llm(prompt: str) -> Dict[str, str]:
    from pipeline.script_gen import generate_json
    return generate_json(None, prompt, temperature=0.7)


def enforce_plain(fields: Dict[str, str], context: str = "",
                  llm: Optional[Callable[[str], Dict[str, str]]] = None) -> Tuple[Dict[str, str], List[str]]:
    """fields(예: title/hook/scene1)에서 용어가 있는 항목만 LLM으로 한 번 다시 쓴다.
    반환: (정리된 fields, 여전히 용어가 남은 키 목록). 호출자가 남은 키는 대체안으로 처리한다.
    LLM 호출이 실패해도 예외를 던지지 않는다(기획/대본 생성을 막지 않기 위해)."""
    bad = {k: find_jargon(v) for k, v in fields.items() if v}
    bad = {k: v for k, v in bad.items() if v}
    if not bad:
        return fields, []
    out = dict(fields)
    terms = sorted({t for v in bad.values() for t in v})
    shown = {k: fields[k] for k in bad}
    prompt = (
        f"아래 릴스 문장에서 사주 전문 용어({', '.join(terms)})를 모두 빼고, 같은 뜻을 누구나 바로 이해하는 쉬운 일상어로 다시 쓰세요.\n"
        "- 누구나 대입되는 구체적인 장면이나 행동 하나로 시작하고, 결론은 숨겨 궁금하게 만드세요.\n"
        "- 일간/신살/십성/대운 같은 용어는 쓰지 말고 한자도 쓰지 마세요.\n"
        "- title은 공백 포함 14~20자의 완성된 문장, hook과 scene1은 한 문장 구어체.\n"
        f"- 영상 맥락: {context[:200]}\n"
        f"- 다시 쓸 문장(JSON): {shown}\n"
        "같은 키만 가진 JSON으로만 답하세요."
    )
    try:
        data = (llm or _default_llm)(prompt)
        for k in bad:
            cand = str((data or {}).get(k, "")).strip()
            if cand and not find_jargon(cand):
                out[k] = cand
    except Exception as e:
        print(f"[HOOK_GUARD][WARN] 용어 제거 재작성 실패(대체안 사용): {e}")
    remaining = [k for k in bad if find_jargon(out[k])]
    return out, remaining
