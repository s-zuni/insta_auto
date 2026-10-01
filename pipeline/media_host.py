"""
Instagram Graph API가 가져갈 수 있는 '공개 직접 URL'을 만들어 주는 미디어 호스팅 모듈.

Google Drive의 uc?export=download 링크는 용량/쿼터에 따라 확인 페이지가 끼어들어 Instagram의
fetch가 간헐적으로 실패하므로, 게시용 공개 URL은 Cloudinary만 사용합니다.

설정: CLOUDINARY_URL=cloudinary://<api_key>:<api_secret>@<cloud_name>
"""
import hashlib
import os
import sys
import time
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

load_dotenv()


def cloudinary_configured() -> bool:
    return bool(_parse_cloudinary_url())


def _parse_cloudinary_url() -> Optional[Dict[str, str]]:
    raw = os.getenv("CLOUDINARY_URL", "").strip()
    if not raw.startswith("cloudinary://"):
        return None
    u = urlparse(raw)
    if not (u.username and u.password and u.hostname):
        return None
    return {"api_key": u.username, "api_secret": u.password, "cloud_name": u.hostname}


def upload_to_cloudinary(file_path: str | Path, kind: str = "image", folder: str = "insta_auto") -> Dict[str, str]:
    """
    Cloudinary에 서명 업로드(REST)하고 공개 https URL을 반환합니다. 추가 SDK 의존성 없음.
    kind: "image" | "video"
    """
    cfg = _parse_cloudinary_url()
    if not cfg:
        return {"error": "CLOUDINARY_URL이 설정되지 않았습니다."}

    file_path = Path(file_path)
    if not file_path.is_file():
        return {"error": f"파일이 없습니다: {file_path}"}

    timestamp = str(int(time.time()))
    # 서명 대상: file/api_key/resource_type을 제외한 파라미터를 키 알파벳순으로 이어붙인 뒤 secret을 덧붙여 SHA-1
    sign_params = {"folder": folder, "timestamp": timestamp}
    to_sign = "&".join(f"{k}={v}" for k, v in sorted(sign_params.items())) + cfg["api_secret"]
    signature = hashlib.sha1(to_sign.encode("utf-8")).hexdigest()

    resource_type = "video" if kind == "video" else "image"
    url = f"https://api.cloudinary.com/v1_1/{cfg['cloud_name']}/{resource_type}/upload"
    try:
        with open(file_path, "rb") as f:
            res = requests.post(
                url,
                data={"api_key": cfg["api_key"], "timestamp": timestamp, "signature": signature, "folder": folder},
                files={"file": (file_path.name, f)},
                timeout=300,
            )
        body = res.json()
        if res.ok and body.get("secure_url"):
            return {"url": body["secure_url"], "provider": "cloudinary", "public_id": body.get("public_id", "")}
        return {"error": f"Cloudinary 업로드 실패: {body.get('error', {}).get('message', res.text)[:200]}"}
    except Exception as e:
        return {"error": f"Cloudinary 업로드 중 오류: {e}"}


def upload_public(file_path: str | Path, kind: str = "image", folder: str = "insta_auto") -> Dict[str, str]:
    """
    Cloudinary로 공개 URL을 만듭니다. 반환: {"url", "provider"} 또는 {"error"}
    (Google Drive 직링크는 Instagram fetch가 불안정해 더 이상 게시용 URL로 쓰지 않습니다. Drive는 보관용입니다.)
    """
    if not cloudinary_configured():
        return {"error": "CLOUDINARY_URL이 설정되지 않았습니다. .env에 cloudinary://<key>:<secret>@<cloud_name> 형식으로 등록하세요."}
    return upload_to_cloudinary(file_path, kind=kind, folder=folder)
