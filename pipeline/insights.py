"""
Instagram Insights 수집 + 성과 기반 주제 피드백.

- published_posts : 게시한 릴스/캐러셀의 메타데이터(시리즈, 주제, 제목, 훅 ...)
- post_insights   : 게시 후 24h / 72h / 7d 시점 성과 스냅샷
- get_top_examples: 성과 상위 게시물을 기획안 프롬프트의 '참고 예시'로 제공 (도메인 선택은 건드리지 않음)

state.db(텔레그램 봇과 동일 파일)를 공유합니다. instagram_manage_insights 권한이 필요합니다.
"""
import datetime
import json
import os
import re
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "state.db"
GRAPH_VERSION = os.getenv("INSTAGRAM_GRAPH_VERSION", "v21.0")

SNAPSHOT_WINDOWS_H = (24, 72, 168)
# 계정/버전에 따라 일부 지표는 지원되지 않으므로 하나씩 요청하고 실패한 것은 건너뜁니다.
CANDIDATE_METRICS = ["reach", "views", "plays", "likes", "comments", "saved", "shares",
                     "total_interactions", "ig_reels_avg_watch_time", "follows", "profile_visits"]
# 예시를 신뢰하려면 최소 이 개수 이상의 72h 이상 지난 게시물이 있어야 합니다.
MIN_POSTS_FOR_EXAMPLES = int(os.getenv("INSIGHTS_MIN_POSTS", "5"))


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS published_posts (
            media_id TEXT PRIMARY KEY,
            format TEXT,
            series TEXT,
            mbti TEXT,
            topic TEXT,
            title TEXT,
            hook TEXT,
            trend_hint TEXT,
            permalink TEXT,
            published_at TEXT
        )
    """)
    # A/B 변형 기록(씬 수, 공유 CTA 유무, TTS 속도 등). 기존 DB는 컬럼만 추가한다.
    if "variant_json" not in {r[1] for r in conn.execute("PRAGMA table_info(published_posts)")}:
        conn.execute("ALTER TABLE published_posts ADD COLUMN variant_json TEXT")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS post_insights (
            media_id TEXT,
            window_h INTEGER,
            collected_at TEXT,
            metrics_json TEXT,
            score REAL,
            PRIMARY KEY (media_id, window_h)
        )
    """)
    return conn


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def record_post(media_id: str, fmt: str, series: str = "", mbti: str = "", topic: str = "",
                title: str = "", hook: str = "", trend_hint: str = "", permalink: str = "",
                variant: Optional[Dict[str, Any]] = None) -> None:
    """게시 직후 호출해 메타데이터를 저장합니다. fmt: 'reel' | 'carousel'
    variant: 어떤 변형으로 만들었는지(예: {"scenes": 9, "share_cta": True, "tts_rate": "+14%"}). 성과 비교용."""
    if not media_id:
        return
    conn = _conn()
    try:
        with conn:
            conn.execute(
                "INSERT OR REPLACE INTO published_posts "
                "(media_id, format, series, mbti, topic, title, hook, trend_hint, permalink, published_at, variant_json) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (str(media_id), fmt, series, mbti, topic, title, hook, trend_hint, permalink, _now().isoformat(),
                 json.dumps(variant or {}, ensure_ascii=False)),
            )
    finally:
        conn.close()


def compute_score(metrics: Dict[str, float]) -> float:
    """참여도 점수 = (저장*3 + 공유*3 + 댓글*2 + 좋아요) / 도달 * 100"""
    reach = max(float(metrics.get("reach", 0) or 0), 1.0)
    weighted = (
        3 * float(metrics.get("saved", 0) or 0)
        + 3 * float(metrics.get("shares", 0) or 0)
        + 2 * float(metrics.get("comments", 0) or 0)
        + float(metrics.get("likes", 0) or 0)
    )
    return round(weighted / reach * 100, 3)


def fetch_media_insights(media_id: str, access_token: Optional[str] = None) -> Dict[str, float]:
    """지원되는 지표만 모아 반환합니다 (실패한 지표는 건너뜀)."""
    token = access_token or os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
    out: Dict[str, float] = {}
    for metric in CANDIDATE_METRICS:
        try:
            r = requests.get(
                f"https://graph.facebook.com/{GRAPH_VERSION}/{media_id}/insights",
                params={"metric": metric, "access_token": token},
                timeout=15,
            )
            if not r.ok:
                continue
            data = r.json().get("data", [])
            if not data:
                continue
            item = data[0]
            val = None
            if item.get("values"):
                val = item["values"][0].get("value")
            elif "total_value" in item:
                val = item["total_value"].get("value")
            if isinstance(val, (int, float)):
                out[metric] = float(val)
        except requests.RequestException:
            continue
    return out


