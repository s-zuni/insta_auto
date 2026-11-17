"""이미지 + 음성 + 자막 → FFmpeg 숏폼(1080x1920 MP4) 렌더링 엔진.

장면별 세그먼트를 만든 뒤 concat. 배경 이미지가 없으면 장면별 그라데이션 톤 컬러를 사용.
Windows 경로 이스케이프 문제를 피하려고 ffmpeg 를 작업 폴더에서 상대경로로 실행한다.
"""
from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path

from ..core.config import settings
from ..core.schemas import ShortsContent
from .tts_subtitle import build_cues, synthesize, write_ass

PALETTE = ["0x1f2a44", "0x3a1f44", "0x14463a", "0x44301f", "0x1f3f44", "0x441f2f"]


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _run(cmd: list[str], cwd: Path) -> None:
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg 실패: {' '.join(cmd[:6])} ...\n{r.stderr[-800:]}")


async def render(shorts: ShortsContent, job_dir: Path) -> tuple[Path, float]:
    """반환: (mp4 경로, 총 길이 초)"""
    if not ffmpeg_available():
        raise RuntimeError("FFmpeg/FFprobe 를 찾을 수 없습니다. PATH 에 설치해 주세요.")
    job_dir.mkdir(parents=True, exist_ok=True)
    fonts_dir = settings.assets_dir / "fonts"
    segs: list[Path] = []
    total = 0.0

    for i, scene in enumerate(shorts.scenes):
        audio = job_dir / f"s{i}.mp3"
        dur = await synthesize(scene.narration, audio) + 0.35
        write_ass(build_cues(scene.narration, dur - 0.35), scene.on_screen_text, dur, job_dir / f"s{i}.ass")
        seg = job_dir / f"seg{i}.mp4"
        vf = f"ass=s{i}.ass:fontsdir=fonts"
        # 폰트 폴더를 작업 폴더 안으로 복사해 상대경로 사용 (Windows 경로 이스케이프 회피)
        local_fonts = job_dir / "fonts"
        if not local_fonts.exists():
            shutil.copytree(fonts_dir, local_fonts)
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "lavfi", "-i", f"color=c={PALETTE[i % len(PALETTE)]}:s=1080x1920:r=30:d={dur:.2f}",
            "-i", audio.name,
            "-vf", vf, "-t", f"{dur:.2f}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "44100", "-shortest",
            seg.name,
        ]
        await asyncio.to_thread(_run, cmd, job_dir)
        segs.append(seg)
        total += dur

    (job_dir / "concat.txt").write_text("".join(f"file '{s.name}'\n" for s in segs), encoding="utf-8")
    out = job_dir / "shorts.mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", "concat.txt",
           "-c", "copy", out.name]
    await asyncio.to_thread(_run, cmd, job_dir)
    return out, total
