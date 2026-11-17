"""Instagram Reels 업로더 (Meta Graph API, resumable upload — 공개 URL 불필요).

Docs: https://developers.facebook.com/docs/instagram-platform/content-publishing
상태: 실호출 로직 작성됨, 실계정 검증 전. 비즈니스/크리에이터 계정 + instagram_content_publish 권한 필요.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import httpx

from ..core.config import settings
from ..core.schemas import PublishResult, ShortsContent


def build_caption(s: ShortsContent) -> str:
    tags = " ".join(f"#{t}" for t in s.hashtags[:10])
    return f"{s.caption}\n\n{tags}".strip()[:2200]


async def publish(shorts: ShortsContent, video_path: Path | None, dry_run: bool = True) -> PublishResult:
    if not video_path or not Path(video_path).exists():
        return PublishResult(channel="instagram", status="failed", message="영상 파일이 없습니다 (먼저 영상 생성 필요)")
    caption = build_caption(shorts)
    if dry_run:
        return PublishResult(channel="instagram", status="dry_run", message=f"캡션 {len(caption)}자, 영상 {Path(video_path).stat().st_size // 1024}KB 검증 통과")
    if not (settings.ig_user_id and settings.ig_access_token):
        return PublishResult(channel="instagram", status="failed", message="IG_USER_ID/IG_ACCESS_TOKEN 미설정")

    base = f"https://graph.facebook.com/{settings.ig_graph_version}"
    token = settings.ig_access_token
    data = Path(video_path).read_bytes()
    try:
        async with httpx.AsyncClient(timeout=120) as c:
            r = await c.post(f"{base}/{settings.ig_user_id}/media", data={
                "media_type": "REELS", "upload_type": "resumable",
                "caption": caption, "access_token": token,
            })
            r.raise_for_status()
            container, upload_uri = r.json()["id"], r.json()["uri"]

            up = await c.post(upload_uri, content=data, headers={
                "Authorization": f"OAuth {token}", "offset": "0", "file_size": str(len(data)),
            })
            up.raise_for_status()

            for _ in range(60):  # 최대 ~5분 대기
                st = await c.get(f"{base}/{container}", params={"fields": "status_code", "access_token": token})
                code = st.json().get("status_code")
                if code == "FINISHED":
                    break
                if code == "ERROR":
                    return PublishResult(channel="instagram", status="failed", message=f"처리 오류: {st.json()}")
                await asyncio.sleep(5)
            else:
                return PublishResult(channel="instagram", status="failed", message="처리 대기 시간 초과")

            pub = await c.post(f"{base}/{settings.ig_user_id}/media_publish",
                               data={"creation_id": container, "access_token": token})
            pub.raise_for_status()
            media_id = pub.json()["id"]
            pl = await c.get(f"{base}/{media_id}", params={"fields": "permalink", "access_token": token})
            url = pl.json().get("permalink") if pl.status_code == 200 else None
        return PublishResult(channel="instagram", status="ok", url=url, message="릴스 게시 완료")
    except Exception as e:  # noqa: BLE001
        return PublishResult(channel="instagram", status="failed", message=f"{type(e).__name__}: {e}")
