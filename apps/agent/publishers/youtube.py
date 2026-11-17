"""YouTube Shorts 업로더 (YouTube Data API v3, resumable upload).

Shorts 조건: 세로(9:16), 60초 이하. 제목/설명에 #Shorts 를 포함한다.
상태: 실호출 로직 작성됨, 실계정 검증 전. 기본 공개범위는 private (YT_PRIVACY).
주의: 미검증(Unverified) API 프로젝트에서 올린 영상은 private 으로 강제될 수 있다.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from ..core.config import settings
from ..core.schemas import PublishResult, ShortsContent

MAX_SECONDS = 60


def build_metadata(s: ShortsContent) -> dict:
    title = s.title[:90] + " #Shorts"
    desc = f"{s.caption}\n\n" + " ".join(f"#{t}" for t in s.hashtags[:10]) + " #Shorts"
    return {
        "snippet": {"title": title[:100], "description": desc[:4900], "tags": s.hashtags[:15], "categoryId": "22"},
        "status": {"privacyStatus": settings.yt_privacy, "selfDeclaredMadeForKids": False},
    }


def _upload_sync(video: Path, body: dict) -> str:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    creds = Credentials(
        None, refresh_token=settings.yt_refresh_token, client_id=settings.yt_client_id,
        client_secret=settings.yt_client_secret, token_uri="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )
    yt = build("youtube", "v3", credentials=creds, cache_discovery=False)
    req = yt.videos().insert(part="snippet,status", body=body,
                             media_body=MediaFileUpload(str(video), chunksize=-1, resumable=True))
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    return resp["id"]


async def publish(shorts: ShortsContent, video_path: Path | None, dry_run: bool = True) -> PublishResult:
    if not video_path or not Path(video_path).exists():
        return PublishResult(channel="youtube", status="failed", message="영상 파일이 없습니다 (먼저 영상 생성 필요)")
    if shorts.duration_sec and shorts.duration_sec > MAX_SECONDS:
        return PublishResult(channel="youtube", status="failed", message=f"Shorts는 {MAX_SECONDS}초 이하여야 합니다 ({shorts.duration_sec:.0f}초)")
    body = build_metadata(shorts)
    if dry_run:
        return PublishResult(channel="youtube", status="dry_run", message=f"제목 '{body['snippet']['title']}' / 공개범위 {settings.yt_privacy}")
    if not (settings.yt_client_id and settings.yt_client_secret and settings.yt_refresh_token):
        return PublishResult(channel="youtube", status="failed", message="YT_CLIENT_ID/SECRET/REFRESH_TOKEN 미설정")
    try:
        vid = await asyncio.to_thread(_upload_sync, Path(video_path), body)
        return PublishResult(channel="youtube", status="ok", url=f"https://youtube.com/shorts/{vid}", message="업로드 완료")
    except Exception as e:  # noqa: BLE001
        return PublishResult(channel="youtube", status="failed", message=f"{type(e).__name__}: {e}")
