"""
Instagram Graph API Automatic Reels Publisher.
Publishes vertical 9:16 Reels and image carousels to Instagram account '@mbti_ju'.
"""
import os
import sys
import time
import requests
from pathlib import Path
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

load_dotenv()

GRAPH_VERSION = os.getenv("INSTAGRAM_GRAPH_VERSION", "v21.0")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def resolve_instagram_account_id(account_id: str, access_token: str) -> str:
    """
    입력된 ID가 페이스북 페이지 ID인 경우, 연결된 인스타그램 비즈니스 계정 ID로 자동 전환합니다.
    (예: 페이지 ID 1243911252149395 -> 인스타그램 비즈니스 계정 ID 17841438562850140)
    """
    try:
        url = f"https://graph.facebook.com/{GRAPH_VERSION}/{account_id}"
        r = requests.get(
            url,
            params={"fields": "id,name,instagram_business_account", "access_token": access_token},
            timeout=10
        )
        if r.ok:
            data = r.json()
            ig_acc = data.get("instagram_business_account", {}).get("id")
            if ig_acc:
                print(f"[INSTA] 페이스북 페이지 ID({account_id})에서 실제 인스타그램 계정 ID({ig_acc})로 자동 전환 완료!")
                return str(ig_acc)
    except Exception as e:
        print(f"[INSTA] 계정 ID 자동 확인 중 알림: {e}")
    return account_id


def _check_token_validity(account_id: str, access_token: str) -> Optional[str]:
    """
    게시 시도 전에 토큰 상태를 미리 점검합니다.
    문제가 없으면 None, 문제가 있으면 원인과 해결 방법을 담은 한글 메시지를 반환합니다.
    """
    try:
        res = requests.get(
            f"https://graph.facebook.com/{GRAPH_VERSION}/{account_id}",
            params={"fields": "id,username,name", "access_token": access_token},
            timeout=15,
        )
        if res.ok:
            return None

        err = res.json().get("error", {}) if res.headers.get("content-type", "").startswith("application/json") else {}
        message = err.get("message", res.text)
        code = err.get("code")

        if code in (190, 102) or "expired" in message.lower() or "session has expired" in message.lower():
            return (
                f"Instagram 액세스 토큰이 만료되었습니다: {message}\n"
                "  ▶ 해결 방법: Graph API Explorer에서 토큰을 재발급받아 .env 및 Railway의 INSTAGRAM_ACCESS_TOKEN에 등록하세요."
            )
        return f"Instagram 토큰/계정 점검 실패: {message}"
    except Exception as e:
        return f"Instagram 토큰 사전 점검 중 네트워크 오류: {e}"


def _graph(path: str = "") -> str:
    return f"https://graph.facebook.com/{GRAPH_VERSION}/{path}".rstrip("/")


def _api_error(res: requests.Response) -> str:
    try:
        return res.json().get("error", {}).get("message", res.text)
    except ValueError:
        return res.text


def _wait_container(container_id: str, access_token: str, timeout: int = 300, interval: int = 5) -> Optional[str]:
    """
    컨테이너가 FINISHED가 될 때까지 대기합니다.
    성공하면 None, 실패/타임아웃이면 원인 메시지를 반환합니다. (미완료 상태로 media_publish를 호출하지 않기 위함)
    """
    start_t = time.time()
    last_status = "UNKNOWN"
    while time.time() - start_t < timeout:
        try:
            s_res = requests.get(
                _graph(container_id),
                params={"fields": "status_code,status", "access_token": access_token},
                timeout=15,
            )
            if s_res.ok:
                body = s_res.json()
                last_status = body.get("status_code", "UNKNOWN")
                if last_status == "FINISHED":
                    return None
                if last_status in ("ERROR", "EXPIRED"):
                    return f"Instagram 미디어 처리 실패({last_status}): {body.get('status', '')}"
        except requests.RequestException as e:
            print(f"  [WARN] 컨테이너 상태 조회 일시 오류: {e}")
        time.sleep(interval)
    return f"Instagram 미디어 처리 대기 시간 초과({timeout}초, 마지막 상태: {last_status})"


def _publish_container(account_id: str, container_id: str, access_token: str, label: str) -> Dict[str, Any]:
    """FINISHED 상태의 컨테이너를 게시하고, 실제 permalink를 조회해 반환합니다."""
    p_res = requests.post(
        _graph(f"{account_id}/media_publish"),
        data={"creation_id": container_id, "access_token": access_token},
        timeout=30,
    )
    if not p_res.ok:
        err_msg = _api_error(p_res)
        print(f"[ERROR] {label} 게시 실패: {err_msg}")
        return {"error": err_msg}

    post_id = p_res.json().get("id")
    link = ""
    try:
        # media id로는 URL을 만들 수 없고, shortcode가 담긴 permalink를 조회해야 합니다.
        l_res = requests.get(
            _graph(post_id),
            params={"fields": "permalink", "access_token": access_token},
            timeout=15,
        )
        if l_res.ok:
            link = l_res.json().get("permalink", "")
    except requests.RequestException as e:
        print(f"  [WARN] permalink 조회 실패: {e}")

    print(f"[SUCCESS] 🎉 인스타그램 {label} 게시 완료! (게시글 ID: {post_id}) {link}")
    return {"id": post_id, "status": "PUBLISHED", "link": link}


