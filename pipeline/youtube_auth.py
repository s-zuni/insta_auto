"""
YouTube OAuth2 Refresh Token Helper Script.
Run this script once locally to authorize your YouTube channel and obtain the YOUTUBE_REFRESH_TOKEN.
Usage:
    python pipeline/youtube_auth.py
"""
import os
import sys
import requests
from pathlib import Path
from dotenv import load_dotenv

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main():
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("[ERROR] 'google-auth-oauthlib' 패키지가 필요합니다.")
        print("        pip install google-auth-oauthlib 명령어로 설치 후 다시 실행하세요.")
        sys.exit(1)

    client_id = os.getenv("YOUTUBE_CLIENT_ID")
    client_secret = os.getenv("YOUTUBE_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("\n=======================================================")
        print("⚠️ .env 파일에 YOUTUBE_CLIENT_ID와 YOUTUBE_CLIENT_SECRET을 설정해야 합니다.")
        print("=======================================================")
        print("1. Google Cloud Console (https://console.cloud.google.com) 접속")
        print("2. 'API 및 서비스' -> '사용 사용자 인증 정보' -> '사용자 인증 정보 만들기' -> 'OAuth 클라이언트 ID' 생성 (데스크톱 앱 선택)")
        print("3. 클라이언트 ID와 클라이언트 보안 비밀번호를 .env 파일에 작성:")
        print("   YOUTUBE_CLIENT_ID=your_client_id")
        print("   YOUTUBE_CLIENT_SECRET=your_client_secret")
        print("=======================================================\n")
        sys.exit(1)

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }

    scopes = [
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube.readonly"
    ]
    flow = InstalledAppFlow.from_client_config(client_config, scopes=scopes)

    print("\n🚀 웹 브라우저에서 유튜브 계정 인증 창이 열립니다...")
    print("   (숏츠를 업로드할 유튜브 채널을 선택해 승인해 주세요.)\n")

    creds = flow.run_local_server(port=8080, prompt="consent", access_type="offline")

    # 채널 정보 조회
    channel_name = "알 수 없음"
    channel_id = ""
    try:
        from googleapiclient.discovery import build
        service = build("youtube", "v3", credentials=creds)
        ch_res = service.channels().list(part="snippet", mine=True).execute()
        if ch_res.get("items"):
            item = ch_res["items"][0]
            channel_name = item["snippet"].get("title", "")
            channel_id = item.get("id", "")
    except Exception as e:
        print(f"  ℹ️ 채널명 확인 참고: {e}")

    print("\n=======================================================")
    print(f"🎉 인증 성공! 등록된 유튜브 채널명: [{channel_name}] (ID: {channel_id})")
    print("=======================================================")
    print("발급된 Refresh Token:")
    print("-" * 65)
    print(creds.refresh_token)
    print("-" * 65)

    # .env 파일에 YOUTUBE_REFRESH_TOKEN 자동 기록
    env_file = PROJECT_ROOT / ".env"
    if env_file.is_file():
        env_text = env_file.read_text(encoding="utf-8")
        if "YOUTUBE_REFRESH_TOKEN=" in env_text:
            lines = env_text.splitlines()
            new_lines = []
            for line in lines:
                if line.startswith("YOUTUBE_REFRESH_TOKEN="):
                    new_lines.append(f"YOUTUBE_REFRESH_TOKEN={creds.refresh_token}")
                else:
                    new_lines.append(line)
            env_file.write_text("\n".join(new_lines), encoding="utf-8")
        else:
            with open(env_file, "a", encoding="utf-8") as f:
                f.write(f"\n# YouTube OAuth2 Refresh Token\nYOUTUBE_REFRESH_TOKEN={creds.refresh_token}\n")

        print(f"💡 .env 파일에 YOUTUBE_REFRESH_TOKEN 이 자동 기록되었습니다 -> {env_file}")
        print("   이제 이 토큰을 Railway의 Variables(환경변수)에도 추가해 주시면 24시간 무인 업로드가 완료됩니다!\n")


if __name__ == "__main__":
    main()