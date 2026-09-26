"""
Google Drive OAuth 1회 설정 스크립트.

서비스 계정은 개인 Gmail 드라이브에서 저장 용량이 0 Byte라 파일 업로드가 항상
403 storageQuotaExceeded 로 실패합니다 (2020년 구글 정책 변경). 이 스크립트는
실제 구글 계정으로 브라우저에서 1회 로그인하여 OAuth 자격 증명(refresh token 포함)을
발급받고, 로컬에 token.json 으로 저장합니다.

사전 준비:
1. https://console.cloud.google.com/apis/credentials 에서 서비스 계정과 같은
   (또는 다른) 프로젝트를 선택하고, "OAuth 클라이언트 ID" 를 "데스크톱 앱" 유형으로 생성합니다.
2. 다운로드한 JSON 파일을 프로젝트 루트에 'client_secret.json' 이름으로 저장합니다.
3. OAuth 동의 화면에서 테스트 사용자로 본인 Google 계정을 추가합니다(게시 상태가
   '테스트 중'인 경우 필수).
4. 아래 명령으로 실행합니다:
     python pipeline/gdrive_oauth_setup.py

실행하면 브라우저가 열리고 로그인 후 동의하면 프로젝트 루트에 token.json 이 생성되고,
콘솔에 Railway 등 배포 환경에 등록할 GOOGLE_OAUTH_TOKEN_JSON 값이 출력됩니다.
"""
import sys
import json
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.gdrive_uploader import DRIVE_OAUTH_SCOPES


def main():
    parser = argparse.ArgumentParser(description="Google Drive OAuth 1회 인증 설정")
    parser.add_argument(
        "--client-secret",
        type=str,
        default=str(PROJECT_ROOT / "client_secret.json"),
        help="Google Cloud Console에서 다운로드한 OAuth 클라이언트(데스크톱 앱) JSON 경로",
    )
    parser.add_argument(
        "--token-out",
        type=str,
        default=str(PROJECT_ROOT / "token.json"),
        help="발급받은 토큰을 저장할 경로",
    )
    args = parser.parse_args()

    client_secret_path = Path(args.client_secret)
    if not client_secret_path.is_file():
        print(f"[ERROR] client_secret.json 파일을 찾을 수 없습니다: {client_secret_path}")
        print("Google Cloud Console > API 및 서비스 > 사용자 인증 정보 에서")
        print("'OAuth 클라이언트 ID' (데스크톱 앱)를 만들고 JSON을 다운로드해 주세요.")
        sys.exit(1)

    from google_auth_oauthlib.flow import InstalledAppFlow

    print("[INFO] 브라우저에서 Google 로그인 창이 열립니다. 업로드에 사용할 구글 계정으로 로그인하세요...")
    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_path), scopes=DRIVE_OAUTH_SCOPES)
    creds = flow.run_local_server(port=0)

    token_path = Path(args.token_out)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    print(f"[OK] 토큰이 저장되었습니다: {token_path}")

    # 실제로 Drive API 호출이 되는지 즉시 검증
    from googleapiclient.discovery import build
    service = build("drive", "v3", credentials=creds)
    about = service.about().get(fields="user").execute()
    print(f"[OK] 인증된 계정: {about['user']['emailAddress']}")

    print("\n" + "=" * 70)
    print("아래 값을 Railway 프로젝트의 환경 변수 GOOGLE_OAUTH_TOKEN_JSON 에 등록하세요.")
    print("(값 전체를 한 줄로 복사해서 붙여넣으면 됩니다)")
    print("=" * 70)
    print(json.dumps(json.loads(creds.to_json()), ensure_ascii=False))
    print("=" * 70)


if __name__ == "__main__":
    main()