def collect_due_insights() -> int:
    """24h/72h/7d 시점이 지났는데 아직 스냅샷이 없는 게시물의 성과를 수집합니다. 저장한 스냅샷 수를 반환."""
    saved = 0
    conn = _conn()
    try:
        posts = conn.execute("SELECT media_id, published_at FROM published_posts").fetchall()
        for p in posts:
            age_h = (_now() - datetime.datetime.fromisoformat(p["published_at"])).total_seconds() / 3600
            for window in SNAPSHOT_WINDOWS_H:
                if age_h < window:
                    continue
                exists = conn.execute(
                    "SELECT 1 FROM post_insights WHERE media_id=? AND window_h=?", (p["media_id"], window)
                ).fetchone()
                if exists:
                    continue
                metrics = fetch_media_insights(p["media_id"])
                if not metrics:
                    print(f"[INSIGHTS] {p['media_id']} {window}h 지표를 가져오지 못했습니다(권한/지연 가능).")
                    break
                metrics["age_h_at_collect"] = round(age_h, 1)  # 창(24/72/168h)보다 훨씬 늦게 수집됐는지 판별용
                with conn:
                    conn.execute(
                        "INSERT OR REPLACE INTO post_insights VALUES (?,?,?,?,?)",
                        (p["media_id"], window, _now().isoformat(), json.dumps(metrics), compute_score(metrics)),
                    )
                saved += 1
                print(f"[INSIGHTS] {p['media_id']} {window}h 스냅샷 저장 (score={compute_score(metrics)})")
    finally:
        conn.close()
    return saved


def _latest_scored_posts() -> List[sqlite3.Row]:
    """게시물별로 가장 늦은 시점(72h 이상)의 스냅샷 점수를 가져옵니다."""
    conn = _conn()
    try:
        return conn.execute("""
            SELECT p.*, i.window_h, i.score, i.metrics_json
            FROM published_posts p
            JOIN post_insights i ON i.media_id = p.media_id
            WHERE i.window_h >= 72
              AND i.window_h = (SELECT MAX(window_h) FROM post_insights WHERE media_id = p.media_id)
            ORDER BY i.score DESC
        """).fetchall()
    finally:
        conn.close()


