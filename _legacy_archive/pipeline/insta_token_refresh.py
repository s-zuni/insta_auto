"""
Instagram/Facebook Graph API 액세스 토큰 갱신 유틸리티.

문제 상황: Graph API Explorer 등에서 바로 복사한 토큰은 "단기 토큰"으로
보통 1~2시간이면 만료됩니다 ("Error validating access token: Session has
expired..."). 이 스크립트는 그 단기 토큰을,

  1) 장기 사용자 토큰 (60일 유효) 으로 교환한 뒤
  2) 페이지 액세스 토큰 (사용자가 비밀번호를 바꾸거나 앱 권한을 철회하지
     않는 한 사실상 만료되지 않음) 을 조회합니다.

.env 에 필요한 값 (Facebook 개발자 콘솔 -> 내 앱 -> 설정 -> 기본 설정):
  FB_APP_ID=...
  FB_APP_SECRET=...

사용법:
  1. https://developers.facebook.com/tools/explorer/ 에서
     인스타그램 계정과 연결된 앱을 선택하고, 다음 권한으로 토큰을 발급받습니다:
       pages_show_list, pages_read_engagement,
       instagram_basic, instagram_content_publish
  2. 발급된 토큰(단기)을 복사해서 아래처럼 실행합니다:
       python pipeline/insta_token_refresh.py <단기_토큰>
  3. 출력된 "페이지 액세스 토큰" 을 .env 의 INSTAGRAM_ACCESS_TOKEN 에 붙여넣습니다.

이후에는 토큰이 사실상 만료되지 않으므로 이 스크립트를 다시 실행할 필요가
없습니다 (단, 60일 이상 로그인/사용이 없거나 비밀번호를 변경하면 재실행 필요).
"""
import os
import sys
from pathlib import Path
import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv()

GRAPH_VERSION = "v21.0"


def exchange_for_long_lived_user_token(short_lived_token: str, app_id: str, app_secret: str) -> str:
    """단기 토큰을 60일짜리 장기 사용자 토큰으로 교환합니다."""
    url = f"https://graph.facebook.com/{GRAPH_VERSION}/oauth/access_token"
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": app_id,
        "client_secret": app_secret,
        "fb_exchange_token": short_lived_token,
    }
    res = requests.get(url, params=params, timeout=30)
    res.raise_for_status()
    return res.json()["access_token"]


def get_page_access_tokens(long_lived_user_token: str) -> list:
    """장기 사용자 토큰으로 연결된 페이지들의 (사실상 무기한) 액세스 토큰을 조회합니다."""
    url = f"https://graph.facebook.com/{GRAPH_VERSION}/me/accounts"
    res = requests.get(url, params={"access_token": long_lived_user_token}, timeout=30)
    res.raise_for_status()
    return res.json().get("data", [])


def main():
    if len(sys.argv) < 2:
        print("사용법: python pipeline/insta_token_refresh.py <그래프API_익스플로러_단기_토큰>")
        sys.exit(1)

    short_token = sys.argv[1].strip()
    app_id = os.getenv("FB_APP_ID", "")
    app_secret = os.getenv("FB_APP_SECRET", "")

    if not app_id or not app_secret:
        print("❌ .env에 FB_APP_ID / FB_APP_SECRET을 먼저 설정하세요.")
        print("   (Facebook 개발자 콘솔 -> 내 앱 -> 설정 -> 기본 설정에서 확인 가능)")
        sys.exit(1)

    print("[1/2] 단기 토큰 -> 장기(60일) 사용자 토큰으로 교환 중...")
    try:
        long_lived_user_token = exchange_for_long_lived_user_token(short_token, app_id, app_secret)
    except requests.HTTPError as e:
        print(f"❌ 교환 실패: {e.response.text if e.response is not None else e}")
        sys.exit(1)
    print("  ✅ 장기 사용자 토큰 발급 완료")

    print("[2/2] 페이지 액세스 토큰(사실상 만료되지 않음) 조회 중...")
    try:
        pages = get_page_access_tokens(long_lived_user_token)
    except requests.HTTPError as e:
        print(f"❌ 페이지 조회 실패: {e.response.text if e.response is not None else e}")
        sys.exit(1)

    if not pages:
        print("⚠️ 연결된 페이지가 없습니다. 이 Facebook 계정에 Instagram 비즈니스 계정과")
        print("   연결된 페이지가 있는지, 앱 권한(pages_show_list, instagram_basic,")
        print("   instagram_content_publish)이 승인되었는지 확인하세요.")
        print(f"\n대체로 사용할 수 있는 장기 사용자 토큰 (60일 후 만료):\n{long_lived_user_token}")
        return

    print(f"\n✅ 연결된 페이지 {len(pages)}개 발견:\n")
    for p in pages:
        print(f"  - 페이지명: {p.get('name')} (ID: {p.get('id')})")
        print(f"    페이지 액세스 토큰: {p.get('access_token')}\n")

    print("=" * 70)
    print("👉 위 페이지 액세스 토큰 중 인스타그램 비즈니스 계정과 연결된 페이지의")
    print("   토큰을 .env 파일의 INSTAGRAM_ACCESS_TOKEN 값으로 교체하세요.")
    print("   이 토큰은 비밀번호 변경/권한 철회가 없는 한 만료되지 않습니다.")
    print("=" * 70)


if __name__ == "__main__":
    main()
