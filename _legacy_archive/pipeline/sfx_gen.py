"""
Zero-Cost Procedural Sound Effect (SFX) Generator for Short-Form Retention.
외부 유료 효과음 라이브러리 없이 순수 Python 표준 라이브러리(wave, math, struct, random)만으로
숏폼 초반 3초 후킹 및 반전 포인트용 마이크로 효과음(.wav)을 생성합니다.
"""
import math
import random
import struct
import wave
from pathlib import Path
from typing import Dict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SFX_DIR = PROJECT_ROOT / "assets" / "sfx"


def _write_wav(path: Path, samples: list[float], sample_rate: int = 44100):
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for s in samples:
            clamped = max(-1.0, min(1.0, s))
            frames.extend(struct.pack("<h", int(clamped * 32767)))
        wf.writeframes(bytes(frames))


def ensure_default_sfx() -> Dict[str, Path]:
    """
    기본 3종 숏폼 효과음 파일이 없으면 자동 합성하여 assets/sfx/ 에 생성합니다.
    - hook_pop.wav   : 씬 1 시작 시점(0.05s)에 주의를 끄는 부드러운 서브베이스 팝
    - whoosh_soft.wav: 핵심 씬 전환 시 텐션을 살리는 짧은 스위시
    - ding_reveal.wav: 반전/결론 씬에서 포인트를 주는 맑은 벨 차임
    """
    SFX_DIR.mkdir(parents=True, exist_ok=True)
    sr = 44100

    pop_path = SFX_DIR / "hook_pop.wav"
    if not pop_path.is_file():
        dur = 0.14
        n = int(sr * dur)
        samples = []
        for i in range(n):
            t = i / sr
            # 160Hz -> 55Hz 피치 드롭 팝
            freq = 55.0 + 110.0 * math.exp(-t * 32.0)
            env = math.sin(math.pi * min(t / 0.012, 1.0)) * math.exp(-t * 22.0)
            samples.append(0.35 * env * math.sin(2.0 * math.pi * freq * t))
        _write_wav(pop_path, samples, sr)

    whoosh_path = SFX_DIR / "whoosh_soft.wav"
    if not whoosh_path.is_file():
        dur = 0.22
        n = int(sr * dur)
        rng = random.Random(42)
        samples = []
        prev = 0.0
        for i in range(n):
            t = i / sr
            env = math.sin(math.pi * (t / dur)) ** 2
            noise = rng.uniform(-1.0, 1.0)
            # 간단한 로우패스 필터링 노이즈 + 스윕 사인파
            filtered = 0.82 * prev + 0.18 * noise
            prev = filtered
            sweep = math.sin(2.0 * math.pi * (180.0 + 260.0 * (t / dur)) * t)
            samples.append(0.22 * env * (0.65 * filtered + 0.35 * sweep))
        _write_wav(whoosh_path, samples, sr)

    ding_path = SFX_DIR / "ding_reveal.wav"
    if not ding_path.is_file():
        dur = 0.45
        n = int(sr * dur)
        samples = []
        for i in range(n):
            t = i / sr
            env = math.exp(-t * 7.5)
            # 1046.5Hz (C6) + 1567.98Hz (G6) 배음 차임
            tone = 0.7 * math.sin(2.0 * math.pi * 1046.5 * t) + 0.3 * math.sin(2.0 * math.pi * 1568.0 * t)
            samples.append(0.24 * env * tone)
        _write_wav(ding_path, samples, sr)

    return {
        "hook_pop": pop_path,
        "whoosh_soft": whoosh_path,
        "ding_reveal": ding_path,
    }


if __name__ == "__main__":
    paths = ensure_default_sfx()
    for k, p in paths.items():
        print(f"[SFX] {k}: {p} ({p.stat().st_size} bytes)")

