"""하드웨어 UUID 기반 라이선스 검증.

모델
----
- 판매자는 Ed25519 **비밀키**를 보관하고, 고객 PC 의 HWID 를 받아 `scripts/issue_license.py` 로 키를 발급한다.
- 고객 PC 에는 **공개키**(LICENSE_PUBLIC_KEY)만 들어간다 → 오프라인에서도 위조 불가 검증.
- 키 형식:  base64url(payload_json) + "." + base64url(signature)
  payload = {"hwid": "...", "exp": "2027-01-31", "plan": "pro", "customer": "..."}
- (선택) Supabase `licenses` 테이블로 폐기(revoke) 여부를 온라인 확인한다. 오프라인이면 캐시를 신뢰.
"""
from __future__ import annotations

import base64
import hashlib
import json
import platform
import subprocess
import uuid
from dataclasses import dataclass
from datetime import date, datetime

from .config import settings


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _raw_machine_id() -> str:
    system = platform.system()
    try:
        if system == "Windows":
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-CimInstance Win32_ComputerSystemProduct).UUID"],
                capture_output=True, text=True, timeout=10,
            ).stdout.strip()
            if out:
                return out
        elif system == "Darwin":
            out = subprocess.run(
                ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                capture_output=True, text=True, timeout=10,
            ).stdout
            for line in out.splitlines():
                if "IOPlatformUUID" in line:
                    return line.split('"')[-2]
        else:
            for p in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
                try:
                    return open(p).read().strip()
                except OSError:
                    continue
    except Exception:
        pass
    return f"mac-{uuid.getnode():x}"  # 최후의 폴백


def get_hwid() -> str:
    """원본 UUID 를 그대로 노출하지 않도록 해시한 고객 PC 식별자."""
    return hashlib.sha256(_raw_machine_id().encode()).hexdigest()[:32]


@dataclass
class LicenseStatus:
    state: str  # valid | invalid | not_required
    message: str = ""
    payload: dict | None = None


def verify_license_key(key: str, public_key_b64: str, hwid: str, today: date | None = None) -> LicenseStatus:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    if not key or "." not in key:
        return LicenseStatus("invalid", "라이선스 키가 없거나 형식이 올바르지 않습니다.")
    if not public_key_b64:
        return LicenseStatus("invalid", "LICENSE_PUBLIC_KEY 가 설정되지 않았습니다.")
    try:
        p_part, s_part = key.split(".", 1)
        payload_bytes = _b64d(p_part)
        Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key_b64)).verify(
            _b64d(s_part), payload_bytes
        )
        payload = json.loads(payload_bytes)
    except (InvalidSignature, ValueError, KeyError):
        return LicenseStatus("invalid", "서명 검증에 실패했습니다.")

    if payload.get("hwid") != hwid:
        return LicenseStatus("invalid", "이 PC에 발급된 라이선스가 아닙니다.", payload)
    exp = payload.get("exp")
    if exp and datetime.strptime(exp, "%Y-%m-%d").date() < (today or date.today()):
        return LicenseStatus("invalid", f"라이선스가 만료되었습니다 ({exp}).", payload)
    return LicenseStatus("valid", "OK", payload)


def check_license() -> LicenseStatus:
    """현재 설정 기준 라이선스 상태. demo 모드나 enforce=false 면 검사하지 않는다."""
    if settings.app_mode == "demo" or not settings.license_enforce:
        return LicenseStatus("not_required", "라이선스 검사 비활성화")
    return verify_license_key(settings.license_key, settings.license_public_key, get_hwid())


def require_license() -> None:
    """FastAPI 의존성: 유효하지 않으면 403."""
    from fastapi import HTTPException

    st = check_license()
    if st.state == "invalid":
        raise HTTPException(status_code=403, detail=st.message)
