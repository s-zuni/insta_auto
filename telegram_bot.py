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

from main import run_pipeline, run_carousel_pipeline

try:
    import zoneinfo
    KST = zoneinfo.ZoneInfo("Asia/Seoul")
except Exception:
    KST = datetime.timezone(datetime.timedelta(hours=9))

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
DEFAULT_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

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
        # 크롤러 연동(운세 도메인 topic / trend_hint) 지원을 위한 컬럼 추가 마이그레이션
        existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(pending_proposals)").fetchall()}
        for col in ("topic", "trend_hint"):
            if col not in existing_cols:
                conn.execute(f"ALTER TABLE pending_proposals ADD COLUMN {col} TEXT")
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

def save_proposal(key: str, series: str, mbti: str, element: str, title: str, topic: str = "", trend_hint: str = ""):
    with sqlite3.connect(DB_PATH) as conn:
        now_str = datetime.datetime.now(KST).isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO pending_proposals VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (key, series, mbti, element, title, now_str, topic, trend_hint)
        )
        conn.commit()

def get_proposal(key: str) -> dict:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT series, mbti, element, title, topic, trend_hint FROM pending_proposals WHERE callback_key = ?",
            (key,)
        ).fetchone()
        if row:
            return {
                "series": row[0], "mbti": row[1], "element": row[2], "title": row[3],
                "topic": row[4] or "", "trend_hint": row[5] or "",
            }
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

