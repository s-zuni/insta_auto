"""FastAPI 로컬 실행 에이전트 엔트리포인트.

실행(저장소 루트에서):  python -m uvicorn apps.agent.main:app --port 8787
"""
from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .core import llm
from .core.config import settings
from .core.license import check_license, require_license
from .core.schemas import (
    GeneratedContent,
    GenerateRequest,
    GenerateResponse,
    HealthResponse,
    PublishRequest,
    PublishResponse,
    PublishResult,
    VideoStatus,
    VideoStatusResponse,
)
from .generators.matrix_prompt import generate_all
from .media import shorts_composer
from .publishers import instagram, naver_blog, threads, youtube

VERSION = "0.1.0"

app = FastAPI(title="insta_auto local agent", version=VERSION)
app.add_middleware(
    CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"],
)

# job_id → 최근 영상 경로 (프로세스 메모리; 로컬 단일 사용자 전제)
_videos: dict[str, Path] = {}
# job_id → (영상 상태, 한국어 메시지)
_video_status: dict[str, tuple[VideoStatus, str]] = {}


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    lic = check_license()
    return HealthResponse(
        app_mode=settings.app_mode, version=VERSION, ffmpeg=shorts_composer.ffmpeg_available(),
        ai_configured=llm.is_configured(), license=lic.state, license_message=lic.message,  # type: ignore[arg-type]
        configured_channels={
            "instagram": bool(settings.ig_user_id and settings.ig_access_token),
            "youtube": bool(settings.yt_refresh_token and settings.yt_client_id),
            "threads": bool(settings.threads_user_id and settings.threads_access_token),
            "naver_blog": bool(settings.naver_blog_id),
        },
    )


@app.post("/api/generate", response_model=GenerateResponse, dependencies=[Depends(require_license)])
async def generate(req: GenerateRequest) -> GenerateResponse:
    job_id = uuid.uuid4().hex[:12]
    content, mock = await generate_all(req)
    warnings: list[str] = []
    video_url = None
    video_status: VideoStatus = "none"
    if mock:
        warnings.append("ANTHROPIC_API_KEY 가 없어 Mock 콘텐츠로 생성했습니다.")
    if req.render_video:
        try:
            path, dur = await shorts_composer.render(content.shorts, settings.output_dir / job_id)
            content.shorts.video_path = str(path)
            content.shorts.duration_sec = dur
            _videos[job_id] = path
            video_url = f"/api/video/{job_id}"
            video_status = "ready"
            _video_status[job_id] = ("ready", "")
        except Exception as e:  # noqa: BLE001  (영상 실패해도 텍스트 콘텐츠는 돌려준다)
            warnings.append(f"영상 생성 실패: {e}")
            video_status = "failed"
            _video_status[job_id] = ("failed", f"영상 생성 실패: {e}")
    return GenerateResponse(
        job_id=job_id, content=content, video_url=video_url, warnings=warnings, mock=mock,
        video_status=video_status,
    )


@app.get("/api/video/{job_id}/status", response_model=VideoStatusResponse)
def video_status(job_id: str) -> VideoStatusResponse:
    """영상 진행 상태 (웹이 폴링). 아직 영상 요청이 없던 job 은 none 이 아니라 404."""
    if job_id in _video_status:
        status, message = _video_status[job_id]
    elif (settings.output_dir / job_id / "shorts.mp4").exists():
        status, message = "ready", ""
    else:
        raise HTTPException(404, "해당 작업의 영상 정보가 없습니다")
    return VideoStatusResponse(
        status=status, message=message, video_url=f"/api/video/{job_id}" if status == "ready" else None,
    )


@app.get("/api/video/{job_id}")
def video(job_id: str) -> FileResponse:
    path = _videos.get(job_id) or (settings.output_dir / job_id / "shorts.mp4")
    if not path.exists():
        raise HTTPException(404, "영상이 없습니다")
    return FileResponse(path, media_type="video/mp4")


@app.post("/api/publish", response_model=PublishResponse, dependencies=[Depends(require_license)])
async def publish(req: PublishRequest) -> PublishResponse:
    c: GeneratedContent = req.content
    video_path = Path(c.shorts.video_path) if c.shorts.video_path else _videos.get(req.job_id)
    jobs = {
        "instagram": lambda: instagram.publish(c.shorts, video_path, req.dry_run),
        "youtube": lambda: youtube.publish(c.shorts, video_path, req.dry_run),
        "threads": lambda: threads.publish(c.threads, req.dry_run),
        "naver_blog": lambda: naver_blog.publish(c.blog, req.dry_run),
    }
    # 채널은 독립 실행 — 하나가 실패해도 나머지는 계속
    results = await asyncio.gather(*(jobs[ch]() for ch in req.channels), return_exceptions=True)
    out: list[PublishResult] = []
    for ch, r in zip(req.channels, results):
        out.append(r if isinstance(r, PublishResult)
                   else PublishResult(channel=ch, status="failed", message=f"{type(r).__name__}: {r}"))
    return PublishResponse(job_id=req.job_id, results=out)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("apps.agent.main:app", host=settings.agent_host, port=settings.agent_port)
