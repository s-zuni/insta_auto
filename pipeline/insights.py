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
                     "total_interactions", "ig_reels_avg_watch_time"]
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
                title: str = "", hook: str = "", trend_hint: str = "", permalink: str = "") -> None:
    """게시 직후 호출해 메타데이터를 저장합니다. fmt: 'reel' | 'carousel'"""
    if not media_id:
        return
    conn = _conn()
    try:
        with conn:
            conn.execute(
                "INSERT OR REPLACE INTO published_posts VALUES (?,?,?,?,?,?,?,?,?,?)",
                (str(media_id), fmt, series, mbti, topic, title, hook, trend_hint, permalink, _now().isoformat()),
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
    if recent:
        out += ["", f"<i>최근 {days}일 집계 게시물 {len(recent)}개</i>"]
    if len(rows) < MIN_POSTS_FOR_EXAMPLES:
        out += ["", f"<i>기획안 참고 예시는 집계 게시물 {MIN_POSTS_FOR_EXAMPLES}개부터 반영됩니다.</i>"]
    return "\n".join(out)


if __name__ == "__main__":
    n = collect_due_insights()
    print(f"수집한 스냅샷: {n}개")
    print(weekly_report())
