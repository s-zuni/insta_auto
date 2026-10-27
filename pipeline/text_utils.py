"""
나레이션/자막 텍스트 가공 유틸리티.
- 한자(漢字) 제거: TTS 엔진이 한글과 한자를 중복 발음하는 문제 방지
  (예: "토(土)사주" -> 음성 "토토 사주" 로 겹쳐 읽히는 현상)
- MBTI 영문 표준화: 한글 음차(인프피, 엠비티아이) -> 표준 영문 대문자(INFP, MBTI)
- 픽셀 폭 기반 자연스러운 줄바꿈: 구분 기호 인식 + 시각적 폭 균형(외톨이 단어 방지)
"""
import re
from typing import List, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from PIL import ImageFont

# "(土)" 처럼 괄호로 감싼 한자 구간을 통째로 제거
_HANJA_PAREN_RE = re.compile(r"[\(（]\s*[㐀-䶿一-鿿]+\s*[\)）]")
# 괄호 밖에 홀로 남은 한자도 제거
_HANJA_RE = re.compile(r"[㐀-䶿一-鿿]")
_MULTI_SPACE_RE = re.compile(r"\s{2,}")

# MBTI 한글 음차 표기 -> 표준 영문 대문자 매핑 사전
MBTI_KOREAN_MAP = {
    "엠비티아이": "MBTI",
    # 16가지 축약형
    "인프피": "INFP",
    "인팁": "INTP",
    "인티제": "INTJ",
    "인프제": "INFJ",
    "엔프피": "ENFP",
    "엔팁": "ENTP",
    "엔티제": "ENTJ",
    "엔프제": "ENFJ",
    "잇프피": "ISFP",
    "잇팁": "ISTP",
    "잇티제": "ISTJ",
    "잇프제": "ISFJ",
    "엣프피": "ESFP",
    "엣팁": "ESTP",
    "엣티제": "ESTJ",
    "엣프제": "ESFJ",
    # 음절별 발음 표기
    "아이엔에프피": "INFP",
    "아이엔티피": "INTP",
    "아이엔티제이": "INTJ",
    "아이엔티제": "INTJ",
    "아이엔프제이": "INFJ",
    "아이엔프제": "INFJ",
    "이엔에프피": "ENFP",
    "이엔티피": "ENTP",
    "이엔티제이": "ENTJ",
    "이엔티제": "ENTJ",
    "이엔프제이": "ENFJ",
    "이엔프제": "ENFJ",
    "아이에스티제이": "ISTJ",
    "아이에스에프제이": "ISFJ",
    "이에스티제이": "ESTJ",
    "이에스에프제이": "ESFJ",
    "아이에스티피": "ISTP",
    "아이에스에프피": "ISFP",
    "이에스티피": "ESTP",
    "이에스에프피": "ESFP",
}

_MBTI_KOR_PATTERN = re.compile("|".join(re.escape(k) for k in sorted(MBTI_KOREAN_MAP.keys(), key=len, reverse=True)))
_MBTI_ENG_PATTERN = re.compile(
    r"(?i)(?<![a-zA-Z0-9])(INTJ|INTP|ENTJ|ENTP|INFJ|INFP|ENFJ|ENFP|ISTJ|ISFJ|ESTJ|ESFJ|ISTP|ISFP|ESTP|ESFP|MBTI)(?![a-zA-Z0-9])"
)


def normalize_mbti_to_english(text: str) -> str:
    """
    한글로 작성된 MBTI 용어(예: '인프피', '엠비티아이', '엔티제') 및 소문자/혼용 MBTI 영문을
    표준 영문 대문자(INFP, MBTI, ENTJ 등)로 일괄 변환합니다.
    """
    if not text:
        return text
    # 1. 한글 음차 표기 변환
    res = _MBTI_KOR_PATTERN.sub(lambda m: MBTI_KOREAN_MAP[m.group(0)], text)
    # 2. 영문 소문자/혼용 표기 대문자화
    res = _MBTI_ENG_PATTERN.sub(lambda m: m.group(0).upper(), res)
    return res