def get_top_examples(n: int = 3, fmt: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    성과 상위 게시물 n개(제목/훅/시리즈/점수). 평가 가능한 게시물이 MIN_POSTS_FOR_EXAMPLES개 미만이면 빈 리스트.
    """
    rows = _latest_scored_posts()
    if fmt:
        rows = [r for r in rows if r["format"] == fmt]
    if len(rows) < MIN_POSTS_FOR_EXAMPLES:
        return []
    return [
        {"title": r["title"], "hook": r["hook"], "series": r["series"], "topic": r["topic"], "score": r["score"]}
        for r in rows[:n]
    ]


def format_examples_for_prompt(examples: List[Dict[str, Any]]) -> str:
    if not examples:
        return ""
    lines = ["[우리 계정에서 반응(저장·공유·댓글)이 좋았던 과거 게시물 - 톤과 훅 방식만 참고하고 그대로 베끼지 마세요]"]
    for e in examples:
        lines.append(f'- ({e["series"]}) 제목: "{e["title"]}" / 훅: "{e["hook"]}"')
    return "\n".join(lines)


def variant_summary(key: str, rows: Optional[List[sqlite3.Row]] = None, fmt: Optional[str] = None) -> Dict[str, Dict[str, float]]:
    """variant_json의 key 값별 평균 score와 게시물 수. 예: variant_summary('share_cta') -> {'True': {...}, 'False': {...}}
    값이 없는 게시물(구버전)은 제외한다."""
    rows = _latest_scored_posts() if rows is None else rows
    groups: Dict[str, List[float]] = {}
    for r in rows:
        if fmt and r["format"] != fmt:
            continue
        try:
            v = json.loads(r["variant_json"] or "{}")
        except (TypeError, ValueError):
            continue
        if key not in v:
            continue
        groups.setdefault(str(v[key]), []).append(r["score"])
    return {k: {"avg_score": round(sum(s) / len(s), 3), "n": len(s)} for k, s in groups.items()}


def weekly_report(days: int = 7) -> str:
    """텔레그램용 요약 리포트(HTML)."""
    rows = _latest_scored_posts()
    cutoff = _now() - datetime.timedelta(days=days)
    recent = [r for r in rows if datetime.datetime.fromisoformat(r["published_at"]) >= cutoff]
    conn = _conn()
    try:
        total_posts = conn.execute("SELECT COUNT(*) FROM published_posts").fetchone()[0]
    finally:
        conn.close()

    if not rows:
        return (f"📊 <b>Insights 리포트</b>\n아직 집계된 성과가 없습니다. (기록된 게시물 {total_posts}개, "
                f"게시 후 72시간이 지나면 집계됩니다)")

    def line(r) -> str:
        m = json.loads(r["metrics_json"])
        return (f"• [{r['format']}/{r['series']}] {r['title'][:20]} — score {r['score']} "
                f"(도달 {int(m.get('reach', 0))}, 저장 {int(m.get('saved', 0))}, 공유 {int(m.get('shares', 0))})")

    by_series: Dict[str, List[float]] = {}
    for r in rows:
        by_series.setdefault(r["series"] or "?", []).append(r["score"])

    out = [f"📊 <b>Insights 리포트</b> (집계 {len(rows)}개 / 전체 {total_posts}개)", ""]
    out.append("<b>🏆 상위 3</b>")
    out += [line(r) for r in rows[:3]]
    if len(rows) > 3:
        out += ["", "<b>⚠️ 하위</b>"] + [line(r) for r in rows[max(3, len(rows) - 3):]]
    out += ["", "<b>📚 시리즈 평균 score</b>"]
    for s, v in sorted(by_series.items(), key=lambda kv: -sum(kv[1]) / len(kv[1])):
        out.append(f"• {s}: {sum(v) / len(v):.2f} ({len(v)}개)")
    ab_lines = []
    for key, label in (("share_cta", "공유 CTA"), ("scene_bucket", "씬 수"), ("tts_rate", "TTS 속도")):
        summ = variant_summary(key, rows, fmt="reel")
        if len(summ) > 1:  # 비교할 변형이 2개 이상일 때만
            ab_lines.append(f"• {label}: " + " / ".join(f"{k} {v['avg_score']:.2f} (n={v['n']})" for k, v in sorted(summ.items())))
    if ab_lines:
        out += ["", "<b>🧪 A/B 변형별 평균 score</b>"] + ab_lines + ["<i>n이 작으면 참고용입니다.</i>"]
    if recent:
        out += ["", f"<i>최근 {days}일 집계 게시물 {len(recent)}개</i>"]
    if len(rows) < MIN_POSTS_FOR_EXAMPLES:
        out += ["", f"<i>기획안 참고 예시는 집계 게시물 {MIN_POSTS_FOR_EXAMPLES}개부터 반영됩니다.</i>"]
    return "\n".join(out)




# ── 훅 분류 (ig-audit: "어떤 훅 공식이 먹혔나"를 나중에 비교하려면 게시 시점에 기록해야 함) ──
from pipeline.hook_guard import JARGON_TERMS as _JARGON  # 플래너/대본 가드와 같은 용어 목록을 쓴다


def classify_hook(hook: str) -> Dict[str, Any]:
    """훅 문장에서 성과 비교용 특징을 뽑는다. 결과는 variant_json에 합쳐 저장한다.
    hook_jargon: 일간/신살 등 전문 용어가 훅에 있는가 (실측: 용어 있는 게시물 119~189회, 없는 게시물 1,510회)."""
    h = (hook or "").strip()
    if re.search(r"\d+\s*개\s*(이상|맞|해당)|체크", h):
        formula = "checklist"
    elif re.search(r"\bvs\b|\s대\s", h, re.I):
        formula = "balance"
    elif re.search(r"TOP\s*\d|순위", h, re.I):
        formula = "ranking"
    elif re.search(r"이것|이 사람|이거", h):
        formula = "mystery"
    elif re.search(r"아닙니다|아니라|진짜 이유|줄 알았|착한", h):
        formula = "fakeout"
    elif re.search(r"[A-Z]{4}", h) or any(j in h for j in _JARGON):
        formula = "identity"
    else:
        formula = "other"
    return {
        "hook_formula": formula,
        "hook_chars": len(h),
        "hook_jargon": any(j in h for j in _JARGON),
        "hook_has_number": bool(re.search(r"\d", h)),
        "hook_has_mbti": bool(re.search(r"\b[EI][NS][TF][JP]\b", h)),
    }


def _median(vals: List[float]) -> float:
    v = sorted(vals)
    if not v:
        return 0.0
    mid = len(v) // 2
    return float(v[mid]) if len(v) % 2 else (v[mid - 1] + v[mid]) / 2


def fetch_account_media(limit: int = 30, access_token: Optional[str] = None,
                        account_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """계정에 실제로 올라간 최근 미디어 목록. GitHub Actions처럼 state.db가 매번 사라지는 환경에서도
    '무엇을 올렸는지'를 DB 없이 알 수 있게 한다."""
    token = access_token or os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
    acct = account_id or os.getenv("INSTAGRAM_ACCOUNT_ID", "")
    if not token or not acct:
        return []
    try:
        r = requests.get(
            f"https://graph.facebook.com/{GRAPH_VERSION}/{acct}/media",
            params={"fields": "id,caption,media_product_type,timestamp,permalink", "limit": limit,
                    "access_token": token},
            timeout=20,
        )
        return r.json().get("data", []) if r.ok else []
    except requests.RequestException:
        return []


def sync_account_media(limit: int = 30) -> int:
    """계정 미디어 중 published_posts에 없는 것을 채워 넣는다(훅=캡션 첫 줄). 추가한 개수 반환."""
    added = 0
    conn = _conn()
    try:
        have = {r[0] for r in conn.execute("SELECT media_id FROM published_posts")}
        for m in fetch_account_media(limit):
            if m["id"] in have:
                continue
            first = (m.get("caption") or "").strip().split("\n")[0][:80]
            fmt = "reel" if m.get("media_product_type") == "REELS" else "carousel"
            with conn:
                conn.execute(
                    "INSERT OR IGNORE INTO published_posts "
                    "(media_id, format, series, mbti, topic, title, hook, trend_hint, permalink, published_at, variant_json) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (m["id"], fmt, "", "", "", first, first, "", m.get("permalink", ""),
                     m.get("timestamp", _now().isoformat()),
                     json.dumps({"synced": True, **classify_hook(first)}, ensure_ascii=False)),
                )
            added += 1
    finally:
        conn.close()
    return added


def audit_rows(limit: int = 30) -> List[Dict[str, Any]]:
    """계정 릴스 각각의 '지금까지 누적' 지표를 새로 받아 ig-audit 지표를 계산한다.
    (DB 스냅샷 시점에 의존하지 않음: 24h/72h 값이 똑같이 저장되던 문제를 피한다.)"""
    rows = []
    for m in fetch_account_media(limit):
        if m.get("media_product_type") != "REELS":
            continue
        met = fetch_media_insights(m["id"])
        if not met:
            continue
        first = (m.get("caption") or "").strip().split("\n")[0][:60]
        rows.append({"id": m["id"], "hook": first, "ts": m.get("timestamp", ""), **met})
    med = _median([r.get("views", r.get("plays", 0)) for r in rows])
    for r in rows:
        views = r.get("views", r.get("plays", 0))
        reach = max(r.get("reach", 0), 1)
        r["outlier"] = round(views / med, 1) if med else 0.0
        r["sends_per_reach_pct"] = round(r.get("shares", 0) / reach * 100, 2)
        r["follows_per_reach_pct"] = round(r.get("follows", 0) / reach * 100, 2)
        r["avg_watch_s"] = round(r.get("ig_reels_avg_watch_time", 0) / 1000, 1)
    rows.sort(key=lambda r: -r["outlier"])
    return rows


def audit_report(limit: int = 30) -> str:
    rows = audit_rows(limit)
    if not rows:
        return "📊 ig-audit: 지표를 가져오지 못했습니다(토큰/권한 확인)."
    med = _median([r.get("views", r.get("plays", 0)) for r in rows])
    out = [f"📊 <b>ig-audit</b> · 릴스 {len(rows)}개 · 조회 중앙값 {int(med)}", ""]
    for r in rows[:5]:
        out.append(f"{r['outlier']}배 · 조회 {int(r.get('views', 0))} · 시청 {r['avg_watch_s']}초 · "
                   f"공유/도달 {r['sends_per_reach_pct']}% · 팔로우/도달 {r['follows_per_reach_pct']}% · {r['hook']}")
    if len(rows) > 5:
        out += ["", "<b>하위</b>"]
        for r in rows[-3:]:
            out.append(f"{r['outlier']}배 · 조회 {int(r.get('views', 0))} · 시청 {r['avg_watch_s']}초 · {r['hook']}")
    if len(rows) < 12:
        out += ["", f"<i>표본 {len(rows)}개: 패턴이 아니라 단서 수준입니다.</i>"]
    return "\n".join(out)


def _send_telegram(text: str) -> None:
    token, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if token and chat:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      data={"chat_id": chat, "text": text, "parse_mode": "HTML"}, timeout=15)


if __name__ == "__main__":
    # --audit    : 계정에서 직접 받아 ig-audit 리포트 출력 (GitHub Actions 등 DB가 없는 환경용)
    # --telegram : 결과를 텔레그램으로도 전송
    if "--audit" in sys.argv:
        text = audit_report()
        print(text)
        if "--telegram" in sys.argv:
            _send_telegram(text)
    else:
        print(f"계정에서 새로 채운 게시물: {sync_account_media()}개")
        n = collect_due_insights()
        print(f"수집한 스냅샷: {n}개")
        print(weekly_report())
