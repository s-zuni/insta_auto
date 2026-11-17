"""Threads Official API 업로더 — 첫 글 + reply_to_id 체인.

Docs: https://developers.facebook.com/docs/threads/posts
상태: 실호출 로직 작성됨, 실계정 검증 전 (publisher-tester 스킬로 dry-run 후 private 계정 테스트)
"""
from __future__ import annotations

import asyncio

import httpx

from ..core.config import settings
from ..core.schemas import PublishResult, ThreadsContent

BASE = "https://graph.threads.net/v1.0"
MAX_LEN = 500


def validate(c: ThreadsContent) -> list[str]:
    errs = []
    for i, p in enumerate(c.posts, 1):
        if len(p) > MAX_LEN:
            errs.append(f"{i}번째 글이 {MAX_LEN}자를 초과합니다 ({len(p)}자)")
    return errs


async def publish(content: ThreadsContent, dry_run: bool = True) -> PublishResult:
    errs = validate(content)
    if errs:
        return PublishResult(channel="threads", status="failed", message="; ".join(errs))
    if dry_run:
        return PublishResult(channel="threads", status="dry_run", message=f"{len(content.posts)}개 글 체인 검증 통과")
    if not (settings.threads_user_id and settings.threads_access_token):
        return PublishResult(channel="threads", status="failed", message="THREADS_USER_ID/ACCESS_TOKEN 미설정")

    uid, token = settings.threads_user_id, settings.threads_access_token
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            parent: str | None = None
            first_id: str | None = None
            for text in content.posts:
                params = {"media_type": "TEXT", "text": text, "access_token": token}
                if parent:
                    params["reply_to_id"] = parent
                r = await client.post(f"{BASE}/{uid}/threads", params=params)
                r.raise_for_status()
                creation_id = r.json()["id"]
                await asyncio.sleep(3)  # 컨테이너 준비 대기 (공식 권장 ~30s 이내)
                r = await client.post(
                    f"{BASE}/{uid}/threads_publish",
                    params={"creation_id": creation_id, "access_token": token},
                )
                r.raise_for_status()
                parent = r.json()["id"]
                first_id = first_id or parent
            link = await client.get(
                f"{BASE}/{first_id}", params={"fields": "permalink", "access_token": token}
            )
            url = link.json().get("permalink") if link.status_code == 200 else None
        return PublishResult(channel="threads", status="ok", url=url, message=f"{len(content.posts)}개 게시")
    except Exception as e:  # noqa: BLE001
        return PublishResult(channel="threads", status="failed", message=f"{type(e).__name__}: {e}")
