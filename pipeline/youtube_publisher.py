"""
YouTube Data API v3 Automatic Shorts Publisher.
Publishes 9:16 vertical videos to YouTube Shorts with automatic OAuth2 refresh token authentication.
"""
import os
import sys
import json
import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
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
        scopes=None
    )

    return build("youtube", "v3", credentials=creds)


def get_registered_channel_info() -> Dict[str, Any]:
    """
    현재 .env에 등록된 YOUTUBE_REFRESH_TOKEN 계정의 채널명과 ID 정보를 조회합니다.
    """
    try:
        service = get_youtube_service()
        ch_res = service.channels().list(part="snippet,statistics", mine=True).execute()
        items = ch_res.get("items", [])
        if items:
            item = items[0]
            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})
            return {
                "title": snippet.get("title", ""),
                "id": item.get("id", ""),
                "custom_url": snippet.get("customUrl", ""),
                "subscriber_count": stats.get("subscriberCount", "0")
            }
    except Exception as e:
        err_str = str(e)
        if "insufficientPermissions" in err_str:
            return {
                "title": "유튜브 채널 (업로드 권한 정상 연동됨)",
                "note": "상세 채널명을 확인하려면 'python pipeline/youtube_auth.py'를 다시 실행해 권한을 갱신하세요."
            }
        return {"error": err_str}
    return {}


def get_target_publish_at(scheduled_time_kst: Optional[str] = "18:30") -> Tuple[Optional[str], Optional[str]]:
    """
    KST 기준 목표 시각(기본값 18:30)을 YouTube Data API v3의 publishAt 규격(RFC 3339 UTC)으로 변환합니다.
    
    규칙:
    1. scheduled_time_kst가 'none', 'immediate', 'off' 등이면 예약 없이 즉시 공개.
    2. 현재 시각(KST) 대비 목표 시각이 최소 5분 이상 미래라면 오늘 해당 시각으로 예약.
    3. 만약 오늘 목표 시각이 이미 지났거나 5분 미만으로 남았다면 None을 반환(즉시 공개 처리).
    
    반환: (publish_at_iso_utc, display_kst_str)
    """
    if not scheduled_time_kst or str(scheduled_time_kst).strip().lower() in ("none", "immediate", "now", "off", "false", ""):
        return None, None

    try:
        parts = str(scheduled_time_kst).strip().split(":")
        target_h = int(parts[0])
        target_m = int(parts[1]) if len(parts) > 1 else 0
    except Exception:
        target_h, target_m = 18, 30

    try:
        import zoneinfo
        kst_tz = zoneinfo.ZoneInfo("Asia/Seoul")
    except Exception:
        kst_tz = datetime.timezone(datetime.timedelta(hours=9))

    utc_tz = datetime.timezone.utc
    now_kst = datetime.datetime.now(kst_tz)
    target_dt_kst = now_kst.replace(hour=target_h, minute=target_m, second=0, microsecond=0)

    diff_seconds = (target_dt_kst - now_kst).total_seconds()

    # 목표 시각까지 최소 5분(300초) 이상 남아 있는 경우에만 YouTube 예약 공개 등록
    # (유튜브 Data API는 현재 시각보다 과거이거나 너무 임박한 publishAt에 대해 에러를 반환함)
    if diff_seconds >= 300:
        target_dt_utc = target_dt_kst.astimezone(utc_tz)
        publish_at_iso = target_dt_utc.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        display_kst = target_dt_kst.strftime("%Y-%m-%d %H:%M KST")
        return publish_at_iso, display_kst

    return None, None


def upload_shorts_to_youtube(
    video_path: str | Path,
    title: str,
    description: str,
    tags: Optional[List[str]] = None,
    privacy_status: str = "public",
    scheduled_time_kst: Optional[str] = "18:30"
) -> Dict[str, Any]:
    """
    생성된 9:16 비디오를 YouTube Shorts로 업로드합니다.
    - scheduled_time_kst: KST 기준 예약 공개 시각 (기본값: '18:30').
      새벽이나 낮에 작업이 실행되어도 유튜브 서버가 정시(18:30 KST)에 자동으로 공개 전환합니다.
      이미 지난 시각이거나 비활성화 시 즉시 공개(public)로 게시됩니다.
    - 제목이나 설명에 #Shorts 태그가 포함되어야 유튜브에서 Shorts로 자동 분류합니다.
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
            tags = ["Shorts", "MBTI", "사주", "운세", "병오년"]

        # 1. 예약 공개(publishAt) 계산
        target_schedule = scheduled_time_kst if scheduled_time_kst is not None else os.getenv("YOUTUBE_SCHEDULE_TIME_KST", "18:30")
        publish_at_iso, display_kst = get_target_publish_at(target_schedule)

        status_body: Dict[str, Any] = {
            "selfDeclaredMadeForKids": False
        }

        if publish_at_iso:
            # YouTube API 규격: publishAt을 설정할 때는 privacyStatus가 반드시 'private'이어야 함
            status_body["privacyStatus"] = "private"
            status_body["publishAt"] = publish_at_iso
            print(f"[YOUTUBE] ⏰ YouTube Shorts 정시 예약 발행 설정: {display_kst} (UTC: {publish_at_iso})")
        else:
            status_body["privacyStatus"] = privacy_status
            print(f"[YOUTUBE] 🚀 YouTube Shorts 즉시 게시 모드 (상태: {privacy_status})")

        body = {
            "snippet": {
                "title": shorts_title,
                "description": shorts_desc,
                "tags": tags,
                "categoryId": "24"  # Entertainment
            },
            "status": status_body
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

        is_scheduled = bool(publish_at_iso)
        status_label = "SCHEDULED" if is_scheduled else "PUBLISHED"
        print(f"[SUCCESS] 🎉 YouTube Shorts {'정시 예약 완료' if is_scheduled else '게시 완료'}! (ID: {video_id})")
        if is_scheduled:
            print(f"  ⏰ 자동 공개 예정 시각: {display_kst}")
        print(f"  ▶️ URL: {shorts_url}")

        return {
            "id": video_id,
            "status": status_label,
            "link": shorts_url,
            "scheduled": is_scheduled,
            "scheduled_time_kst": display_kst if is_scheduled else None
        }

    except Exception as e:
        err_msg = str(e)
        print(f"[ERROR] YouTube Shorts 업로드 중 오류 발생: {err_msg}")
        return {"error": err_msg}


if __name__ == "__main__":
    print("[YOUTUBE] 등록된 채널 정보 조회 중...")
    info = get_registered_channel_info()
    if info.get("title"):
        print("\n=======================================================")
        print(f"🎉 연동된 유튜브 채널명: [{info['title']}]")
        if info.get("id"):
            print(f"   채널 ID: {info['id']}")
        if info.get("custom_url"):
            print(f"   핸들: {info['custom_url']}")
        if info.get("subscriber_count"):
            print(f"   구독자 수: {info['subscriber_count']}명")
        if info.get("note"):
            print(f"   참고: {info['note']}")
        print("=======================================================\n")
    else:
        print("조회 에러:", info)