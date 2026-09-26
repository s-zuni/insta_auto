"""
Telegram Reels Automation Unified Bot.
Features:
- Single process bot running 24/7 on Railway or local
- SQLite state persistence (state.db) for pending proposals, daily schedule, and last chat ID
- In-process pipeline execution with concurrency lock (threading.Semaphore)
- Dynamic chat_id support: automatically replies to the user who sent /generate
- APScheduler for exact 17:30 KST daily proposal delivery
- Cloud credentials bootstrap from GOOGLE_SERVICE_ACCOUNT_JSON
- HTML message formatting for bulletproof Telegram delivery
- Robust 409 Conflict backoff for rolling deployments
"""
import os
import sys
import time
import json
import random
import sqlite3
import datetime
import html
import threading
import tempfile
import requests
from pathlib import Path
from dotenv import load_dotenv

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ─────────────────────────────────────────────────────────────
# 0. 클라우드 배포 자격 증명 부트스트랩 (Railway 등)
# ─────────────────────────────────────────────────────────────
def bootstrap_credentials():
    sa_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if sa_json and sa_json.strip():
        temp_dir = tempfile.gettempdir()
        sa_file = Path(temp_dir) / "service_account.json"
        sa_file.write_text(sa_json.strip(), encoding="utf-8")
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(sa_file)
        print(f"[BOOTSTRAP] GOOGLE_APPLICATION_CREDENTIALS 설정 완료: {sa_file}")

bootstrap_credentials()
load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from main import run_pipeline

try:
    import zoneinfo
    KST = zoneinfo.ZoneInfo("Asia/Seoul")
except Exception:
    KST = datetime.timezone(datetime.timedelta(hours=9))

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
DEFAULT_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite").strip()
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

MBTI_TYPES = [
    "INTJ", "INTP", "ENTJ", "ENTP",
    "INFJ", "INFP", "ENFJ", "ENFP",
    "ISTJ", "ISFJ", "ESTJ", "ESFJ",
    "ISTP", "ISFP", "ESTP", "ESFP",
]
FIVE_ELEMENTS = ["목(木)", "화(火)", "토(土)", "금(金)", "수(水)"]

DB_PATH = PROJECT_ROOT / "state.db"
PIPELINE_LOCK = threading.Semaphore(1)


# ─────────────────────────────────────────────────────────────
# 1. SQLite 상태 영속화
# ─────────────────────────────────────────────────────────────
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pending_proposals (
                callback_key TEXT PRIMARY KEY,
                series TEXT,
                mbti TEXT,
                element TEXT,
                title TEXT,
                created_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_schedule (
                schedule_date TEXT PRIMARY KEY,
                sent_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bot_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        conn.commit()

init_db()

def save_proposal(key: str, series: str, mbti: str, element: str, title: str):
    with sqlite3.connect(DB_PATH) as conn:
        now_str = datetime.datetime.now(KST).isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO pending_proposals VALUES (?, ?, ?, ?, ?, ?)",
            (key, series, mbti, element, title, now_str)
        )
        conn.commit()

def get_proposal(key: str) -> dict:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT series, mbti, element, title FROM pending_proposals WHERE callback_key = ?",
            (key,)
        ).fetchone()
        if row:
            return {"series": row[0], "mbti": row[1], "element": row[2], "title": row[3]}
    return {}

def mark_daily_sent(date_str: str):
    with sqlite3.connect(DB_PATH) as conn:
        now_str = datetime.datetime.now(KST).isoformat()
        conn.execute("INSERT OR REPLACE INTO daily_schedule VALUES (?, ?)", (date_str, now_str))
        conn.commit()

def is_daily_sent(date_str: str) -> bool:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT 1 FROM daily_schedule WHERE schedule_date = ?", (date_str,)).fetchone()
        return bool(row)

def save_last_chat_id(chat_id: str | int):
    if not chat_id:
        return
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT OR REPLACE INTO bot_settings VALUES ('last_chat_id', ?)", (str(chat_id),))
        conn.commit()

def get_last_chat_id() -> str:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT value FROM bot_settings WHERE key = 'last_chat_id'").fetchone()
        if row:
            return row[0]
    return DEFAULT_CHAT_ID


