"""네이버 블로그 업로더 — Playwright + 로컬 크롬 세션(persistent profile) 유지.

네이버는 블로그 글쓰기 공식 API가 없어 에디터(SmartEditor ONE)를 자동 조작한다.
→ 셀렉터가 가장 깨지기 쉬운 모듈. 모든 셀렉터는 SELECTORS 한 곳에 모으고 publisher-tester 스킬로 점검한다.

최초 1회: `python -m apps.agent.publishers.naver_blog login` 으로 창을 띄워 직접 로그인 (세션이 profile 폴더에 저장됨).
상태: 골격 + 베스트에포트 구현. 실계정 검증 전 (팀원 C 가 셀렉터 확정 필요).
"""
from __future__ import annotations

import asyncio
import re
import sys

from ..core.config import settings
from ..core.schemas import BlogContent, PublishResult

SELECTORS = {
    "editor_frame": "iframe#mainFrame",
    "title": ".se-documentTitle .se-text-paragraph",
    "body": ".se-component.se-text .se-text-paragraph",
    "help_close": ".se-help-panel-close-button",
    "popup_cancel": ".se-popup-button-cancel",
    "publish_open": "button.publish_btn__m9KHH, button[class*='publish_btn']",
    "tag_input": "input#tag-input, input[class*='tag_input']",
    "publish_confirm": "button.confirm_btn__WEaBq, button[class*='confirm_btn']",
}


def markdown_to_plain(md: str) -> list[str]:
    """SmartEditor 는 마크다운을 해석하지 않으므로 헤딩/리스트 기호를 정리한 문단 리스트로 변환."""
    lines = []
    for raw in md.splitlines():
        t = re.sub(r"^#{1,6}\s*", "", raw).strip()
        t = re.sub(r"^[-*]\s+", "• ", t)
        lines.append(t)
    return lines


def validate(c: BlogContent) -> list[str]:
    errs = []
    if not c.title.strip():
        errs.append("제목이 비어 있습니다")
    if len(c.body_markdown.strip()) < 300:
        errs.append("본문이 너무 짧습니다 (300자 미만)")
    if not settings.naver_blog_id:
        errs.append("NAVER_BLOG_ID 미설정")
    return errs


async def _launch(headless: bool):
    from playwright.async_api import async_playwright

    pw = await async_playwright().start()
    settings.profile_dir.mkdir(parents=True, exist_ok=True)
    ctx = await pw.chromium.launch_persistent_context(
        str(settings.profile_dir), channel="chrome", headless=headless,
        viewport={"width": 1280, "height": 900}, locale="ko-KR",
    )
    return pw, ctx


async def login() -> None:
    pw, ctx = await _launch(headless=False)
    page = ctx.pages[0] if ctx.pages else await ctx.new_page()
    await page.goto("https://nid.naver.com/nidlogin.login")
    print("브라우저에서 로그인을 마치면 Enter 를 누르세요...")
    await asyncio.to_thread(input)
    await ctx.close()
    await pw.stop()


async def publish(content: BlogContent, dry_run: bool = True) -> PublishResult:
    errs = [e for e in validate(content) if not (dry_run and "NAVER_BLOG_ID" in e)]
    if errs:
        return PublishResult(channel="naver_blog", status="failed", message="; ".join(errs))
    if dry_run:
        return PublishResult(channel="naver_blog", status="dry_run",
                             message=f"본문 {len(content.body_markdown)}자, 태그 {len(content.tags)}개 검증 통과")
    pw = ctx = None
    try:
        pw, ctx = await _launch(settings.naver_headless)
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        await page.goto(f"https://blog.naver.com/{settings.naver_blog_id}?Redirect=Write")
        frame = page.frame_locator(SELECTORS["editor_frame"])
        # 로그인 안 된 경우
        if "nidlogin" in page.url:
            return PublishResult(channel="naver_blog", status="failed", message="로그인 세션 없음 — `naver_blog login` 먼저 실행")
        for sel in (SELECTORS["popup_cancel"], SELECTORS["help_close"]):  # 이어쓰기/도움말 팝업
            loc = frame.locator(sel)
            if await loc.count():
                await loc.first.click()
        await frame.locator(SELECTORS["title"]).first.click()
        await page.keyboard.type(content.title, delay=15)
        await frame.locator(SELECTORS["body"]).first.click()
        for line in markdown_to_plain(content.body_markdown):
            await page.keyboard.type(line, delay=5)
            await page.keyboard.press("Enter")
        await frame.locator(SELECTORS["publish_open"]).first.click()
        tag = frame.locator(SELECTORS["tag_input"])
        if await tag.count():
            for t in content.tags[:10]:
                await tag.first.fill(t)
                await page.keyboard.press("Enter")
        await frame.locator(SELECTORS["publish_confirm"]).first.click()
        await page.wait_for_load_state("networkidle", timeout=20000)
        return PublishResult(channel="naver_blog", status="ok", url=page.url, message="발행 클릭 완료 (결과 URL 확인 필요)")
    except Exception as e:  # noqa: BLE001
        return PublishResult(channel="naver_blog", status="failed", message=f"{type(e).__name__}: {e}")
    finally:
        if ctx:
            await ctx.close()
        if pw:
            await pw.stop()


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "login":
    asyncio.run(login())
