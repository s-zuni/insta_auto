"""
Automated Reels & Shorts Pipeline Runner for GitHub Actions / Scheduled Cron.
1. Automatically plans today's viral MBTI x Saju topic (or uses custom topic)
2. Generates script -> TTS -> AI Visuals -> FFmpeg Composition -> Instagram & YouTube Publish
3. Sends real-time progress and completion links directly to Telegram
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


# ── 게시 시각 가드 ─────────────────────────────────────────────
PUBLISH_TARGET_KST = os.getenv("PUBLISH_TARGET_KST", "18:30")  # 인스타 공개 목표 시각
PUBLISH_LEAD_SEC = int(os.getenv("PUBLISH_LEAD_SEC", "90"))  # 업로드/컨테이너 처리 시간 보정
PUBLISH_MAX_WAIT_MIN = int(os.getenv("PUBLISH_MAX_WAIT_MIN", "100"))  # 목표 시각 전 최대 대기 허용
PUBLISH_LATE_GRACE_MIN = int(os.getenv("PUBLISH_LATE_GRACE_MIN", "120"))  # 목표 시각 이후 허용 지연


def _now_and_target():
    import datetime
    try:
        import zoneinfo
        tz = zoneinfo.ZoneInfo("Asia/Seoul")
    except Exception:
        tz = datetime.timezone(datetime.timedelta(hours=9))
    now = datetime.datetime.now(tz)
    try:
        h, m = (int(x) for x in PUBLISH_TARGET_KST.split(":")[:2])
    except Exception:
        h, m = 18, 30
    return now, now.replace(hour=h, minute=m, second=0, microsecond=0)


def _publish_window():
    """('wait', 대기초) | ('go', 0) | ('skip', 목표 대비 초). 새벽 등 허용 구간 밖이면 skip."""
    now, target = _now_and_target()
    delta = (target - now).total_seconds()  # 양수: 목표까지 남음, 음수: 지남
    if 0 < delta <= PUBLISH_MAX_WAIT_MIN * 60:
        return "wait", max(0.0, delta - PUBLISH_LEAD_SEC)
    if -PUBLISH_LATE_GRACE_MIN * 60 <= delta <= 0:
        return "go", 0.0
    return "skip", delta


def _notify_skip():
    now, target = _now_and_target()
    msg = (
        f"⚠️ <b>[게시 시각 가드] 허용 시간대 밖이라 게시를 건너뜁니다</b>\n\n"
        f"• 목표 공개: <b>{target.strftime('%H:%M')} KST</b>\n"
        f"• 현재: <b>{now.strftime('%H:%M:%S')} KST</b>\n"
        f"• 사유: GitHub 스케줄 지연 등으로 새벽/비정상 시각 실행 감지\n"
        f"인스타 새벽 오발행 방지를 위해 게시하지 않았습니다."
    )
    print(f"[GUARD] {msg}")
    tg_notify(msg)


def _publish_gate() -> bool:
    """게시 직전 호출: 목표 시각 전이면 대기, 허용 구간 밖(새벽 등)이면 False."""
    state, secs = _publish_window()
    if state == "skip":
        _notify_skip()
        return False
    if state == "wait" and secs > 0:
        now, target = _now_and_target()
        print(f"[GUARD] ⏳ {target.strftime('%H:%M')} KST 공개까지 {secs / 60:.1f}분 대기 (현재 {now.strftime('%H:%M:%S')} KST)")
        time.sleep(secs)
    return True


def main():
    parser = argparse.ArgumentParser(description="MBTI×사주 릴스&숏츠 자동화 러너 (GitHub Actions / Cron용)")
    parser.add_argument("--topic", type=str, default="", help="특정 주제 (미지정 시 자동 바이럴 기획)")
    parser.add_argument("--series", type=str, default="", help="시리즈 (미지정 시 자동 기획)")
    parser.add_argument("--mbti", type=str, default="", help="MBTI (미지정 시 자동 기획)")
    parser.add_argument("--youtube-schedule-kst", type=str, default="18:30", help="YouTube Shorts KST 예약 공개 시각")
    parser.add_argument("--no-publish", action="store_true", help="게시 건너뛰기 (테스트용)")
    args = parser.parse_args()

    # GitHub Actions 스케줄 큐 지연(새벽 지연 실행) 감지 및 방어
    # GITHUB_EVENT_NAME == 'schedule'인 경우에만 18:00~21:00 KST 범위를 벗어난 심각한 지연을 차단합니다.
    # (수동 실행이나 cron-job.org 등의 workflow_dispatch는 언제든 정상 실행)
    # 새 방식: 일찍 시작해 영상을 만들고, 게시 직전에 목표 시각(18:30 KST)까지 대기. 허용 구간 밖이면 시작 단계에서 즉시 종료.
    publish_gate = None
    if os.getenv("GITHUB_EVENT_NAME", "").lower() == "schedule":
        state, secs = _publish_window()
        if state == "skip":
            _notify_skip()
            sys.exit(0)
        print(f"[GUARD] 게시 윈도우: {state} (게시까지 대기 약 {secs / 60:.1f}분) - 생성 후 목표 시각에 게시합니다.")
        publish_gate = _publish_gate

    print("=" * 65)
    print("🚀 [CRON/ACTIONS] MBTI×사주 릴스 자동화 파이프라인 가동")
    print("=" * 65)

    topic = args.topic
    series = args.series or "MBTI"
    mbti = args.mbti or "ENFP"
    element = "목(木)"
    trend_hint = ""
    title = topic or "자동 기획 릴스"

    # 1. 주제가 지정되지 않은 경우, 100만 바이럴 기획기(A/B안)에서 자동 선정
    if not topic:
        try:
            print("[1/3] 🧠 오늘의 바이럴 토픽 자동 기획 중...")
            from pipeline.topic_planner import get_planned_reels_proposals
            proposals = get_planned_reels_proposals()
            chosen_key = random.choice(["option_a", "option_b"])
            plan = proposals.get(chosen_key) or proposals.get("option_a")
            title = plan.get("title", "릴스 영상")
            series = plan.get("series", "MBTI")
            mbti = plan.get("mbti", "") or "ENFP"
            element = plan.get("element", "") or "목(木)"
            topic = plan.get("topic", "")
            trend_hint = plan.get("trend_hint", "")
            print(f"  ✅ 기획 완료: [{series}] {title} ({topic[:40]}...)")
        except Exception as e:
            print(f"  ⚠️ 자동 기획 실패({e}), 기본 MBTI 주제로 대체")
            title = "98년생 임수 INFP 결혼운"
            topic = "98년생 임수 INFP, 올해 결혼운 언제 터질까?"
            series = "MBTI"
            mbti = "INFP"

    # 2. 텔레그램 시작 알림 발송
    tg_notify(
        f"🎬 <b>[GitHub Actions] '{html.escape(title)}' 자동 제작 시작!</b>\n\n"
        f"• <b>시리즈:</b> {series} ({mbti or element})\n"
        f"• <b>주제:</b> {html.escape(topic[:80])}\n"
        f"• <b>프로세스:</b> 대본 ➔ TTS ➔ 9:16 비주얼 ➔ 영상 합성 ➔ Instagram & YouTube 게시\n\n"
        f"⏳ 약 2~3분 소요됩니다."
    )

    # 3. 원스톱 파이프라인 실행
    from main import run_pipeline

    publish = not args.no_publish
    try:
        t0 = time.time()
        res = run_pipeline(
            series=series,
            mbti=mbti,
            element=element,
            topic=topic,
            trend_hint=trend_hint,
            mock_script=False,
            mock_images=False,
            upload_gdrive=True,
            publish_insta=publish,
            publish_youtube=publish,
            youtube_schedule_kst=args.youtube_schedule_kst,
            publish_gate=publish_gate,
        )
        elapsed = time.time() - t0

        insta = res.get("instagram", {})
        youtube = res.get("youtube", {})
        drive = res.get("gdrive", {})

        insta_link = insta.get("link", "")
        yt_link = youtube.get("link", "")
        drive_link = drive.get("folder_link", "")

        msg_lines = [
            f"🎉 <b>[GitHub Actions] '{html.escape(title)}' 자동 게시 완료!</b> (총 {elapsed:.1f}초)\n"
        ]

        if insta_link:
            msg_lines.append(f"📸 <b>Instagram 릴스:</b> <a href=\"{insta_link}\">게시물 보기</a>")
        elif publish and insta.get("error"):
            msg_lines.append(f"⚠️ <b>Instagram 실패:</b> {html.escape(str(insta.get('error'))[:100])}")

        if yt_link:
            if youtube.get("scheduled"):
                msg_lines.append(f"▶️ <b>YouTube 숏츠:</b> <a href=\"{yt_link}\">영상 보기</a> (⏰ {youtube.get('scheduled_time_kst')} 자동 공개 예약)")
            else:
                msg_lines.append(f"▶️ <b>YouTube 숏츠:</b> <a href=\"{yt_link}\">영상 보기</a>")
        elif publish and youtube.get("error"):
            msg_lines.append(f"⚠️ <b>YouTube 실패:</b> {html.escape(str(youtube.get('error'))[:100])}")

        if drive_link:
            msg_lines.append(f"☁️ <b>Google Drive:</b> <a href=\"{drive_link}\">원본 폴더 열기</a>")

        tg_notify("\n".join(msg_lines))
        print("\n" + "=" * 65)
        print("🎉 [CRON/ACTIONS] 성공적으로 완료되었습니다!")
        print("=" * 65)

    except Exception as e:
        err_msg = f"❌ <b>[GitHub Actions] '{html.escape(title)}' 제작 실패:</b>\n<code>{html.escape(str(e)[:300])}</code>"
        print(f"\n[ERROR] 파이프라인 실패: {e}")
        tg_notify(err_msg)
        sys.exit(1)


if __name__ == "__main__":
    main()

