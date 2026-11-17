"""
FFmpeg 설치 및 실행 가능 여부를 점검하는 유틸리티 모듈.
"""
import shutil
import subprocess
import sys
from pathlib import Path


def get_ffmpeg_path() -> str | None:
    """
    시스템 PATH 또는 일반적인 설치 경로에서 ffmpeg 실행 파일 경로를 탐색합니다.
    """
    # 1. 환경 변수 PATH 확인
    ffmpeg_bin = shutil.which("ffmpeg")
    if ffmpeg_bin:
        return ffmpeg_bin

    # 2. Windows 일반 설치 경로 (Scoop, Choco, WinGet 등)
    home = Path.home()
    candidate_paths = [
        home / "scoop" / "shims" / "ffmpeg.exe",
        home / "scoop" / "apps" / "ffmpeg" / "current" / "bin" / "ffmpeg.exe",
        Path(r"C:\ProgramData\chocolatey\bin\ffmpeg.exe"),
        home / "AppData" / "Local" / "Microsoft" / "WinGet" / "Links" / "ffmpeg.exe",
    ]

    for path in candidate_paths:
        if path.is_file():
            return str(path)

    return None


def check_ffmpeg() -> bool:
    """
    FFmpeg가 설치되어 있고 정상 실행되는지 확인합니다.
    """
    ffmpeg_path = get_ffmpeg_path()
    if not ffmpeg_path:
        print("[ERROR] FFmpeg를 찾을 수 없습니다.")
        print("  - Scoop 사용 시: scoop install ffmpeg")
        print("  - WinGet 사용 시: winget install Gyan.FFmpeg")
        print("  - Choco 사용 시: choco install ffmpeg")
        return False

    try:
        result = subprocess.run(
            [ffmpeg_path, "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        version_line = result.stdout.splitlines()[0] if result.stdout else "알 수 없음"
        print(f"[OK] FFmpeg 감지됨: {ffmpeg_path}")
        print(f"     버전 정보: {version_line}")
        return True
    except Exception as e:
        print(f"[ERROR] FFmpeg 실행 중 오류 발생: {e}")
        return False


if __name__ == "__main__":
    success = check_ffmpeg()
    sys.exit(0 if success else 1)