# 문장부호/구어체 어미/연결 어미 뒤에서 자연스럽게 끊어 자막/음성 호흡 단위를 만들기 위한 경계
_CLAUSE_BOUNDARY_RE = re.compile(
    r"(?<=[.!?,])\s+"          # 마침표/느낌표/물음표/쉼표 뒤
    r"|(?<=요)\s+(?=[가-힣])"   # '~해요' 뒤 다음 어절
    r"|(?<=죠)\s+(?=[가-힣])"   # '~하죠' 뒤 다음 어절
    r"|(?<=다)\s+(?=[가-힣])"   # '~합니다/했다' 뒤 다음 어절
    r"|(?<=는데)\s+(?=[가-힣])" # '~보이는데' 뒤 다음 어절
    r"|(?<=지만)\s+(?=[가-힣])" # '~하지만' 뒤 다음 어절
    r"|(?<=거든)\s+(?=[가-힣])" # '~하거든/거든요' 뒤 다음 어절
    r"|(?<=니까)\s+(?=[가-힣])" # '~하니까' 뒤 다음 어절
    r"|(?<=으면)\s+(?=[가-힣])" # '~있으면' 뒤 다음 어절
    r"|(?<=[가-힣]면)\s+(?=[가-힣])" # '~하면/되면' 뒤 다음 어절
    r"|(?<=아서)\s+(?=[가-힣])" # '~좋아서' 뒤 다음 어절
    r"|(?<=어서)\s+(?=[가-힣])" # '~강해서' 뒤 다음 어절
    r"|(?<=하고)\s+(?=[가-힣])" # '~하고' 뒤 다음 어절
)


def sanitize_narration(text: str) -> str:
    """TTS가 한글과 한자를 중복 발음하지 않도록 나레이션에서 한자를 제거하고,
    MBTI 용어를 표준 영문 대문자로 변환합니다."""
    if not text:
        return text
    cleaned = _HANJA_PAREN_RE.sub("", text)
    cleaned = _HANJA_RE.sub("", cleaned)
    cleaned = _MULTI_SPACE_RE.sub(" ", cleaned)
    cleaned = normalize_mbti_to_english(cleaned)
    return cleaned.strip()


def sanitize_title(text: str) -> str:
    """화면 표시용 제목/헤드라인에서 한자를 제거하고 MBTI를 표준 영문 대문자로 변환합니다.
    Pretendard에는 한자 글리프가 없어 두부(□)로 깨지므로 '을목(乙木)' -> '을목' 처럼 한글만 남깁니다."""
    if not text:
        return text
    return sanitize_narration(text).replace("( )", "").replace("()", "").strip()


def split_into_clauses(text: str) -> List[str]:
    """문장부호/어미를 기준으로 나레이션을 자연스러운 구(clause) 단위로 분할합니다."""
    text = text.strip()
    if not text:
        return []
    parts = [p.strip() for p in _CLAUSE_BOUNDARY_RE.split(text) if p and p.strip()]
    if not parts:
        return [text]

    # 너무 짧은 조각(6자 미만)은 앞 조각에 합쳐 캡션이 지나치게 잘게 쪼개지는 것을 방지
    merged: List[str] = []
    for part in parts:
        if merged and len(part) < 6:
            merged[-1] = f"{merged[-1]} {part}"
        else:
            merged.append(part)
    return merged


def wrap_by_pixel_width(text: str, font: "ImageFont.FreeTypeFont", max_width: int) -> List[str]:
    """주어진 폰트/크기 기준 실측 픽셀 폭에 맞춰 텍스트를 여러 줄로 래핑하며,
    마지막 줄에 단어가 1개만 덜렁 남는 외톨이 단어(Orphan word) 현상을 방지하도록 균형을 맞춥니다."""
    words = text.split()
    if not words:
        return []
    lines: List[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if font.getlength(candidate) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)

    # 외톨이 단어(Orphan word) 방지: 마지막 줄 단어가 1개이고 바로 앞 줄 단어가 3개 이상이면 앞 줄 마지막 단어를 넘김
    for i in range(len(lines) - 1, 0, -1):
        cur_words = lines[i].split()
        prev_words = lines[i - 1].split()
        if len(cur_words) == 1 and len(prev_words) >= 3:
            cand_cur = f"{prev_words[-1]} {lines[i]}"
            if font.getlength(cand_cur) <= max_width:
                lines[i - 1] = " ".join(prev_words[:-1])
                lines[i] = cand_cur

    return lines


