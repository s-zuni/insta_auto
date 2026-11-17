"""API 입출력 스키마 및 Mock 파이프라인 테스트. (외부 네트워크·실계정·API 키 없이 통과해야 함)"""
import base64
import json
from datetime import date

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from apps.agent.core import license as lic
from apps.agent.core.config import settings
from apps.agent.core.schemas import GeneratedContent
from apps.agent.main import app


@pytest.fixture(autouse=True)
def _offline(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    monkeypatch.setattr(settings, "license_enforce", False)


client = TestClient(app)
REQ = {"business_type": "카페", "topic": "원두 보관법", "style": "info", "render_video": False}


def test_health_shape():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert set(body["configured_channels"]) == {"instagram", "youtube", "threads", "naver_blog"}


def test_generate_returns_three_contents_in_mock():
    r = client.post("/api/generate", json=REQ)
    assert r.status_code == 200
    body = r.json()
    assert body["mock"] is True
    GeneratedContent.model_validate(body["content"])  # 스키마 계약
    assert len(body["content"]["shorts"]["scenes"]) >= 3
    assert all(len(p) <= 500 for p in body["content"]["threads"]["posts"])
    assert body["content"]["blog"]["body_markdown"]


def test_generate_rejects_bad_style():
    assert client.post("/api/generate", json={**REQ, "style": "nope"}).status_code == 422


def test_publish_dry_run_all_channels():
    gen = client.post("/api/generate", json=REQ).json()
    r = client.post("/api/publish", json={
        "job_id": gen["job_id"], "channels": ["threads", "naver_blog", "instagram", "youtube"],
        "content": gen["content"], "dry_run": True,
    })
    assert r.status_code == 200
    by_ch = {x["channel"]: x for x in r.json()["results"]}
    assert by_ch["threads"]["status"] == "dry_run"
    assert by_ch["naver_blog"]["status"] == "dry_run"
    # 영상 없이 렌더링을 건너뛰었으므로 영상 채널은 명확한 실패 사유를 돌려줘야 함
    assert by_ch["instagram"]["status"] == "failed" and "영상" in by_ch["instagram"]["message"]
    assert by_ch["youtube"]["status"] == "failed"


def test_license_enforced_blocks_without_key(monkeypatch):
    monkeypatch.setattr(settings, "license_enforce", True)
    monkeypatch.setattr(settings, "license_key", "")
    assert client.post("/api/generate", json=REQ).status_code == 403
    assert client.get("/health").json()["license"] == "invalid"  # health 는 항상 열려 있어야 함


def test_license_roundtrip_and_hwid_binding():
    sk = Ed25519PrivateKey.generate()
    pub = base64.b64encode(sk.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()

    def issue(hwid: str, exp: str) -> str:
        payload = json.dumps({"hwid": hwid, "exp": exp}).encode()
        def enc(b: bytes) -> str:
            return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

        return f"{enc(payload)}.{enc(sk.sign(payload))}"

    today = date(2026, 6, 1)
    assert lic.verify_license_key(issue("H1", "2026-12-31"), pub, "H1", today).state == "valid"
    assert lic.verify_license_key(issue("H1", "2026-12-31"), pub, "H2", today).state == "invalid"
    assert lic.verify_license_key(issue("H1", "2026-01-01"), pub, "H1", today).state == "invalid"
    assert lic.verify_license_key("garbage.sig", pub, "H1", today).state == "invalid"
