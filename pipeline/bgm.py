"""
BGM 선택 모듈.

음원은 `assets/bgm/<mood>/*.mp3` 에 직접 넣어 둡니다 (Pixabay Music 등 상업 이용 가능한 무료 음원).
시리즈별 분위기 폴더를 우선 사용하고, 없으면 `assets/bgm/` 루트/`default/`에서 고릅니다.
음원이 하나도 없으면 None을 반환하며 BGM 없이 영상이 만들어집니다.
"""
import hashlib
import random
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BGM_DIR = PROJECT_ROOT / "assets" / "bgm"
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".ogg"}

# series -> 분위기 폴더
SERIES_MOOD = {
    "MBTI": "bright",
    "DAILY": "calm",
    "ELEMENT": "calm",
    "SAJU": "mystic",
    "SHINJEOM": "mystic",
    "JAMIDOSU": "mystic",
    "TAROT": "mystic",
}
MOODS = ("bright", "calm", "mystic", "default")


def _tracks(folder: Path):
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in AUDIO_EXTS)


def pick_bgm(series: str = "", seed: Optional[str] = None) -> Optional[Path]:
    """시리즈 분위기에 맞는 트랙을 고릅니다. seed를 주면 같은 입력에 같은 트랙(재현성)."""
    mood = SERIES_MOOD.get(series, "default")
    candidates = _tracks(BGM_DIR / mood) or _tracks(BGM_DIR / "default") or _tracks(BGM_DIR)
    if not candidates:
        # 분위기 폴더가 하나라도 채워져 있으면 그중 아무거나
        for m in MOODS:
            candidates = _tracks(BGM_DIR / m)
            if candidates:
                break
    if not candidates:
        return None
    if seed:
        idx = int(hashlib.md5(seed.encode("utf-8")).hexdigest(), 16) % len(candidates)
        return candidates[idx]
    return random.choice(candidates)
