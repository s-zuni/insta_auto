"""
Threads API 게시 모듈 (텍스트 전용).

필요한 .env:
  THREADS_USER_ID=...        # GET /me 로 확인한 Threads 사용자 ID
  THREADS_ACCESS_TOKEN=...   # 장기 토큰(60일). refresh_long_lived_token()으로 연장 가능
  THREADS_APP_SECRET=...     # 앱 대시보드 -> Threads API 설정의 'Threads 앱 시크릿' (단기->장기 교환용)
"""
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv()

THREADS_API = "https://graph.threads.net"
THREADS_VERSION = os.getenv("THREADS_API_VERSION", "v1.0")
MAX_TEXT_LEN = 500


def clean_token(token: Optional[str]) -> str:
    """Railway 등에 붙여넣다 섞인 따옴표/공백/줄바꿈/'THREADS_ACCESS_TOKEN=' 접두어를 제거합니다."""
    t = (token or "").strip()
    if "=" in t[:30]:
        t = t.split("=", 1)[1]
    return "".join(t.split()).strip("'\"")


def _url(path: str) -> str:
    return f"{THREADS_API}/{THREADS_VERSION}/{path}".rstrip("/")


def _api_error(res: requests.Response) -> str:
    # 상세 원인 추적용: 콘솔 + threads_error.log (토큰은 요청 본문에만 있고 응답에는 없음)
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {res.request.method} {res.request.url.split('?')[0]} -> {res.status_code} {res.text[:1000]}"
    print(f"[THREADS][ERROR] {line}")
    try:
        with open(PROJECT_ROOT / "threads_error.log", "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    try:
        err = res.json().get("error", {})
        return f"[{err.get('code')}/{err.get('error_subcode')}] {err.get('message', res.text)}"
    except Exception:
        return res.text[:300]


def exchange_for_long_lived_token(short_lived_token: str, app_secret: Optional[str] = None) -> Dict[str, Any]:
    """단기 토큰(1시간)을 장기 토큰(60일)으로 교환합니다. 반환: {access_token, expires_in}"""
    app_secret = app_secret or os.getenv("THREADS_APP_SECRET", "")
    if not app_secret:
        return {"error": "THREADS_APP_SECRET 이 필요합니다."}
    res = requests.get(
        f"{THREADS_API}/access_token",
        params={"grant_type": "th_exchange_token", "client_secret": app_secret, "access_token": short_lived_token},
        timeout=30,
    )
    if not res.ok:
        return {"error": _api_error(res)}
    return res.json()


def refresh_long_lived_token(token: Optional[str] = None) -> Dict[str, Any]:
    """장기 토큰을 60일 더 연장합니다(발급 24시간 후부터, 만료 전에만 가능). 반환: {access_token, expires_in}"""
    token = clean_token(token or os.getenv("THREADS_ACCESS_TOKEN", ""))
    if not token:
        return {"error": "THREADS_ACCESS_TOKEN 이 필요합니다."}
    res = requests.get(
        f"{THREADS_API}/refresh_access_token",
        params={"grant_type": "th_refresh_token", "access_token": token},
        timeout=30,
    )
    if not res.ok:
        return {"error": _api_error(res)}
    return res.json()


def get_me(token: Optional[str] = None) -> Dict[str, Any]:
    """토큰 소유자의 id/username 조회 (설정 확인용)."""
    token = clean_token(token or os.getenv("THREADS_ACCESS_TOKEN", ""))
    res = requests.get(_url("me"), params={"fields": "id,username", "access_token": token}, timeout=30)
    if not res.ok:
        return {"error": _api_error(res)}
    return res.json()


def publish_text_to_threads(
    text: str,
    topic_tag: Optional[str] = None,
    user_id: Optional[str] = None,
    access_token: Optional[str] = None,
    reply_to_id: Optional[str] = None,
) -> Dict[str, Any]:
    """텍스트 글 1건을 게시합니다(reply_to_id를 주면 해당 글에 대한 답글). 성공 시 {"id": ..., "permalink": ...}, 실패 시 {"error": ...}."""
    user_id = user_id or os.getenv("THREADS_USER_ID", "")
    access_token = clean_token(access_token or os.getenv("THREADS_ACCESS_TOKEN", ""))
    if not user_id or not access_token:
        return {"error": "THREADS_USER_ID 및 THREADS_ACCESS_TOKEN이 필요합니다."}
    text = (text or "").strip()
    if not text:
        return {"error": "게시할 텍스트가 비어 있습니다."}
    if len(text) > MAX_TEXT_LEN:
        return {"error": f"텍스트가 {MAX_TEXT_LEN}자를 초과합니다 ({len(text)}자)."}

    payload = {"media_type": "TEXT", "text": text, "access_token": access_token}
    if topic_tag and not reply_to_id:
        payload["topic_tag"] = topic_tag
    if reply_to_id:
        payload["reply_to_id"] = reply_to_id

    print(f"[THREADS] 컨테이너 생성 (user {user_id}, {len(text)}자)...")
    res = requests.post(_url(f"{user_id}/threads"), data=payload, timeout=30)
    if not res.ok:
        return {"error": _api_error(res), "status_code": res.status_code}
    creation_id = res.json().get("id")

    time.sleep(3)  # 컨테이너 처리 대기 (텍스트는 짧게로 충분)
    res = requests.post(
        _url(f"{user_id}/threads_publish"),
        data={"creation_id": creation_id, "access_token": access_token},
        timeout=30,
    )
    if not res.ok:
        return {"error": _api_error(res), "status_code": res.status_code}
    post_id = res.json().get("id")

    permalink = ""
    try:
        r = requests.get(_url(post_id), params={"fields": "permalink", "access_token": access_token}, timeout=15)
        if r.ok:
            permalink = r.json().get("permalink", "")
    except Exception:
        pass
    print(f"[THREADS] ✅ 게시 완료: {permalink or post_id}")
    return {"id": post_id, "permalink": permalink}


def publish_thread(
    posts: list,
    topic_tag: Optional[str] = None,
    user_id: Optional[str] = None,
    access_token: Optional[str] = None,
) -> Dict[str, Any]:
    """타래 게시: posts[0]=본문, 이후는 직전 글에 이어지는 답글. 반환: {"ids": [...], "permalink": 본문 링크,
    "error": 중간 실패 시 메시지}. 본문이 실패하면 {"error": ...}, 답글 중간 실패 시 이미 올라간 ids와 error를 함께 반환."""
    if not posts:
        return {"error": "게시할 글이 없습니다."}
    first = publish_text_to_threads(posts[0], topic_tag=topic_tag, user_id=user_id, access_token=access_token)
    if "error" in first:
        return first
    ids = [first["id"]]
    for i, text in enumerate(posts[1:], start=1):
        time.sleep(2)
        r = publish_text_to_threads(
            text, user_id=user_id, access_token=access_token, reply_to_id=ids[-1]
        )
        if "error" in r:
            return {"ids": ids, "permalink": first.get("permalink", ""), "error": f"답글 {i} 게시 실패: {r['error']}"}
        ids.append(r["id"])
    return {"ids": ids, "id": ids[0], "permalink": first.get("permalink", "")}


if __name__ == "__main__":
    # 사용법:
    #   python pipeline/threads_publisher.py exchange <단기_토큰>   -> 장기 토큰 출력
    #   python pipeline/threads_publisher.py me                    -> 사용자 ID/이름 확인
    #   python pipeline/threads_publisher.py refresh               -> 장기 토큰 연장
    cmd = sys.argv[1] if len(sys.argv) > 1 else "me"
    if cmd == "exchange" and len(sys.argv) > 2:
        out = exchange_for_long_lived_token(sys.argv[2])
    elif cmd == "refresh":
        out = refresh_long_lived_token(sys.argv[2] if len(sys.argv) > 2 else None)
    else:
        out = get_me()
    print(out)
