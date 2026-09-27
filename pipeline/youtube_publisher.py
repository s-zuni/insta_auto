"""
YouTube Data API v3 Automatic Shorts Publisher.
Publishes 9:16 vertical videos to YouTube Shorts with automatic OAuth2 refresh token authentication.
"""
import os
import sys
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
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


def get_youtube_service():
    """
    Refresh Token 기반으로 OAuth2 자격 증명을 자동 갱신하여 YouTube Data API v3 서비스 객체를 생성합니다.
    24시간 무인 가동되는 서버(Railway) 환경에 완벽 최적화되어 있습니다.
    """
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    client_id = os.getenv("YOUTUBE_CLIENT_ID")
    client_secret = os.getenv("YOUTUBE_CLIENT_SECRET")
    refresh_token = os.getenv("YOUTUBE_REFRESH_TOKEN")

    if not client_id or not client_secret or not refresh_token:
        raise ValueError("YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN 환경변수가 설정되지 않았습니다.")

    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=["https://www.googleapis.com/auth/youtube.upload"]
    )

    return build("youtube", "v3", credentials=creds)


def upload_shorts_to_youtube(
    video_path: str | Path,
    title: str,
    description: str,
    tags: Optional[List[str]] = None,
    privacy_status: str = "public"
) -> Dict[str, Any]:
    """
    생성된 9:16 비디오를 YouTube Shorts로 업로드합니다.
    제목이나 설명에 #Shorts 태그가 포함되어야 유튜브에서 Shorts로 자동 분류합니다.
    """
    from googleapiclient.http import MediaFileUpload

    video_path = Path(video_path)
    if not video_path.is_file():
        raise FileNotFoundError(f"업로드할 비디오 파일이 없습니다: {video_path}")

    try:
        service = get_youtube_service()

        shorts_title = title if "#Shorts" in title else f"{title} #Shorts"
        if len(shorts_title) > 100:
            shorts_title = shorts_title[:90] + " #Shorts"

        shorts_desc = description
        if "#Shorts" not in shorts_desc:
            shorts_desc = f"{description}\n\n#Shorts #MBTI #사주 #운세"

        if not tags:
            tags = ["Shorts", "MBTI", "사주", "운세", "오늘의운세", "병오년"]

        body = {
            "snippet": {
                "title": shorts_title,
                "description": shorts_desc,
                "tags": tags,
                "categoryId": "24"  # Entertainment
            },
            "status": {
                "privacyStatus": privacy_status,  # public, unlisted, private
                "selfDeclaredMadeForKids": False
            }
        }

        print(f"[YOUTUBE] YouTube Shorts 업로드 시작 ('{shorts_title}')...")
        media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True)
        request = service.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )

        response = request.execute()
        video_id = response.get("id")
        shorts_url = f"https://www.youtube.com/shorts/{video_id}"

        print(f"[SUCCESS] 🎉 YouTube Shorts 게시 완료! (ID: {video_id})")
        print(f"  ▶️ URL: {shorts_url}")

        return {
            "id": video_id,
            "status": "PUBLISHED",
            "link": shorts_url
        }

    except Exception as e:
        err_msg = str(e)
        print(f"[ERROR] YouTube Shorts 업로드 중 오류 발생: {err_msg}")
        return {"error": err_msg}


if __name__ == "__main__":
    test_video = Path("assets/output/final_reel.mp4")
    if test_video.is_file():
        print(f"[INFO] YouTube Shorts 연동 점검 시작 ({test_video.name})...")
        res = upload_shorts_to_youtube(
            video_path=test_video,
            title="MBTI x 사주 릴스 테스트",
            description="자동 생성 파이프라인 연동 테스트",
            privacy_status="unlisted"  # 테스트용 일부공개
        )
        print("결과:", res)
    else:
        print("[ERROR] 테스트용 비디오 파일이 없습니다.")