# ─────────────────────────────────────────────────────────────
# 2. 텔레그램 유틸
# ─────────────────────────────────────────────────────────────
def tg_send(text: str, reply_markup: dict = None, chat_id: str | int = None) -> dict:
    target_chat = str(chat_id) if chat_id else (DEFAULT_CHAT_ID or get_last_chat_id())
    if not target_chat:
        print("[TG][ERROR] 수신 대상 chat_id가 설정되지 않아 메시지를 보낼 수 없습니다.")
        return {}

    payload = {
        "chat_id": target_chat,
        "text": text,
        "parse_mode": "HTML",
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)

    try:
        r = requests.post(f"{API_URL}/sendMessage", json=payload, timeout=15)
        res = r.json()
        if not res.get("ok"):
            print(f"[TG][ERROR] sendMessage 실패 (status={r.status_code}): {res}")
        return res
    except Exception as e:
        print(f"[TG][ERROR] 전송 중 예외 발생: {e}")
        return {}

def tg_answer(callback_id: str, text: str = "선택 확인!"):
    try:
        requests.post(
            f"{API_URL}/answerCallbackQuery",
            json={"callback_query_id": callback_id, "text": text},
            timeout=5
        )
    except Exception:
        pass

def get_updates(offset: int) -> tuple[list, int]:
    """반환값: (updates_list, http_status_code)"""
    try:
        r = requests.get(
            f"{API_URL}/getUpdates",
            params={
                "offset": offset,
                "timeout": 20,
                "allowed_updates": json.dumps(["message", "callback_query"])
            },
            timeout=30
        )
        if r.ok:
            return r.json().get("result", []), r.status_code
        else:
            return [], r.status_code
    except Exception as e:
        print(f"[TG][WARN] 폴링 네트워크 오류: {e}")
        return [], 0


# ─────────────────────────────────────────────────────────────
# 3. Gemini 기획안 생성
# ─────────────────────────────────────────────────────────────
def gemini_plan(prompt: str) -> dict:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_KEY}"
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.8
        }
    }
    try:
        r = requests.post(url, json=body, timeout=25)
        if r.ok:
            raw = r.json()["candidates"][0]["content"]["parts"][0]["text"]
            parsed = json.loads(raw)
            if isinstance(parsed, list) and len(parsed) > 0 and isinstance(parsed[0], dict):
                return parsed[0]
            if isinstance(parsed, dict):
                return parsed
        else:
            print(f"[GEMINI][WARN] API 응답 에러 (code={r.status_code}): {r.text[:200]}")
    except Exception as e:
        print(f"[GEMINI] 기획안 생성 예외: {e}")
    return {}


def generate_and_send_proposals(chat_id: str | int = None):
    mbti_a = random.choice(MBTI_TYPES)
    el_b = random.choice(FIVE_ELEMENTS)
    print(f"[BOT] 기획안 생성 시작 -> A: {mbti_a}, B: {el_b}")
    tg_send("🔮 <b>오늘의 사주/MBTI 릴스 기획안을 생성 중입니다...</b> (약 10초)", chat_id=chat_id)

    pa = gemini_plan(
        f"인스타그램 릴스용 {mbti_a} MBTI x 사주 숏폼 대본 기획안을 단일 JSON 객체 하나로 응답하세요. "
        f'형식: {{"title":"제목(15자이내)","hook":"초반 3초 후킹 대사","summary":"전체 요약 1줄"}}'
    )
    pb = gemini_plan(
        f"인스타그램 릴스용 {el_b} 오행 운세 숏폼 대본 기획안을 단일 JSON 객체 하나로 응답하세요. "
        f'형식: {{"title":"제목(15자이내)","hook":"초반 3초 후킹 대사","summary":"전체 요약 1줄"}}'
    )

    title_a = pa.get("title", f"{mbti_a} 사주 완벽 분석")
    hook_a = pa.get("hook", f"{mbti_a}라면 이 영상 꼭 보세요!")
    sum_a = pa.get("summary", f"{mbti_a} 심리와 사주 궁합 융합 분석")

    title_b = pb.get("title", f"{el_b} 오늘의 오행 운세")
    hook_b = pb.get("hook", f"오늘 {el_b} 기운이 강한 분들 주목!")
    sum_b = pb.get("summary", f"{el_b} 오행의 흐름과 실천 팁")

    ts = int(time.time())
    ka = f"a_{mbti_a}_{ts}"
    kb = f"b_{el_b}_{ts}"

    save_proposal(ka, "MBTI", mbti_a, "", title_a)
    save_proposal(kb, "DAILY", "", el_b, title_b)

    msg = (
        f"🔮 <b>[오늘의 릴스 기획안 2가지]</b>\n\n"
        f"───────────────────\n"
        f"📌 <b>[A안] MBTI {html.escape(mbti_a)}</b>\n"
        f"• <b>제목:</b> {html.escape(title_a)}\n"
        f"• <b>후킹:</b> <i>{html.escape(hook_a)}</i>\n"
        f"• <b>요약:</b> {html.escape(sum_a)}\n\n"
        f"───────────────────\n"
        f"📌 <b>[B안] 오행 운세 {html.escape(el_b)}</b>\n"
        f"• <b>제목:</b> {html.escape(title_b)}\n"
        f"• <b>후킹:</b> <i>{html.escape(hook_b)}</i>\n"
        f"• <b>요약:</b> {html.escape(sum_b)}\n"
        f"───────────────────\n\n"
        f"👇 <b>원하는 안을 누르면 대본→TTS→영상→Drive→인스타 릴스까지 원스톱으로 제작 및 게시됩니다!</b>"
    )

    markup = {
        "inline_keyboard": [
            [{"text": f"✅ A안 — {mbti_a} 릴스 제작 & 게시", "callback_data": ka}],
            [{"text": f"✅ B안 — {el_b} 릴스 제작 & 게시", "callback_data": kb}],
            [{"text": "🔄 새 기획안 다시 생성", "callback_data": "regenerate"}],
        ]
    }
    tg_send(msg, reply_markup=markup, chat_id=chat_id)
    print(f"[BOT] 기획안 발송 완료 (A: {title_a}, B: {title_b})")


