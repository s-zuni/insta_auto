"""TTS 음성 합성(edge-tts) 및 타임스탬프 자막 생성.

장면 단위로 합성 → ffprobe 로 길이 측정 → 글자 수 비례로 자막 큐 분배 (엔진 이벤트에 의존하지 않아 견고).
"""
from __future__ import annotations

import asyncio
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..core.config import settings


@dataclass
class Cue:
    start: float
    end: float
    text: str


def probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    return float(json.loads(out)["format"]["duration"])


async def synthesize(text: str, out_path: Path, voice: str | None = None) -> float:
    """text → mp3. 반환: 길이(초)."""
    import edge_tts

    out_path.parent.mkdir(parents=True, exist_ok=True)
    await edge_tts.Communicate(text, voice or settings.tts_voice).save(str(out_path))
    return await asyncio.to_thread(probe_duration, out_path)


def split_chunks(text: str, max_chars: int = 14) -> list[str]:
    """공백 기준으로 자막 한 줄이 max_chars 를 넘지 않게 분할."""
    chunks: list[str] = []
    cur = ""
    for word in text.split():
        if cur and len(cur) + 1 + len(word) > max_chars:
            chunks.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    if cur:
        chunks.append(cur)
    return chunks or [text]


def build_cues(text: str, duration: float, offset: float = 0.0) -> list[Cue]:
    chunks = split_chunks(text)
    total = sum(len(c) for c in chunks) or 1
    cues, t = [], offset
    for c in chunks:
        d = duration * len(c) / total
        cues.append(Cue(round(t, 3), round(t + d, 3), c))
        t += d
    return cues


def _ass_time(sec: float) -> str:
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def write_ass(cues: list[Cue], title: str, duration: float, path: Path, font: str = "Pretendard") -> None:
    """1080x1920 기준 ASS. 상단 큰 제목(Title) + 하단 자막(Sub)."""
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,OutlineColour,BackColour,Bold,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV
Style: Sub,{font},64,&H00FFFFFF,&H00000000,&H80000000,1,1,5,1,2,60,60,420
Style: Title,{font},84,&H0000E0FF,&H00000000,&H80000000,1,1,6,1,8,60,60,260

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    lines = []
    if title:
        lines.append(f"Dialogue: 0,{_ass_time(0)},{_ass_time(duration)},Title,,0,0,0,,{title}")
    for c in cues:
        lines.append(f"Dialogue: 1,{_ass_time(c.start)},{_ass_time(c.end)},Sub,,0,0,0,,{c.text}")
    path.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")
