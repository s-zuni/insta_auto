"""
Instagram Graph API Automatic Reels Publisher.
Publishes vertical 9:16 videos to Instagram account 'mbti.ju'.
"""
import os
import sys
import time
import requests
from pathlib import Path
from typing import Dict, Any, Optional
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


def _check_token_validity(account_id: str, access_token: str) -> Optional[str]:
    """
    게시 시도 전에 토큰 상태를 미리 점검합니다.
    문제가 없으면 None, 문제가 있으면 원인과 해결 방법을 담은 한글 메시지를 반환합니다.
    """
    try:
        res = requests.get(
            f"https://graph.facebook.com/v19.0/{account_id}",
            params={"fields": "id,username", "access_token": access_token},
            timeout=15,
        )
        if res.ok:
            return None

        err = res.json().get("error", {}) if res.headers.get("content-type", "").startswith("application/json") else {}
        message = err.get("message", res.text)
        code = err.get("code")

        if code in (190, 102) or "expired" in message.lower() or "session has expired" in message.lower():
            return (
                f"Instagram 액세스 토큰이 만료되었습니다: {message}\n"
                "  ▶ 해결 방법: Graph API Explorer에서 새 단기 토큰을 발급받은 뒤\n"
                "    'python pipeline/insta_token_refresh.py <새_단기_토큰>' 을 실행해\n"
                "    사실상 만료되지 않는 장기 페이지 액세스 토큰으로 교체하세요.\n"
                "    (자세한 절차는 README 또는 스크립트 안내 참고)"
            )
        return f"Instagram 토큰/계정 점검 실패: {message}"
    except Exception as e:
        return f"Instagram 토큰 사전 점검 중 네트워크 오류: {e}"


def publish_reel_to_instagram(
    video_url: str,
    caption: str,
    account_id: Optional[str] = None,
    access_token: Optional[str] = None
) -> Dict[str, Any]:
    """
    Instagram Graph API를 사용하여 릴스 영상(video_url)과 캡션을 자동 게시합니다.
    """
    if not account_id:
        account_id = os.getenv("INSTAGRAM_ACCOUNT_ID")
    if not access_token:
        access_token = os.getenv("INSTAGRAM_ACCESS_TOKEN")

    if not account_id or not access_token:
        raise ValueError("INSTAGRAM_ACCOUNT_ID 및 INSTAGRAM_ACCESS_TOKEN이 필요합니다.")

    # 0. 토큰 사전 점검 (만료된 토큰으로 컨테이너를 만들었다가 인코딩 대기 시간을
    #    낭비하는 것을 방지하고, 만료 시 원인/해결법을 바로 안내합니다.)
    token_error = _check_token_validity(account_id, access_token)
    if token_error:
        print(f"[ERROR] {token_error}")
        return {"error": token_error}

    base_url = f"https://graph.facebook.com/v19.0/{account_id}"

    # 1. 릴스미디어 컨테이너 생성
    print(f"[INSTA] 릴스 미디어 컨테이너 생성 요청 (계정: {account_id})...")
    container_url = f"{base_url}/media"
    container_payload = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "access_token": access_token
    }

    res = requests.post(container_url, data=container_payload)
    if not res.ok:
        err_msg = res.json().get("error", {}).get("message", res.text)
        print(f"[ERROR] 릴스 컨테이너 생성 실패: {err_msg}")
        return {"error": err_msg, "status_code": res.status_code}

    container_id = res.json().get("id")
    print(f"  ✅ 컨테이너 생성 완료 (ID: {container_id})")

    # 2. 업로드 및 인코딩 상태 대기 (최대 5분)
    print("  ⏳ Instagram 인코딩 및 처리 대기 중...")
    status_url = f"https://graph.facebook.com/v19.0/{container_id}"
    status_params = {"fields": "status_code", "access_token": access_token}

    start_t = time.time()
    while time.time() - start_t < 300:
        s_res = requests.get(status_url, params=status_params)
        if s_res.ok:
            status_code = s_res.json().get("status_code")
            if status_code == "FINISHED":
                print("  ✅ 영상 인코딩 완료!")
                break
            elif status_code == "ERROR":
                print("  ❌ Instagram 영상 처리 중 에러가 발생했습니다.")
                return {"error": "Instagram media processing error", "details": s_res.json()}
        time.sleep(10)

    # 3. 릴스 게시 요청
    print("[INSTA] 릴스 최종 게시(Publish) 실행 중...")
    publish_url = f"{base_url}/media_publish"
    publish_payload = {
        "creation_id": container_id,
        "access_token": access_token
    }

    p_res = requests.post(publish_url, data=publish_payload)
    if p_res.ok:
        post_id = p_res.json().get("id")
        permalink = f"https://www.instagram.com/p/{post_id}/"
        print(f"[SUCCESS] 🎉 인스타그램 릴스 게시 완료! (게시글 ID: {post_id})")
        return {"id": post_id, "status": "PUBLISHED", "link": permalink}
    else:
        err_msg = p_res.json().get("error", {}).get("message", p_res.text)
        print(f"[ERROR] 릴스 게시 실패: {err_msg}")
        return {"error": err_msg}


if __name__ == "__main__":
    account_id = os.getenv("INSTAGRAM_ACCOUNT_ID")
    token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
    print(f"[INFO] Instagram 계정 상태 확인 (ID: {account_id})")
    url = f"https://graph.facebook.com/v19.0/{account_id}"
    res = requests.get(url, params={"fields": "id,username,name", "access_token": token})
    if res.ok:
        print("연동 계정 정보:", res.json())
    else:
        print("오류:", res.text)
