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
