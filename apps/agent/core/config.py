"""환경변수 및 원격 설정 로더.

루트의 `.env` 하나를 읽는다. 값이 비어 있으면 각 모듈이 Mock/Dry-run 으로 폴백한다.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

AGENT_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = AGENT_DIR.parent.parent


def _resolve(p: str) -> Path:
    path = Path(p)
    return path if path.is_absolute() else REPO_ROOT / path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    # runtime
    app_mode: Literal["local", "demo"] = "local"
    agent_host: str = "127.0.0.1"
    agent_port: int = 8787
    agent_cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    agent_output_dir: str = "apps/agent/output"

    # license
    license_enforce: bool = False
    license_key: str = ""
    license_public_key: str = ""
    supabase_url: str = ""
    supabase_service_role_key: str = ""

    # AI
    anthropic_api_key: str = ""
    ai_model: str = "claude-sonnet-5-5"
    tts_voice: str = "ko-KR-SunHiNeural"
    image_provider: str = "none"

    # Instagram
    ig_user_id: str = ""
    ig_access_token: str = ""
    ig_graph_version: str = "v21.0"

    # YouTube
    yt_client_id: str = ""
    yt_client_secret: str = ""
    yt_refresh_token: str = ""
    yt_privacy: Literal["public", "unlisted", "private"] = "private"

    # Threads
    threads_user_id: str = ""
    threads_access_token: str = ""

    # Naver
    naver_blog_id: str = ""
    naver_profile_dir: str = "apps/agent/.browser_profile"
    naver_headless: bool = False

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.agent_cors_origins.split(",") if o.strip()]

    @property
    def output_dir(self) -> Path:
        d = _resolve(self.agent_output_dir)
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def profile_dir(self) -> Path:
        return _resolve(self.naver_profile_dir)

    @property
    def assets_dir(self) -> Path:
        return AGENT_DIR / "assets"


settings = Settings()
