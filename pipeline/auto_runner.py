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
    github_event = os.getenv("GITHUB_EVENT_NAME", "").lower()
    if github_event == "schedule":
        try:
            import datetime
            try:
                import zoneinfo
                kst_tz = zoneinfo.ZoneInfo("Asia/Seoul")
            except Exception:
                kst_tz = datetime.timezone(datetime.timedelta(hours=9))
            now_kst = datetime.datetime.now(kst_tz)
            # 원래 18:28 KST 스케줄: 18:00 ~ 20:30 허용
            if now_kst.hour < 18 or now_kst.hour >= 21:
                warn_msg = (
                    f"⚠️ <b>[GitHub Actions 지연 감지] 새벽 오발행 차단</b>\n\n"
                    f"• 원래 목표: <b>18:28 KST</b>\n"
                    f"• 실제 러너 시작: <b>{now_kst.strftime('%H:%M:%S')} KST</b>\n"
                    f"• 사유: GitHub 무료 러너 대기열 병목으로 지연 발생\n\n"
                    f"인스타그램 피드 및 숏츠 새벽 오발행을 방지하기 위해 작업을 안전하게 건너뜁니다.\n"
                    f"👉 정시(18:28) 확정 발행을 위해 <b>cron-job.org</b> 웹훅 연동을 권장합니다."
                )
                print(f"[GUARD] {warn_msg}")
                tg_notify(warn_msg)
                sys.exit(0)
        except Exception as e:
            print(f"[GUARD][WARN] 지연 검사 중 오류(무시하고 계속): {e}")

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