def _set_setting(key: str, value: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT OR REPLACE INTO bot_settings VALUES (?, ?)", (key, value))
        conn.commit()

def _get_setting(key: str) -> str:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute("SELECT value FROM bot_settings WHERE key = ?", (key,)).fetchone()
        return row[0] if row else ""

def _del_setting(key: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM bot_settings WHERE key = ?", (key,))
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
# 3. 운세 도메인 크롤링 기반 기획안 생성
# ─────────────────────────────────────────────────────────────
DOMAIN_LABELS = {"SAJU": "사주", "MBTI": "MBTI", "SHINJEOM": "신점", "JAMIDOSU": "자미두수", "TAROT": "타로", "DAILY": "오행 운세"}


def generate_and_send_proposals(chat_id: str | int = None):
    from pipeline.topic_crawler import get_crawled_reels_proposals

    print("[BOT] 운세 도메인(사주/MBTI/신점/자미두수/타로) 실시간 크롤링 기반 기획안 생성 시작")
    tg_send("🔮 <b>사주·MBTI·신점·자미두수·타로 실시간 화제를 크롤링해 기획안을 생성 중입니다...</b> (약 10~15초)", chat_id=chat_id)

    proposals = get_crawled_reels_proposals()
    pa = proposals.get("option_a", {})
    pb = proposals.get("option_b", {})

    series_a = pa.get("series", "MBTI")
    series_b = pb.get("series", "SAJU")
    mbti_a = pa.get("mbti", "")
    mbti_b = pb.get("mbti", "")
    topic_a = pa.get("topic", "")
    topic_b = pb.get("topic", "")
    trend_a = pa.get("trend_hint", "")
    trend_b = pb.get("trend_hint", "")
    title_a = pa.get("title", f"{DOMAIN_LABELS.get(series_a, series_a)} 릴스")
    title_b = pb.get("title", f"{DOMAIN_LABELS.get(series_b, series_b)} 릴스")
    hook_a = pa.get("hook", "")
    hook_b = pb.get("hook", "")
    sum_a = pa.get("summary", "")
    sum_b = pb.get("summary", "")

    ts = int(time.time())
    ka = f"a_{series_a}_{ts}"
    kb = f"b_{series_b}_{ts}"

    save_proposal(ka, series_a, mbti_a, "", title_a, topic=topic_a, trend_hint=trend_a)
    save_proposal(kb, series_b, mbti_b, "", title_b, topic=topic_b, trend_hint=trend_b)

    label_a = DOMAIN_LABELS.get(series_a, series_a) + (f" {mbti_a}" if mbti_a else "")
    label_b = DOMAIN_LABELS.get(series_b, series_b) + (f" {mbti_b}" if mbti_b else "")

    msg = (
        f"🔮 <b>[릴스·캐러셀 기획안 2가지 - 실시간 운세 트렌드 기반]</b>\n\n"
        f"───────────────────\n"
        f"📌 <b>[A안] {html.escape(label_a)}</b>\n"
        + (f"• <b>실시간 화제:</b> {html.escape(trend_a)}\n" if trend_a else "")
        + f"• <b>제목:</b> {html.escape(title_a)}\n"
        f"• <b>후킹:</b> <i>{html.escape(hook_a)}</i>\n"
        f"• <b>요약:</b> {html.escape(sum_a)}\n\n"
        f"───────────────────\n"
        f"📌 <b>[B안] {html.escape(label_b)}</b>\n"
        + (f"• <b>실시간 화제:</b> {html.escape(trend_b)}\n" if trend_b else "")
        + f"• <b>제목:</b> {html.escape(title_b)}\n"
        f"• <b>후킹:</b> <i>{html.escape(hook_b)}</i>\n"
        f"• <b>요약:</b> {html.escape(sum_b)}\n"
        f"───────────────────\n\n"
        f"👇 <b>원하는 안의 🚀 버튼을 누르면 릴스(Instagram·YouTube)와 캐러셀이 연달아 자동 제작·게시됩니다!</b>"
    )

    markup = {
        "inline_keyboard": [
            [{"text": f"🚀 A안 — {label_a} 릴스+캐러셀 한 번에 게시", "callback_data": f"both:{ka}"}],
            [{"text": f"🚀 B안 — {label_b} 릴스+캐러셀 한 번에 게시", "callback_data": f"both:{kb}"}],
            [
                {"text": "🎬 A안 릴스만", "callback_data": ka},
                {"text": "🖼 A안 캐러셀만", "callback_data": f"car:{ka}"},
            ],
            [
                {"text": "🎬 B안 릴스만", "callback_data": kb},
                {"text": "🖼 B안 캐러셀만", "callback_data": f"car:{kb}"},
            ],
            [{"text": "✍️ 둘 다 별로예요 — 직접 주제 입력", "callback_data": "custom_topic"}],
            [{"text": "🔄 새 기획안 다시 생성", "callback_data": "regenerate"}],
        ]
    }
    tg_send(msg, reply_markup=markup, chat_id=chat_id)
    print(f"[BOT] 기획안 발송 완료 (A: [{series_a}] {title_a} / B: [{series_b}] {title_b})")


# ─────────────────────────────────────────────────────────────
# 4. In-Process 파이프라인 실행
# ─────────────────────────────────────────────────────────────
def _reels_job(plan: dict, chat_id: str | int = None):
    """릴스 제작+게시 본문 (락은 호출부가 관리). 실패해도 예외를 밖으로 던지지 않고 텔레그램으로 알린다."""
    title = plan.get("title", "릴스 영상")
    series = plan.get("series", "MBTI")
    mbti = plan.get("mbti", "") or "ENFP"
    element = plan.get("element", "") or "목(木)"
    topic = plan.get("topic", "")
    trend_hint = plan.get("trend_hint", "")

    try:
        tg_send(
            f"🎬 <b>[{html.escape(title)}]</b> 제작을 시작합니다!\n\n"
            f"1. 대본 기획 (Gemini 3.1 Flash-Lite)\n"
            f"2. 한국어 음성 합성 (TTS)\n"
            f"3. 16:9 비주얼 생성 및 릴스 프레임 합성\n"
            f"4. Ken Burns + 자막 하드코딩 영상 합성 (FFmpeg)\n"
            f"5. Google Drive 업로드\n"
            f"6. Instagram 릴스 자동 게시\n"
            f"7. YouTube Shorts 자동 게시\n\n"
            f"⏳ 약 1~3분 소요됩니다.",
            chat_id=chat_id
        )

        res = run_pipeline(
            series=series,
            mbti=mbti,
            element=element,
            topic=topic,
            trend_hint=trend_hint,
            mock_script=False,
            mock_images=False,
            upload_gdrive=True,
            publish_insta=True,
            publish_youtube=True
        )

        v_path = res.get("video_path", "")
        gdrive = res.get("gdrive", {})
        insta = res.get("instagram", {})
        youtube = res.get("youtube", {})
        placeholder_count = res.get("placeholder_scene_count", 0)
        total_scenes = res.get("total_scene_count", 0)

        lines = [
            f"🎉 <b>[{html.escape(title)}] 릴스 파이프라인 완료!</b>\n",
            f"📁 <b>로컬 파일:</b> <code>{html.escape(str(v_path))}</code>"
        ]

        if res.get("publish_blocked"):
            lines.append("⛔ <b>자동 게시 중단:</b> 플레이스홀더 씬이 있어 Instagram/YouTube 게시를 건너뛰었습니다. 이미지 엔진 상태 확인 후 재시도하세요.")
        if placeholder_count:
            lines.append(
                f"⚠️ <b>이미지 경고:</b> {placeholder_count}/{total_scenes}개 씬에서 "
                f"AI 이미지 생성이 실패해 단색 배경(플레이스홀더)으로 대체되었습니다."
            )

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

        if youtube.get("link"):
            lines.append(f"▶️ <b>YouTube Shorts:</b> <a href=\"{youtube['link']}\">숏츠 바로가기</a>")
        elif youtube.get("error"):
            lines.append(f"⚠️ <b>YouTube Shorts 참고:</b> {html.escape(str(youtube['error'])[:150])}")

        tg_send("\n".join(lines), chat_id=chat_id)

    except Exception as e:
        print(f"[PIPELINE][ERROR] {e}")
        tg_send(f"❌ <b>영상 제작 중 오류가 발생했습니다:</b>\n<code>{html.escape(str(e)[:400])}</code>", chat_id=chat_id)


def _carousel_job(plan: dict, chat_id: str | int = None):
    """캐러셀 제작+게시 본문 (락은 호출부가 관리). 실패해도 예외를 밖으로 던지지 않고 텔레그램으로 알린다."""
    title = plan.get("title", "캐러셀")

    try:
        tg_send(
            f"🖼 <b>[{html.escape(title)}]</b> 캐러셀 제작을 시작합니다!\n"
            f"대본 → 표지 비주얼 → 슬라이드 렌더 → 호스팅 → Instagram 게시\n⏳ 약 1분 소요됩니다.",
            chat_id=chat_id,
        )
        res = run_carousel_pipeline(
            series=plan.get("series", "MBTI"),
            mbti=plan.get("mbti", "") or "ENFP",
            element=plan.get("element", "") or "목(木)",
            topic=plan.get("topic", ""),
            trend_hint=plan.get("trend_hint", ""),
            publish_insta=True,
        )
        insta = res.get("instagram", {})
        lines = [f"🎉 <b>[{html.escape(title)}] 캐러셀 완료!</b> ({len(res.get('slide_paths', []))}장)\n"]
        if insta.get("link"):
            lines.append(f"📸 <b>Instagram 캐러셀:</b> <a href=\"{insta['link']}\">게시물 바로가기</a>")
        elif insta.get("error"):
            lines.append(f"⚠️ <b>Instagram 게시 참고:</b> {html.escape(str(insta['error'])[:200])}")
        elif insta.get("skipped"):
            lines.append("⛔ <b>자동 게시 중단:</b> 표지 이미지 생성에 실패해 게시를 건너뛰었습니다.")
        tg_send("\n".join(lines), chat_id=chat_id)
    except Exception as e:
        print(f"[CAROUSEL][ERROR] {e}")
        tg_send(f"❌ <b>캐러셀 제작 중 오류:</b>\n<code>{html.escape(str(e)[:400])}</code>", chat_id=chat_id)


def _run_locked(jobs, plan: dict, chat_id: str | int = None):
    """PIPELINE_LOCK을 한 번 잡고 jobs를 순서대로 백그라운드 실행합니다 (한 작업이 실패해도 다음 작업은 진행)."""
    if not PIPELINE_LOCK.acquire(blocking=False):
        tg_send("⚠️ 현재 다른 제작/업로드 작업이 진행 중입니다. 완료 후 다시 시도해 주세요.", chat_id=chat_id)
        return

    def _worker():
        try:
            for job in jobs:
                job(plan, chat_id)
        finally:
            PIPELINE_LOCK.release()

    threading.Thread(target=_worker, daemon=True).start()


def execute_pipeline_task(plan: dict, chat_id: str | int = None):
    _run_locked([_reels_job], plan, chat_id)


def execute_carousel_task(plan: dict, chat_id: str | int = None):
    _run_locked([_carousel_job], plan, chat_id)


def execute_both_task(plan: dict, chat_id: str | int = None):
    """한 번의 선택으로 릴스(Instagram+YouTube)와 캐러셀을 연달아 제작·게시합니다."""
    tg_send(
        f"🚀 <b>[{html.escape(plan.get('title', '기획안'))}]</b> 릴스 + 캐러셀을 연달아 제작·게시합니다.\n"
        f"순서: 릴스 → 캐러셀 (총 약 3~5분)",
        chat_id=chat_id,
    )
    _run_locked([_reels_job, _carousel_job], plan, chat_id)


# ─────────────────────────────────────────────────────────────
# 4-2. Threads 전용 텍스트 글 (릴스/캐러셀과 별개 콘텐츠)
# ─────────────────────────────────────────────────────────────
def _threads_token() -> str:
    """주기 갱신으로 DB에 저장된 토큰을 우선 사용하고, 없으면 .env 값을 씁니다."""
    return _get_setting("threads_token") or os.getenv("THREADS_ACCESS_TOKEN", "")


def _recent_threads_posts() -> list:
    try:
        return json.loads(_get_setting("threads_recent") or "[]")
    except Exception:
        return []


THREADS_SLOTS = {"morning": (7, 30), "afternoon": (14, 0), "evening": (18, 0)}  # KST
THREADS_AUTO_POST = os.getenv("THREADS_AUTO_POST", "true").strip().lower() not in ("0", "false", "no")


def _threads_cta_slot(date_str: str) -> str:
    """하루 3개 글 중 CTA를 붙일 1개 슬롯을 그날 처음 호출될 때 무작위로 정해 고정합니다."""
    key = f"threads_cta_slot:{date_str}"
    slot = _get_setting(key)
    if slot not in THREADS_SLOTS:
        slot = random.choice(list(THREADS_SLOTS))
        _set_setting(key, slot)
    return slot


def _remember_threads_post(posts: list):
    recent = ([posts[0]] + _recent_threads_posts())[:10]
    _set_setting("threads_recent", json.dumps(recent, ensure_ascii=False))


def _format_thread_preview(thread) -> str:
    parts = []
    for i, p in enumerate(thread.posts):
        label = "본문" if i == 0 else f"답글 {i}"
        parts.append(f"<b>[{label}]</b>\n{html.escape(p)}")
    return "\n\n".join(parts)


def propose_threads_post(chat_id: str | int = None):
    """수동 /thread: Threads 타래 초안(CTA 없음)을 생성해 텔레그램으로 보내고, 승인 버튼을 붙입니다."""
    from pipeline.threads_content import generate_threads_thread

    tg_send("🧵 <b>Threads 타래 초안을 생성 중입니다...</b> (약 20~40초)", chat_id=chat_id)
    try:
        thread = generate_threads_thread(recent_posts=_recent_threads_posts())
    except Exception as e:
        tg_send(f"❌ 초안 생성 실패: {html.escape(str(e))}", chat_id=chat_id)
        return
    key = f"thr{int(time.time())}"
    _set_setting(f"thread_draft:{key}", json.dumps({"posts": thread.posts, "topic_tag": thread.topic_tag}, ensure_ascii=False))
    markup = {"inline_keyboard": [
        [{"text": "🧵 이대로 게시", "callback_data": f"thr_post:{key}"}],
        [{"text": "🔄 다시 생성", "callback_data": "thr_regen"}],
    ]}
    tg_send(
        f"🧵 <b>Threads 초안</b> [{thread.category}] 토픽 #{html.escape(thread.topic_tag)}\n\n{_format_thread_preview(thread)}",
        reply_markup=markup,
        chat_id=chat_id,
    )


def publish_threads_draft(key: str, chat_id: str | int = None):
    from pipeline.threads_publisher import publish_thread

    raw = _get_setting(f"thread_draft:{key}")
    if not raw:
        tg_send("⚠️ 초안이 만료되었거나 이미 게시되었습니다. /thread 로 다시 생성하세요.", chat_id=chat_id)
        return
    draft = json.loads(raw)
    _del_setting(f"thread_draft:{key}")  # 중복 클릭으로 이중 게시되지 않도록 먼저 제거
    result = publish_thread(draft["posts"], topic_tag=draft.get("topic_tag"), access_token=_threads_token() or None)
    if result.get("ids"):
        _remember_threads_post(draft["posts"])
    if "error" in result:
        tg_send(f"❌ <b>Threads 게시 실패</b>\n{html.escape(str(result['error']))}", chat_id=chat_id)
        return
    tg_send(f"✅ <b>Threads 게시 완료!</b>\n{html.escape(result.get('permalink') or result.get('id', ''))}", chat_id=chat_id)


def threads_scheduled_job(slot: str):
    """하루 3회(07:30/14:00/18:00 KST) Threads 타래를 생성해 게시합니다. 3개 중 1개에만 CTA 답글을 붙입니다."""
    from pipeline.threads_content import generate_threads_thread
    from pipeline.threads_publisher import publish_thread

    date_str = datetime.datetime.now(KST).strftime("%Y-%m-%d")
    done_key = f"threads_done:{date_str}:{slot}"
    if _get_setting(done_key):
        print(f"[THREADS] {date_str} {slot} 슬롯은 이미 처리되었습니다.")
        return
    if not (os.getenv("THREADS_USER_ID") and _threads_token()):
        print("[THREADS][WARN] THREADS_USER_ID/THREADS_ACCESS_TOKEN 미설정 - 건너뜀")
        return
    _set_setting(done_key, "1")  # 재시작/중복 트리거로 이중 게시되지 않도록 시도 전에 표시

    with_cta = (slot == _threads_cta_slot(date_str))
    try:
        thread = generate_threads_thread(slot=slot, with_cta=with_cta, recent_posts=_recent_threads_posts())
    except Exception as e:
        print(f"[THREADS][ERROR] 생성 실패: {e}")
        tg_send(f"❌ Threads {slot} 글 생성 실패: {html.escape(str(e))}")
        return

    if not THREADS_AUTO_POST:
        key = f"thr{int(time.time())}"
        _set_setting(f"thread_draft:{key}", json.dumps({"posts": thread.posts, "topic_tag": thread.topic_tag}, ensure_ascii=False))
        markup = {"inline_keyboard": [[{"text": "🧵 이대로 게시", "callback_data": f"thr_post:{key}"}]]}
        tg_send(f"🧵 <b>Threads {slot} 초안</b> [{thread.category}]\n\n{_format_thread_preview(thread)}", reply_markup=markup)
        return

    result = publish_thread(thread.posts, topic_tag=thread.topic_tag, access_token=_threads_token() or None)
    if result.get("ids"):
        _remember_threads_post(thread.posts)
    if "error" in result:
        tg_send(f"❌ <b>Threads {slot} 게시 실패</b>\n{html.escape(str(result['error']))}")
        return
    cta_note = " · CTA 포함" if thread.has_cta else ""
    tg_send(
        f"✅ <b>Threads {slot} 게시 완료</b> [{thread.category}{cta_note}]\n"
        f"{html.escape(result.get('permalink') or result.get('id', ''))}"
    )


def refresh_threads_token_job():
    """Threads 장기 토큰(60일)을 주기적으로 연장해 DB에 저장합니다."""
    from pipeline.threads_publisher import refresh_long_lived_token

    token = _threads_token()
    if not token:
        return
    out = refresh_long_lived_token(token)
    if "access_token" in out:
        _set_setting("threads_token", out["access_token"])
        print("[THREADS] 토큰 갱신 완료")
    else:
        print(f"[THREADS][WARN] 토큰 갱신 실패: {out.get('error')}")
        try:
            tg_send(f"⚠️ Threads 토큰 갱신 실패: {html.escape(str(out.get('error')))}\n만료 전에 토큰을 재발급해 주세요.")
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────
# 5. 콜백 처리
# ─────────────────────────────────────────────────────────────
def begin_custom_topic(chat_id: str | int):
    _set_setting(f"await_topic:{chat_id}", "1")
    tg_send(
        "✍️ <b>만들고 싶은 주제를 한 줄로 보내주세요.</b>\n"
        "예) <code>INFJ가 연애에서 자꾸 도망치는 이유</code>, <code>타로로 보는 이번 달 재물운</code>\n"
        "• MBTI 유형이 들어 있으면 MBTI 시리즈, 타로/신점/자미두수 키워드가 있으면 해당 시리즈, 그 외는 사주 시리즈로 제작돼요.\n"
        "• 취소: /cancel",
        chat_id=chat_id,
    )


def handle_custom_topic_text(text: str, chat_id: str | int):
    """사용자가 입력한 주제를 분류해 저장하고 릴스/캐러셀 중 포맷을 고르게 합니다."""
    from pipeline.topic_crawler import classify_custom_topic

    info = classify_custom_topic(text)
    key = f"u_{info['series']}_{int(time.time())}"
    title = text.strip()[:15]
    save_proposal(key, info["series"], info["mbti"], "", title, topic=info["topic"], trend_hint="")

    label = DOMAIN_LABELS.get(info["series"], info["series"]) + (f" {info['mbti']}" if info["mbti"] else "")
    markup = {
        "inline_keyboard": [
            [{"text": "🚀 릴스+캐러셀 한 번에 게시", "callback_data": f"both:{key}"}],
            [{"text": "🎬 릴스만", "callback_data": key}, {"text": "🖼 캐러셀만", "callback_data": f"car:{key}"}],
        ]
    }
    tg_send(
        f"📝 <b>직접 입력 주제</b>\n• 시리즈: <b>{html.escape(label)}</b>\n• 주제: {html.escape(info['topic'])}\n\n🚀 버튼을 누르면 릴스와 캐러셀이 모두 게시돼요.",
        reply_markup=markup,
        chat_id=chat_id,
    )


def handle_callback(cq: dict, chat_id: str | int = None):
    cbid = cq.get("id")
    data = cq.get("data", "")
    tg_answer(cbid, "선택 확인!")

    if data == "regenerate":
        generate_and_send_proposals(chat_id=chat_id)
        return

    if data == "custom_topic":
        begin_custom_topic(chat_id)
        return

    if data == "thr_regen":
        propose_threads_post(chat_id=chat_id)
        return

    if data.startswith("thr_post:"):
        publish_threads_draft(data[len("thr_post:"):], chat_id=chat_id)
        return

    as_carousel = data.startswith("car:")
    as_both = data.startswith("both:")
    key = data[4:] if as_carousel else data[5:] if as_both else data
    plan = get_proposal(key)
    if not plan:
        tg_send("⚠️ 기획안 정보가 만료되었거나 찾을 수 없습니다. /generate 로 다시 요청하세요.", chat_id=chat_id)
        return

    if as_both:
        execute_both_task(plan, chat_id=chat_id)
    elif as_carousel:
        execute_carousel_task(plan, chat_id=chat_id)
    else:
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
        # 게시 24h/72h/7d 시점 성과 스냅샷 수집 (매시간, 대상 없으면 즉시 종료)
        def _collect_insights_job():
            try:
                from pipeline.insights import collect_due_insights
                collect_due_insights()
            except Exception as e:
                print(f"[INSIGHTS][ERROR] {e}")

        scheduler.add_job(
            _collect_insights_job,
            CronTrigger(minute=10, timezone=KST),
            id="collect_insights",
            replace_existing=True
        )
        for _slot, (_h, _m) in THREADS_SLOTS.items():
            scheduler.add_job(
                threads_scheduled_job,
                CronTrigger(hour=_h, minute=_m, timezone=KST),
                args=[_slot],
                id=f"threads_post_{_slot}",
                replace_existing=True,
                misfire_grace_time=900,
                coalesce=True,
            )
        scheduler.add_job(
            refresh_threads_token_job,
            CronTrigger(day_of_week="mon", hour=4, minute=0, timezone=KST),
            id="refresh_threads_token",
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
                            "/topic 주제 — 직접 주제 지정 (릴스/캐러셀 선택)\n"
                            "/thread — Threads 타래 초안 수동 생성 (승인 후 게시)\n"
                            "/insights — 성과 리포트\n"
                            "/status — 현재 시스템 상태 확인",
                            chat_id=sender_chat
                        )

                    # /generate 명령어 (공백이나 @봇이름 붙은 경우 모두 지원)
                    elif txt.startswith("/generate"):
                        generate_and_send_proposals(chat_id=sender_chat)

                    # /topic [주제] — 주제를 바로 지정하거나, 인자가 없으면 다음 메시지를 주제로 받음
                    elif txt.startswith("/topic"):
                        arg = txt[len("/topic"):].split(None, 1)
                        arg_text = arg[1].strip() if len(arg) > 1 and not arg[0].startswith("@") else ""
                        if arg_text:
                            handle_custom_topic_text(arg_text, sender_chat)
                        else:
                            begin_custom_topic(sender_chat)

                    elif txt.startswith("/thread"):
                        propose_threads_post(chat_id=sender_chat)

                    elif txt.startswith("/cancel"):
                        _del_setting(f"await_topic:{sender_chat}")
                        tg_send("취소했어요.", chat_id=sender_chat)

                    # /insights — 성과 리포트
                    elif txt.startswith("/insights"):
                        from pipeline.insights import collect_due_insights, weekly_report
                        try:
                            collect_due_insights()
                        except Exception as e:
                            print(f"[INSIGHTS][ERROR] {e}")
                        tg_send(weekly_report(), chat_id=sender_chat)

                    # 주제 입력 대기 중인 상태의 일반 텍스트 = 사용자 지정 주제
                    elif txt and not txt.startswith("/") and _get_setting(f"await_topic:{sender_chat}"):
                        _del_setting(f"await_topic:{sender_chat}")
                        handle_custom_topic_text(txt, sender_chat)

                    # /status 명령어
                    elif txt.startswith("/status"):
                        now_kst = datetime.datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")
                        tg_send(f"🟢 <b>시스템 정상 가동 중</b>\n현재 시각: {now_kst}", chat_id=sender_chat)

        except Exception as e:
            print(f"[LOOP][ERROR] {e}")

        time.sleep(1)


if __name__ == "__main__":
    run_bot()