def _prepare_account(account_id: Optional[str], access_token: Optional[str]):
    account_id = account_id or os.getenv("INSTAGRAM_ACCOUNT_ID")
    access_token = access_token or os.getenv("INSTAGRAM_ACCESS_TOKEN")
    if not account_id or not access_token:
        raise ValueError("INSTAGRAM_ACCOUNT_ID 및 INSTAGRAM_ACCESS_TOKEN이 필요합니다.")

    # 계정 ID가 페이스북 페이지 ID일 경우 실제 인스타그램 비즈니스 ID로 자동 전환
    account_id = resolve_instagram_account_id(account_id, access_token)
    token_error = _check_token_validity(account_id, access_token)
    return account_id, access_token, token_error


def publish_reel_to_instagram(
    video_url: str,
    caption: str,
    account_id: Optional[str] = None,
    access_token: Optional[str] = None,
    cover_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Instagram Graph API를 사용하여 릴스 영상(video_url)과 캡션을 자동 게시합니다.
    cover_url을 주면 해당 이미지를 릴스 커버로 사용합니다.
    """
    account_id, access_token, token_error = _prepare_account(account_id, access_token)
    if token_error:
        print(f"[ERROR] {token_error}")
        return {"error": token_error}

    print(f"[INSTA] 릴스 미디어 컨테이너 생성 요청 (계정 ID: {account_id})...")
    reel_payload = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "access_token": access_token,
    }
    if cover_url:
        reel_payload["cover_url"] = cover_url
    res = requests.post(_graph(f"{account_id}/media"), data=reel_payload, timeout=30)
    if not res.ok:
        err_msg = _api_error(res)
        print(f"[ERROR] 릴스 컨테이너 생성 실패: {err_msg}")
        return {"error": err_msg, "status_code": res.status_code}

    container_id = res.json().get("id")
    print(f"  ✅ 컨테이너 생성 완료 (ID: {container_id})")

    print("  ⏳ Instagram 인코딩 및 처리 대기 중...")
    wait_error = _wait_container(container_id, access_token, timeout=300, interval=10)
    if wait_error:
        print(f"  ❌ {wait_error}")
        return {"error": wait_error}
    print("  ✅ 영상 인코딩 완료!")

    print("[INSTA] 릴스 최종 게시(Publish) 실행 중...")
    return _publish_container(account_id, container_id, access_token, "릴스")


def publish_carousel_to_instagram(
    image_urls: List[str],
    caption: str,
    account_id: Optional[str] = None,
    access_token: Optional[str] = None
) -> Dict[str, Any]:
    """
    공개 접근 가능한 이미지 URL 2~10개로 캐러셀 게시물을 자동 게시합니다.
    (자식 컨테이너 생성 -> CAROUSEL 컨테이너 생성 -> FINISHED 대기 -> media_publish)
    """
    if not 2 <= len(image_urls) <= 10:
        return {"error": f"캐러셀은 이미지 2~10장이 필요합니다 (현재 {len(image_urls)}장)."}

    account_id, access_token, token_error = _prepare_account(account_id, access_token)
    if token_error:
        print(f"[ERROR] {token_error}")
        return {"error": token_error}

    child_ids: List[str] = []
    for idx, url in enumerate(image_urls, 1):
        res = requests.post(
            _graph(f"{account_id}/media"),
            data={"image_url": url, "is_carousel_item": "true", "access_token": access_token},
            timeout=30,
        )
        if not res.ok:
            err_msg = _api_error(res)
            print(f"[ERROR] 캐러셀 슬라이드 {idx} 컨테이너 생성 실패: {err_msg}")
            return {"error": f"슬라이드 {idx} 생성 실패: {err_msg}"}
        child_ids.append(res.json()["id"])
        print(f"  ✅ 슬라이드 {idx}/{len(image_urls)} 컨테이너 생성 (ID: {child_ids[-1]})")

    for idx, cid in enumerate(child_ids, 1):
        wait_error = _wait_container(cid, access_token, timeout=120, interval=3)
        if wait_error:
            return {"error": f"슬라이드 {idx}: {wait_error}"}

    res = requests.post(
        _graph(f"{account_id}/media"),
        data={
            "media_type": "CAROUSEL",
            "children": ",".join(child_ids),
            "caption": caption,
            "access_token": access_token,
        },
        timeout=30,
    )
    if not res.ok:
        err_msg = _api_error(res)
        print(f"[ERROR] 캐러셀 컨테이너 생성 실패: {err_msg}")
        return {"error": err_msg}

    carousel_id = res.json()["id"]
    wait_error = _wait_container(carousel_id, access_token, timeout=120, interval=3)
    if wait_error:
        return {"error": wait_error}

    return _publish_container(account_id, carousel_id, access_token, "캐러셀")


if __name__ == "__main__":
    account_id = os.getenv("INSTAGRAM_ACCOUNT_ID")
    token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
    resolved_id = resolve_instagram_account_id(account_id, token)
    print(f"[INFO] Instagram 계정 상태 확인 (원래 ID: {account_id} -> 최종 ID: {resolved_id})")
    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{resolved_id}"
    res = requests.get(url, params={"fields": "id,username,name", "access_token": token})
    if res.ok:
        print("연동 계정 정보:", res.json())
    else:
        print("오류:", res.text)