def wrap_natural_title(
    title: str,
    font: "ImageFont.FreeTypeFont",
    max_width: int,
    max_lines: int = 2
) -> List[str]:
    """
    릴스/숏츠 상단 타이틀 및 썸네일 커버용 고품질 줄바꿈 함수.
    1. 자연스러운 의미 경계(쉼표, 물음표, 콜론, '+', 'vs' 등) 분할을 최우선 시도.
    2. 모든 가능한 2분할 지점 중 두 줄의 실측 픽셀 폭 차이(|W1 - W2|)를 최소화하는 균형 분할 적용.
    3. 1단어만 다음 줄로 떨어져 나가는 외톨이 단어(Orphan word) 원천 차단.
    """
    clean = title.replace("\r", "").replace("\n", " ").strip()
    clean = normalize_mbti_to_english(clean)
    words = clean.split()
    if not words:
        return []
    if len(words) <= 2:
        return [clean]

    # 1. 의미적 구분 기호(쉼표, 물음표, 느낌표, 콜론, '+', 'vs' 등) 기준 분할
    delimiters = [", ", "? ", "! ", ": ", " + ", " x ", " X ", " vs ", " VS "]
    for delim in delimiters:
        if delim in clean:
            idx = clean.find(delim)
            part1 = clean[:idx + len(delim.rstrip())].strip()
            part2 = clean[idx + len(delim):].strip()
            if part1 and part2:
                w1 = font.getlength(part1)
                w2 = font.getlength(part2)
                if w1 <= max_width and w2 <= max_width:
                    return [part1, part2]

    # 2. 픽셀 너비 균형 분할 (Minimizing |W1 - W2|)
    best_split = None
    min_diff = float("inf")
    for i in range(1, len(words)):
        p1 = " ".join(words[:i])
        p2 = " ".join(words[i:])
        w1 = font.getlength(p1)
        w2 = font.getlength(p2)
        if w1 <= max_width and w2 <= max_width:
            penalty = 0
            # 뒤 줄에 단어가 1개만 남는데 전체 단어가 4개 이상이면 페널티
            if len(p2.split()) == 1 and len(words) >= 4:
                penalty = 350
            diff = abs(w1 - w2) + penalty
            if diff < min_diff:
                min_diff = diff
                best_split = [p1, p2]

    if best_split:
        return best_split

    # 3. 폴백: 균형 래핑
    lines = wrap_by_pixel_width(clean, font, max_width)
    return lines[:max_lines]


_PUNCT_RE = re.compile(r"[^\w가-힣]", re.UNICODE)


def _norm(token: str) -> str:
    return _PUNCT_RE.sub("", token)


def align_word_times(
    words: List[str],
    word_timings: list,
    scene_start: float,
    scene_end: float,
) -> List[Tuple[float, float]]:
    """
    나레이션 어절(words)마다 (start, end) 시각을 돌려줍니다.
    word_timings(TTS 단어 경계)와 어절이 1:1이 아니어도(예: edge-tts가 어절을 다르게 쪼갬)
    글자 누적 위치로 대응시키고, 대응이 안 되면 씬 구간을 글자 수 비례로 나눕니다.
    word_timings 항목은 .word/.start_time/.end_time 속성 또는 dict 키를 가진 객체여야 합니다.
    """
    def g(o, k):
        return getattr(o, k) if hasattr(o, k) else o[k]

    n = len(words)
    if n == 0:
        return []

    def proportional() -> List[Tuple[float, float]]:
        weights = [max(len(_norm(w)), 1) for w in words]
        total = sum(weights)
        out, cur = [], scene_start
        for w in weights:
            nxt = cur + (scene_end - scene_start) * w / total
            out.append((cur, nxt))
            cur = nxt
        return out

    if not word_timings:
        return proportional()

    timings = [(_norm(str(g(t, "word"))), float(g(t, "start_time")), float(g(t, "end_time"))) for t in word_timings]
    timings = [t for t in timings if t[0]]
    t_chars = sum(len(t[0]) for t in timings)
    w_chars = sum(len(_norm(w)) for w in words)
    if not timings or t_chars == 0 or abs(t_chars - w_chars) > max(3, 0.1 * w_chars):
        return proportional()

    # 글자 누적 위치 -> 해당 글자가 속한 TTS 단어 인덱스
    char_to_timing: List[int] = []
    for ti, t in enumerate(timings):
        char_to_timing += [ti] * len(t[0])

    result: List[Tuple[float, float]] = []
    pos = 0
    for w in words:
        ln = len(_norm(w))
        if ln == 0:
            prev_end = result[-1][1] if result else scene_start
            result.append((prev_end, prev_end))
            continue
        first = char_to_timing[min(pos, len(char_to_timing) - 1)]
        last = char_to_timing[min(pos + ln - 1, len(char_to_timing) - 1)]
        result.append((timings[first][1], timings[last][2]))
        pos += ln

    # 시작 시각이 역행하지 않도록 정리
    fixed: List[Tuple[float, float]] = []
    for s, e in result:
        if fixed and s < fixed[-1][0]:
            s = fixed[-1][0]
        fixed.append((s, max(e, s)))
    return fixed


HIGHLIGHT_KEYWORDS = {
    "1위", "2위", "3위", "대박", "조심", "소름", "대운", "운세", "궁합", "후회", "비밀", "특징", "팩트", "MBTI",
    "INTJ", "INTP", "ENTJ", "ENTP", "INFJ", "INFP", "ENFJ", "ENFP",
    "ISTJ", "ISFJ", "ESTJ", "ESFJ", "ISTP", "ISFP", "ESTP", "ESFP"
}


