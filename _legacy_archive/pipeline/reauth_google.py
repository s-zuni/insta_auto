"""
Unified Google Drive & YouTube Shorts OAuth2 Re-authentication Script.
One-click browser login to re-authorize both Google Drive and YouTube Data API.

Usage:
    python -m pipeline.reauth_google
"""
import os
import sys
import json
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
venv_python = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
if venv_python.is_file() and Path(sys.executable).resolve() != venv_python.resolve():
    res = subprocess.run([str(venv_python), "-m", "pipeline.reauth_google"] + sys.argv[1:])
    sys.exit(res.returncode)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]


def main():
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        print("[ERROR] 'google-auth-oauthlib' 및 'google-api-python-client' 패키지가 필요합니다.")
        sys.exit(1)

    client_secret_path = PROJECT_ROOT / "client_secret.json"
    if not client_secret_path.is_file():
        print(f"[ERROR] client_secret.json 파일을 찾을 수 없습니다: {client_secret_path}")
        sys.exit(1)

    with open(client_secret_path, "r", encoding="utf-8") as f:
        secret_data = json.load(f)

    installed_info = secret_data.get("installed") or secret_data.get("web") or {}
    client_id = installed_info.get("client_id")
    client_secret = installed_info.get("client_secret")

    print("\n=================================================================")
    print("🔐 구글 드라이브 & 유튜브 쇼츠 원클릭 통합 OAuth 인증")
    print("=================================================================")
    print("브라우저에서 로그인 창이 열립니다.")
    print("  1. 유튜브와 드라이브를 사용할 구글 계정을 선택하세요.")
    print("  2. 'Google에서 확인하지 않은 앱' 경고가 뜨면 [고급] -> [이동(안전하지 않음)]을 클릭하세요.")
    print("  3. 모든 권한(드라이브 및 유튜브) 체크박스를 선택하고 [계속]을 눌러주세요.\n")

    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), scopes=SCOPES)
    creds = flow.run_local_server(port=0, prompt="select_account consent", access_type="offline")

    # 1. token.json 저장 (Google Drive용)
    token_path = PROJECT_ROOT / "token.json"
    token_path.write_text(creds.to_json(), encoding="utf-8")
    print(f"✅ [1/2] 구글 드라이브 인증 파일 저장 완료: {token_path.name}")

    # 2. .env 파일 업데이트 (YouTube Shorts용)
    env_file = PROJECT_ROOT / ".env"
    if env_file.is_file():
        env_text = env_file.read_text(encoding="utf-8")
        lines = env_text.splitlines()
        new_lines = []
        replaced_keys = set()
        for line in lines:
            if line.startswith("YOUTUBE_CLIENT_ID="):
                new_lines.append(f"YOUTUBE_CLIENT_ID={client_id}")
                replaced_keys.add("YOUTUBE_CLIENT_ID")
            elif line.startswith("YOUTUBE_CLIENT_SECRET="):
                new_lines.append(f"YOUTUBE_CLIENT_SECRET={client_secret}")
                replaced_keys.add("YOUTUBE_CLIENT_SECRET")
            elif line.startswith("YOUTUBE_REFRESH_TOKEN="):
                new_lines.append(f"YOUTUBE_REFRESH_TOKEN={creds.refresh_token}")
                replaced_keys.add("YOUTUBE_REFRESH_TOKEN")
            else:
                new_lines.append(line)

        if "YOUTUBE_CLIENT_ID" not in replaced_keys:
            new_lines.append(f"YOUTUBE_CLIENT_ID={client_id}")
        if "YOUTUBE_CLIENT_SECRET" not in replaced_keys:
            new_lines.append(f"YOUTUBE_CLIENT_SECRET={client_secret}")
        if "YOUTUBE_REFRESH_TOKEN" not in replaced_keys:
            new_lines.append(f"YOUTUBE_REFRESH_TOKEN={creds.refresh_token}")

        env_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
        print(f"✅ [2/2] .env 파일 유튜브 토큰 자동 갱신 완료!")

    # 3. 채널 정보 확인
    channel_name = "알 수 없음"
    try:
        yt_service = build("youtube", "v3", credentials=creds)
        ch_res = yt_service.channels().list(part="snippet", mine=True).execute()
        if ch_res.get("items"):
            channel_name = ch_res["items"][0]["snippet"].get("title", "")
    except Exception as e:
        print(f"  (채널 확인 알림: {e})")

    print("\n=================================================================")
    print(f"🎉 인증 완료! 연결된 유튜브 채널: [{channel_name}]")
    print("이제 파이프라인 실행 시 구글 드라이브와 유튜브 쇼츠에 자동 업로드됩니다.")
    print("=================================================================\n")


if __name__ == "__main__":
    main()