# ─────────────────────────────────────────────────────────────
# 4. In-Process 파이프라인 실행
# ─────────────────────────────────────────────────────────────
def execute_pipeline_task(plan: dict, chat_id: str | int = None):
    if not PIPELINE_LOCK.acquire(blocking=False):
        tg_send("⚠️ 현재 다른 영상 제작/업로드 작업이 진행 중입니다. 완료 후 다시 시도해 주세요.", chat_id=chat_id)
        return

    title = plan.get("title", "릴스 영상")
    series = plan.get("series", "MBTI")
    mbti = plan.get("mbti", "ENFP")
    element = plan.get("element", "목(木)")

    def _worker():
        try:
            tg_send(
                f"🎬 <b>[{html.escape(title)}]</b> 제작을 시작합니다!\n\n"
                f"1. 대본 기획 (Gemini 3.1 Flash-Lite)\n"
                f"2. 한국어 음성 합성 (TTS)\n"
                f"3. 9:16 비주얼 에셋 생성 (FLUX.1)\n"
                f"4. Ken Burns + 자막 하드코딩 영상 합성 (FFmpeg)\n"
                f"5. Google Drive 업로드\n"
                f"6. Instagram 릴스 자동 게시\n\n"
                f"⏳ 약 1~3분 소요됩니다.",
                chat_id=chat_id
            )

            res = run_pipeline(
                series=series,
                mbti=mbti,
                element=element,
                mock_script=False,
                mock_images=False,
                upload_gdrive=True,
                publish_insta=True
            )

            v_path = res.get("video_path", "")
            gdrive = res.get("gdrive", {})
            insta = res.get("instagram", {})

            lines = [
                f"🎉 <b>[{html.escape(title)}] 릴스 파이프라인 완료!</b>\n",
                f"📁 <b>로컬 파일:</b> <code>{html.escape(str(v_path))}</code>"
            ]

            if gdrive.get("folder_link"):
                lines.append(f"☁️ <b>Google Drive:</b> <a href=\"{gdrive['folder_link']}\">폴더 바로가기</a>")
            elif gdrive.get("error"):
                lines.append(f"⚠️ <b>Drive 업로드 참고:</b> {html.escape(str(gdrive['error'])[:150])}")

            if insta.get("link"):
                lines.append(f"📸 <b>Instagram 릴스:</b> <a href=\"{insta['link']}\">게시물 바로가기</a>")
            elif insta.get("error"):
                lines.append(f"⚠️ <b>Instagram 게시 참고:</b> {html.escape(str(insta['error'])[:150])}")
            elif insta.get("skipped"):
                lines.append("ℹ️ <b>Instagram:</b> 영상 직링크 미제공으로 건너뜀")

            tg_send("\n".join(lines), chat_id=chat_id)

        except Exception as e:
            print(f"[PIPELINE][ERROR] {e}")
            tg_send(f"❌ <b>영상 제작 중 오류가 발생했습니다:</b>\n<code>{html.escape(str(e)[:400])}</code>", chat_id=chat_id)
        finally:
            PIPELINE_LOCK.release()

    threading.Thread(target=_worker, daemon=True).start()


