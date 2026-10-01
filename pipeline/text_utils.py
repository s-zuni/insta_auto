"""
나레이션/자막 텍스트 가공 유틸리티.
- 한자(漢字) 제거: TTS 엔진이 한글과 한자를 중복 발음하는 문제 방지
  (예: "토(土)사주" -> 음성 "토토 사주" 로 겹쳐 읽히는 현상)
- 픽셀 폭 기반 줄바꿈: 글자 수가 아닌 실제 렌더 폭 기준으로 자연스럽게 줄바꿈
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

# 문장부호/구어체 어미 뒤에서 자연스럽게 끊어 자막/음성 호흡 단위를 만들기 위한 경계
_CLAUSE_BOUNDARY_RE = re.compile(
    r"(?<=[.!?,])\s+"          # 마침표/느낌표/물음표/쉼표 뒤
    r"|(?<=요)\s+(?=[가-힣])"   # '~해요' 뒤 다음 어절
    r"|(?<=죠)\s+(?=[가-힣])"   # '~하죠' 뒤 다음 어절
    r"|(?<=다)\s+(?=[가-힣])"   # '~합니다/했다' 뒤 다음 어절
)


def sanitize_narration(text: str) -> str:
    """TTS가 한글과 한자를 중복 발음하지 않도록 나레이션에서 한자를 제거합니다."""
    if not text:
        return text
    cleaned = _HANJA_PAREN_RE.sub("", text)
    cleaned = _HANJA_RE.sub("", cleaned)
    cleaned = _MULTI_SPACE_RE.sub(" ", cleaned)
    return cleaned.strip()


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
    """주어진 폰트/크기 기준 실측 픽셀 폭에 맞춰 텍스트를 여러 줄로 래핑합니다."""
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
    return lines


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
                tokens.append("{\\kf" + str(cs) + "}" + w)
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
        chunks.append((cursor, c_end, block))
        cursor = c_end
    return chunks
