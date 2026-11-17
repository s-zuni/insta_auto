"""[판매자 전용] 라이선스 키 발급 도구. 비밀키 파일은 절대 커밋/배포하지 말 것.

  python scripts/issue_license.py keygen                  # 키쌍 생성 (license_private.key 는 안전한 곳에 보관)
  python scripts/issue_license.py issue --hwid <HWID> --exp 2027-01-31 --customer "OO카페"
고객 PC 의 HWID: python -c "from apps.agent.core.license import get_hwid; print(get_hwid())"
"""
import argparse
import base64
import json
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def enc(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    k = sub.add_parser("keygen")
    k.add_argument("--out", default="license_private.key")

    i = sub.add_parser("issue")
    i.add_argument("--key", default="license_private.key")
    i.add_argument("--hwid", required=True)
    i.add_argument("--exp", required=True, help="YYYY-MM-DD")
    i.add_argument("--customer", default="")
    i.add_argument("--plan", default="pro")

    a = ap.parse_args()
    if a.cmd == "keygen":
        sk = Ed25519PrivateKey.generate()
        Path(a.out).write_bytes(sk.private_bytes(
            serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption()))
        pub = sk.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        print("LICENSE_PUBLIC_KEY=" + base64.b64encode(pub).decode())
        print(f"비밀키 저장: {a.out}  (커밋 금지!)")
    else:
        sk = Ed25519PrivateKey.from_private_bytes(Path(a.key).read_bytes())
        payload = json.dumps(
            {"hwid": a.hwid, "exp": a.exp, "plan": a.plan, "customer": a.customer}, ensure_ascii=False
        ).encode()
        print(f"{enc(payload)}.{enc(sk.sign(payload))}")


if __name__ == "__main__":
    main()
