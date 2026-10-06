"""
BGM 선택 모듈.

음원은 로컬 `assets/bgm/<mood>/*.mp3` 또는 Google Drive의 BGM 폴더(GDRIVE_BGM_FOLDER_ID)에서
가져옵니다.
1. 해당 시리즈 무드(bright, calm, mystic, default)의 로컬 캐시 확인 -> 있으면 즉시 사용
2. 로컬에 없으면 Google Drive의 해당 무드 폴더에서 조회 후 로컬로 자동 다운로드 (캐싱)
3. 구글 드라이브에도 해당 무드가 없으면 default 무드 -> 전체 무드 순으로 대체
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


def _local_tracks(folder: Path):
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in AUDIO_EXTS)


def pick_bgm(series: str = "", seed: Optional[str] = None) -> Optional[Path]:
    """
    시리즈 분위기에 맞는 BGM 트랙을 고릅니다.
    로컬 음원이 없으면 Google Drive BGM 폴더에서 실시간으로 조회하여 다운로드 후 사용합니다.
    seed를 주면 같은 입력에 같은 트랙을 재현성 있게 선택합니다.
    """
    mood = SERIES_MOOD.get(series, "default")

    # 1. 해당 무드의 로컬 캐시 확인
    local_candidates = _local_tracks(BGM_DIR / mood)
    if local_candidates:
        if seed:
            idx = int(hashlib.md5(seed.encode("utf-8")).hexdigest(), 16) % len(local_candidates)
            return local_candidates[idx]
        return random.choice(local_candidates)

    # 2. 해당 무드가 로컬에 없으면 Google Drive의 해당 무드 폴더에서 조회 및 다운로드
    try:
        from pipeline.gdrive_uploader import get_gdrive_bgm_tracks, download_drive_file_to_temp

        print(f"  [BGM] Google Drive BGM 폴더에서 '{mood}' 무드 음원 조회 중...")
        gdrive_tracks = get_gdrive_bgm_tracks(mood)

        if not gdrive_tracks and mood != "default":
            # 해당 무드가 구글 드라이브에 없으면 default 무드 시도
            print(f"  [BGM] '{mood}' 무드가 없어 'default' 무드로 대체 탐색 중...")
            local_default = _local_tracks(BGM_DIR / "default")
            if local_default:
                return local_default[0]
            gdrive_tracks = get_gdrive_bgm_tracks("default")

        if gdrive_tracks:
            if seed:
                idx = int(hashlib.md5(seed.encode("utf-8")).hexdigest(), 16) % len(gdrive_tracks)
                selected = gdrive_tracks[idx]
            else:
                selected = random.choice(gdrive_tracks)

            target_folder = BGM_DIR / mood
            target_folder.mkdir(parents=True, exist_ok=True)
            local_dest = target_folder / selected["name"]

            # 이미 다운로드되어 있으면 캐시된 파일 바로 사용
            if local_dest.is_file() and local_dest.stat().st_size > 1000:
                print(f"  🎵 [BGM] 캐시된 구글 드라이브 음원 사용: {selected['name']}")
                return local_dest

            print(f"  ⬇️ [BGM] Google Drive에서 음원 다운로드 중 ({mood}): {selected['name']}...")
            if download_drive_file_to_temp(selected["id"], local_dest):
                print(f"  ✅ [BGM] 음원 다운로드 완료: {local_dest.name} ({local_dest.stat().st_size / 1024 / 1024:.2f} MB)")
                return local_dest
            else:
                print(f"  ⚠️ [BGM] Google Drive 음원 다운로드 실패: {selected['name']}")
    except Exception as e:
        print(f"  ⚠️ [BGM] Google Drive BGM 조회 중 예외 발생: {e}")

    # 3. 최후의 수단: 다른 로컬 무드에 있는 음원이라도 사용
    for m in MOODS:
        fallback = _local_tracks(BGM_DIR / m)
        if fallback:
            return fallback[0]

    return None
