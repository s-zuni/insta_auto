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