def _colorize_token(word: str, kf_prefix: str = "") -> str:
    """핵심 키워드(MBTI, 순위, 자극적 단어)에 골드/옐로우 컬러 코드를 부여합니다."""
    clean_w = re.sub(r"[^\w가-힣A-Za-z]", "", word).upper()
    is_highlight = any(kw in clean_w for kw in HIGHLIGHT_KEYWORDS)
    if is_highlight:
        # 노란색(&H002BF7FF&) 액센트 부여 후 원래 흰색(&H00FFFFFF&)으로 복귀
        return f"{kf_prefix}{{\\c&H002BF7FF&}}{word}{{\\c&H00FFFFFF&}}"
    return f"{kf_prefix}{word}"


def build_karaoke_blocks(
    narration: str,
    word_timings: list,
    scene_start: float,
    scene_end: float,
    font: "ImageFont.FreeTypeFont",
    max_width: int,
    max_lines: int = 2,
    time_shift: float = 0.0,
) -> List[Tuple[float, float, str]]:
    """
    단어 단위 하이라이트(ASS \\kf)가 들어간 자막 블록 (start, end, text)들을 만듭니다.
    블록 분할은 build_caption_chunks와 동일(문장부호/어미 기준 구 + 실측 픽셀 폭 줄바꿈, 최대 2줄).
    time_shift는 씬 전환 겹침 보정용(초)으로, 모든 시각에서 차감됩니다.
    """
    words_all = narration.split()
    times = align_word_times(words_all, word_timings, scene_start, scene_end)
    if not words_all:
        return []

    # 블록 -> (줄 리스트, 어절 인덱스 범위)
    blocks: List[List[List[str]]] = []
    for clause in split_into_clauses(narration):
        wrapped = wrap_by_pixel_width(clause, font, max_width)
        for i in range(0, len(wrapped), max_lines):
            blocks.append([line.split() for line in wrapped[i:i + max_lines]])

    out: List[Tuple[float, float, str]] = []
    wi = 0
    for bi, lines in enumerate(blocks):
        block_words = sum(len(l) for l in lines)
        if block_words == 0:
            continue
        idxs = list(range(wi, wi + block_words))
        wi += block_words

        b_start = times[idxs[0]][0]
        next_start = times[wi][0] if wi < len(times) else scene_end
        b_end = max(next_start, times[idxs[-1]][1])

        parts: List[str] = []
        k = 0
        for li, line in enumerate(lines):
            tokens = []
            for w in line:
                s = times[idxs[k]][0]
                nxt = times[idxs[k + 1]][0] if k + 1 < len(idxs) else b_end
                cs = max(int(round((nxt - s) * 100)), 1)
                tokens.append(_colorize_token(w, f"{{\\kf{cs}}}"))
                k += 1
            parts.append(" ".join(tokens))
        out.append((max(b_start - time_shift, 0.0), max(b_end - time_shift, 0.0), "\\N".join(parts)))

    # 블록이 겹치거나 비는 부분 정리: 각 블록은 다음 블록 시작까지 유지
    for i in range(len(out) - 1):
        s, e, t = out[i]
        out[i] = (s, max(min(e, out[i + 1][0]), s + 0.05), t)
    return out


def build_caption_chunks(
    narration: str,
    start_time: float,
    end_time: float,
    font: "ImageFont.FreeTypeFont",
    max_width: int,
    max_lines: int = 2,
) -> List[Tuple[float, float, str]]:
    """
    나레이션을 자연스러운 구 단위로 자막 블록(최대 max_lines줄)들로 나누고,
    각 블록 재생 구간을 글자 수 비례로 배분합니다. (ASS 줄바꿈은 '\\N' 사용)
    """
    duration = max(end_time - start_time, 0.01)
    clauses = split_into_clauses(narration)
    if not clauses:
        return [(start_time, end_time, narration)]

    blocks: List[str] = []
    for clause in clauses:
        wrapped = wrap_by_pixel_width(clause, font, max_width)
        for i in range(0, len(wrapped), max_lines):
            group = wrapped[i:i + max_lines]
            blocks.append("\\N".join(group))

    if not blocks:
        return [(start_time, end_time, narration)]

    weights = [max(len(b.replace("\\N", "")), 1) for b in blocks]
    total_weight = sum(weights)

    chunks: List[Tuple[float, float, str]] = []
    cursor = start_time
    for idx, (block, w) in enumerate(zip(blocks, weights)):
        if idx == len(blocks) - 1:
            c_end = end_time
        else:
            c_end = cursor + duration * (w / total_weight)

        # 각 줄별 단어 단위로 하이라이트 색상 적용
        colored_lines = []
        for line in block.split("\\N"):
            words = line.split()
            colored_lines.append(" ".join(_colorize_token(wd) for wd in words))
        c_text = "\\N".join(colored_lines)

        chunks.append((cursor, c_end, c_text))
        cursor = c_end
    return chunks