# ─────────────────────────────────────────────────────────────
# 5. 콜백 처리
# ─────────────────────────────────────────────────────────────
def handle_callback(cq: dict, chat_id: str | int = None):
    cbid = cq.get("id")
    data = cq.get("data", "")
    tg_answer(cbid, "선택 확인!")

    if data == "regenerate":
        generate_and_send_proposals(chat_id=chat_id)
        return

    plan = get_proposal(data)
    if not plan:
        tg_send("⚠️ 기획안 정보가 만료되었거나 찾을 수 없습니다. /generate 로 다시 요청하세요.", chat_id=chat_id)
        return

    execute_pipeline_task(plan, chat_id=chat_id)


# ─────────────────────────────────────────────────────────────
# 6. APScheduler 스케줄러 (매일 17:30 KST)
# ─────────────────────────────────────────────────────────────
def scheduled_daily_job():
    today_str = datetime.datetime.now(KST).strftime("%Y-%m-%d")
    print(f"[SCHEDULER] 17:30 KST 트리거 발생 (날짜: {today_str})")
    if not is_daily_sent(today_str):
        generate_and_send_proposals()
        mark_daily_sent(today_str)
    else:
        print(f"[SCHEDULER] 오늘({today_str})은 이미 발송되었습니다.")

def start_scheduler():
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger

        scheduler = BackgroundScheduler(timezone=KST)
        scheduler.add_job(
            scheduled_daily_job,
            CronTrigger(hour=17, minute=30, timezone=KST),
            id="daily_reels_proposal",
            replace_existing=True
        )
        scheduler.start()
        print("[SCHEDULER] ✅ APScheduler 가동 완료: 매일 17:30 KST 자동 발송")
    except Exception as e:
        print(f"[SCHEDULER][ERROR] 스케줄러 시작 실패: {e}")


# ─────────────────────────────────────────────────────────────
# 7. 메인 폴링 루프
# ─────────────────────────────────────────────────────────────
def run_bot():
    if not BOT_TOKEN:
        print("[ERROR] TELEGRAM_BOT_TOKEN 이 설정되지 않았습니다.")
        sys.exit(1)

    print(f"[BOT] 🚀 MBTI×사주 릴스 봇 가동 (Chat ID: {DEFAULT_CHAT_ID or '미지정 - 사용자 입력시 자동인식'})")
    start_scheduler()

    # 가동 알림 전송 (chat_id가 있는 경우)
    if DEFAULT_CHAT_ID or get_last_chat_id():
        tg_send(
            "🤖 <b>MBTI×사주 릴스 자동화 시스템 가동 완료!</b>\n\n"
            "• 매일 <b>17:30 KST</b>에 기획안 A안/B안이 자동 발송됩니다.\n"
            "• 지금 바로 받으려면 <b>/generate</b> 를 입력하세요.\n"
            "• 버튼 클릭 시 <b>대본→TTS→영상→Drive→인스타 릴스</b>가 원스톱으로 처리됩니다."
        )

    last_id = 0

    while True:
        try:
            updates, status = get_updates(last_id + 1)

            # 409 Conflict: 롤링 배포 중 이전 컨테이너가 아직 종료되지 않은 경우
            if status == 409:
                print("[TG] 다른 인스턴스와 일시적 충돌(409). 5초 대기 후 재시도...")
                time.sleep(5)
                continue

            for up in updates:
                last_id = up["update_id"]

                # 인라인 버튼 클릭 이벤트
                if "callback_query" in up:
                    cq = up["callback_query"]
                    cq_chat = cq.get("message", {}).get("chat", {}).get("id")
                    if cq_chat:
                        save_last_chat_id(cq_chat)
                    handle_callback(cq, chat_id=cq_chat)

                # 텍스트 메시지 수신 이벤트
                elif "message" in up:
                    msg = up["message"]
                    sender_chat = msg.get("chat", {}).get("id")
                    if sender_chat:
                        save_last_chat_id(sender_chat)

                    txt = msg.get("text", "").strip()

                    # /start, /help 명령어
                    if txt.startswith("/start") or txt.startswith("/help"):
                        tg_send(
                            "🔮 <b>MBTI×사주 릴스 자동화 봇</b>\n\n"
                            "/generate — 기획안 A/B안 즉시 생성\n"
                            "/status — 현재 시스템 상태 확인",
                            chat_id=sender_chat
                        )

                    # /generate 명령어 (공백이나 @봇이름 붙은 경우 모두 지원)
                    elif txt.startswith("/generate"):
                        generate_and_send_proposals(chat_id=sender_chat)

                    # /status 명령어
                    elif txt.startswith("/status"):
                        now_kst = datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")
                        tg_send(f"🟢 <b>시스템 정상 가동 중</b>\n현재 시각: {now_kst}", chat_id=sender_chat)

        except Exception as e:
            print(f"[LOOP][ERROR] {e}")

        time.sleep(1)


if __name__ == "__main__":
    run_bot()