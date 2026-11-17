"""Web UI ↔ Agent 표준 입출력 모델.

⚠️ 계약(contract) 파일: 이 파일을 바꾸면 반드시 `apps/web/src/lib/types.ts` 도 같이 수정하고
`tests/test_api_contract.py` 를 통과시킬 것. (CLAUDE.md '계약 동기화 규칙' 참고)
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

StyleId = Literal["info", "story", "review", "promo", "empathy"]
Channel = Literal["instagram", "youtube", "threads", "naver_blog"]
PublishStatus = Literal["ok", "failed", "dry_run", "skipped"]


# ---------- 입력 ----------
class GenerateRequest(BaseModel):
    business_type: str = Field(..., description="업종 (예: 카페, 미용실)")
    topic: str = Field(..., min_length=2, description="마케팅 주제")
    style: StyleId = "info"
    brand_name: str = ""
    extra_context: str = Field("", description="사장님이 덧붙이는 정보 (가격, 위치, 이벤트 등)")
    render_video: bool = Field(True, description="False면 영상 렌더링을 건너뜀 (테스트/데모)")


# ---------- 콘텐츠 ----------
class Scene(BaseModel):
    narration: str = Field(..., description="TTS로 읽을 문장")
    on_screen_text: str = Field("", description="화면 상단 큰 텍스트")
    image_prompt: str = Field("", description="배경 이미지 프롬프트 (없으면 그라데이션)")


class ShortsContent(BaseModel):
    title: str
    scenes: list[Scene]
    caption: str = ""
    hashtags: list[str] = Field(default_factory=list)
    video_path: str | None = None
    duration_sec: float | None = None


class ThreadsContent(BaseModel):
    posts: list[str] = Field(..., min_length=1, description="체인(첫 글 + 이어쓰기), 각 500자 이내")


class BlogContent(BaseModel):
    title: str
    body_markdown: str
    tags: list[str] = Field(default_factory=list)
    meta_description: str = ""


class GeneratedContent(BaseModel):
    shorts: ShortsContent
    threads: ThreadsContent
    blog: BlogContent


class GenerateResponse(BaseModel):
    job_id: str
    content: GeneratedContent
    video_url: str | None = Field(None, description="Agent 기준 상대 경로 (/api/video/{job_id})")
    warnings: list[str] = Field(default_factory=list)
    mock: bool = Field(False, description="AI 키 없이 Mock 으로 생성됐는지")


# ---------- 발행 ----------
class PublishRequest(BaseModel):
    job_id: str
    channels: list[Channel] = Field(..., min_length=1)
    content: GeneratedContent = Field(..., description="사용자가 3분할 에디터에서 수정한 최종본")
    dry_run: bool = True


class PublishResult(BaseModel):
    channel: Channel
    status: PublishStatus
    url: str | None = None
    message: str = ""


class PublishResponse(BaseModel):
    job_id: str
    results: list[PublishResult]


# ---------- 상태 ----------
class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    app_mode: str
    version: str
    ffmpeg: bool
    ai_configured: bool
    license: Literal["valid", "invalid", "not_required"]
    license_message: str = ""
    configured_channels: dict[str, bool] = Field(default_factory=dict)
