"""
Threads Automated Content Generator & Publisher for GitHub Actions / Cron.
1. Automatically generates viral MBTI x Saju thread posts based on time slots (morning/afternoon/evening)
2. Publishes to Threads account (@mbti_ju) via official Threads API
3. Sends real-time progress and post permalink directly to Telegram
"""
import os
import sys
import time
import html
import random
import argparse
import requests
from pathlib import Path
from dotenv import load_dotenv

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv()


def tg_notify(text: str):
    """텔레그램 채팅방으로 실시간 알림을 발송합니다."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        print("[NOTIFY] TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID가 없어 텔레그램 알림을 건너뜁니다.")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        if not r.ok:
            print(f"[NOTIFY][WARN] 텔레그램 발송 실패: {r.text}")
    except Exception as e:
        print(f"[NOTIFY][WARN] 텔레그램 요청 오류: {e}")


def determine_slot() -> str:
    """현재 한국 시간(KST)에 맞춰 적절한 슬롯을 자동 판별합니다."""
    import datetime
    try:
        import zoneinfo
        kst = zoneinfo.ZoneInfo("Asia/Seoul")
        now_hour = datetime.datetime.now(kst).hour
    except Exception:
        # UTC + 9
        now_hour = (datetime.datetime.utcnow().hour + 9) % 24

    if now_hour < 11:
        return "morning"
    elif now_hour < 16:
        return "afternoon"
    else:
        return "evening"


def main():
    parser = argparse.ArgumentParser(description="Threads 자동 포스팅 러너 (GitHub Actions / Cron용)")
    parser.add_argument("--slot", type=str, default="auto", choices=["auto", "morning", "afternoon", "evening"],
                        help="시간대 슬롯 (auto: 현재 시각 기반 자동 판별)")
    parser.add_argument("--category", type=str, default="", choices=["", "사주", "MBTI", "운세"],
                        help="카테고리 (미지정 시 60/20/20 가중치 자동 선택)")
    parser.add_argument("--topic", type=str, default="", help="특정 주제 지정 (선택)")
    parser.add_argument("--with-cta", action="store_true", help="CTA 답글 강제 포함")
    parser.add_argument("--no-publish", action="store_true", help="게시 건너뛰기 (테스트용)")
    args = parser.parse_args()

    slot = determine_slot() if args.slot == "auto" else args.slot
    category = args.category or None

    print("=" * 65)
    print(f"🧵 [THREADS] 자동 포스팅 러너 가동 (슬롯: {slot}, 카테고리: {category or '자동'})")
    print("=" * 65)

    from pipeline.threads_content import generate_threads_thread
    from pipeline.threads_publisher import publish_thread, refresh_long_lived_token

    # 1. 스레드 콘텐츠 생성
    t0 = time.time()
    try:
        thread = generate_threads_thread(
            category=category,
            slot=slot,
            with_cta=args.with_cta or (slot == "evening"),  # 저녁 글에는 기본적으로 CTA 답글 연결
        )
        print(f"[1/2] ✍️ 스레드 생성 완료 ({time.time() - t0:.1f}초) | 카테고리: {thread.category} | 총 {len(thread.posts)}개 글")
    except Exception as e:
        err_msg = f"❌ <b>[Threads 생성 실패]</b>\n<code>{html.escape(str(e))}</code>"
        print(f"[ERROR] 스레드 생성 실패: {e}")
        tg_notify(err_msg)
        sys.exit(1)

    # 본문 미리보기 포맷
    preview_body = thread.posts[0]
    preview_short = preview_body[:180] + ("..." if len(preview_body) > 180 else "")

    if args.no_publish:
        print("[TEST] --no-publish 모드이므로 게시하지 않고 종료합니다.")
        print("=== 생성된 글 목록 ===")
        for idx, p in enumerate(thread.posts, 1):
            print(f"[{idx}] {p}\n")
        return

    # 2. Threads API 게시
    print("[2/2] 🚀 Threads API 타래 게시 중...")
    result = publish_thread(thread.posts, topic_tag=thread.topic_tag)

    if "error" in result:
        err_msg = (
            f"❌ <b>[Threads 게시 실패]</b> ({slot} 슬롯)\n"
            f"카테고리: {thread.category}\n"
            f"오류: <code>{html.escape(str(result['error']))}</code>"
        )
        print(f"[ERROR] Threads 게시 실패: {result['error']}")
        tg_notify(err_msg)
        sys.exit(1)

    permalink = result.get("permalink", "")
    cta_badge = " (🔗 mbtiju.com CTA 포함)" if thread.has_cta else ""

    success_msg = (
        f"🧵 <b>[Threads 자동 게시 완료]</b> [{thread.category}{cta_badge}]\n\n"
        f"• <b>슬롯:</b> {slot.upper()}\n"
        f"• <b>내용:</b>\n<i>\"{html.escape(preview_short)}\"</i>\n\n"
        f"🔗 <b>스레드 바로가기:</b> <a href=\"{permalink}\">{permalink or '스레드 열기'}</a>"
    )
    tg_notify(success_msg)
    print("\n" + "=" * 65)
    print(f"🎉 Threads 타래 게시 성공! 링크: {permalink}")
    print("=" * 65)

    # 3. 토큰 자동 갱신 시도 (만료 방지 백그라운드 케어)
    try:
        ref_res = refresh_long_lived_token()
        if ref_res.get("access_token"):
            print("  🔑 [TOKEN] Threads 60일 장기 토큰 자동 갱신 완료")
    except Exception:
        pass


if __name__ == "__main__":
    main()

