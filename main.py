"""
Instagram Reels & YouTube Shorts Automation Pipeline Orchestrator.
MBTI x Saju Content -> TTS -> Visuals -> FFmpeg Composition -> Google Drive Upload -> Instagram Reels -> YouTube Shorts
"""
import os
import sys
import argparse
import time
from pathlib import Path
from dotenv import load_dotenv

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.ffmpeg_check import check_ffmpeg
from pipeline.script_gen import generate_script, create_sample_script, ReelsScript
from pipeline.mbti_saju_content import generate_mbti_saju_script
from pipeline.text_utils import sanitize_narration
from pipeline.tts_engine import generate_speech, FullAudioResult
from pipeline.visual_gen import generate_scene_images
from pipeline.composer import compose_reels_video
from pipeline.gdrive_uploader import upload_reels_assets_to_drive
from pipeline.insta_publisher import publish_reel_to_instagram, publish_carousel_to_instagram
from pipeline import media_host
from pipeline.bgm import pick_bgm
from pipeline.cover import build_reel_cover
from pipeline.insights import record_post
from pipeline.youtube_publisher import upload_shorts_to_youtube


def run_pipeline(
    topic: str = "",
    series: str = "MBTI",
    mbti: str = "ENFP",
    element: str = "목(木)",
    trend_hint: str = "",
    mock_script: bool = False,
    mock_images: bool = False,
    upload_gdrive: bool = True,
    publish_insta: bool = True,
    publish_youtube: bool = True,
    output_path: str = "assets/output/final_reel.mp4"
) -> dict:
    """인스타그램 릴스 및 유튜브 숏츠 생성/배포 파이프라인 전체를 원스톱으로 실행합니다."""
    start_total_time = time.time()
    print("\n" + "=" * 65)
    print("🚀 MBTI × 사주 인스타그램 릴스 & 유튜브 숏츠 자동 생성 파이프라인 시작")
    print(f"📌 시리즈: {series} | {topic or mbti or element}")
    print("=" * 65)

    if not check_ffmpeg():
        raise RuntimeError("FFmpeg가 준비되지 않았습니다. 설치를 완료한 후 다시 시도하세요.")

    # 1. 대본 기획
    print("\n[1/7] 🧠 릴스/숏츠 대본 기획 중 (Gemini)...")
    t0 = time.time()
    try:
        if mock_script:
            print("  ℹ️  --mock-script 모드")
            script: ReelsScript = create_sample_script(topic or f"{series} {mbti}")
        elif series != "GENERAL":
            ctx = {}
            if series == "MBTI":
                ctx = {"mbti": mbti}
                if topic:
                    ctx["topic"] = topic
            elif series in ("DAILY", "ELEMENT"):
                ctx = {"element": element}
                if topic:
                    ctx["topic"] = topic
            elif series in ("LOVE", "CAREER", "SAJU", "SHINJEOM", "JAMIDOSU", "TAROT"):
                ctx = {"topic": topic or f"{series} 운세"}
            if trend_hint:
                ctx["trend_hint"] = trend_hint
            script: ReelsScript = generate_mbti_saju_script(series=series, context=ctx)
        else:
            script: ReelsScript = generate_script(topic)
        print(f"  ✅ 대본 생성 완료 ({time.time() - t0:.1f}초) | {script.title}")
    except Exception as e:
        print(f"  ⚠️ 대본 생성 실패 ({e}). 폴백 대본 사용.")
        script = create_sample_script(topic or f"{series} {mbti}")

    # 한자가 섞여 있으면 TTS가 한글+한자를 중복 발음(예: "토(土)"->"토토")하므로
    # 나레이션에서 한자를 제거합니다. (제목/캡션은 시각 요소이므로 그대로 유지)
    for sc in script.scenes:
        sc.narration = sanitize_narration(sc.narration)

    # 2. 음성 합성
    print("\n[2/7] 🎙️ 한국어 내레이션 음성 합성 중...")
    t0 = time.time()
    audio_result: FullAudioResult = generate_speech(script.scenes)
    print(f"  ✅ 음성 합성 완료 ({time.time() - t0:.1f}초) | {audio_result.total_duration:.1f}초 분량")

    # 3. 비주얼 생성
    print("\n[3/7] 🎨 16:9 비주얼 생성 및 상단 제목 릴스 프레임 합성 중...")
    t0 = time.time()
    visual_result = generate_scene_images(script.scenes, force_mock=mock_images, title=script.title)
    image_paths = visual_result.image_paths
    print(f"  ✅ 비주얼 준비 완료 ({time.time() - t0:.1f}초)")

    # 4. 영상 합성
    print("\n[4/7] 🎬 Ken Burns + 자막 하드코딩 영상 합성 중...")
    t0 = time.time()
    bgm_path = pick_bgm(series, seed=script.title)
    if bgm_path:
        print(f"  🎵 BGM 선택: {bgm_path.name}")
    else:
        print("  ℹ️ assets/bgm/ 에 음원이 없어 BGM 없이 진행합니다.")
    final_video = compose_reels_video(
        image_paths=image_paths,
        scene_results=audio_result.scene_results,
        output_video_path=output_path,
        bgm_path=bgm_path,
    )
    print(f"  ✅ 영상 렌더링 완료 ({time.time() - t0:.1f}초)")

    # 프로필 그리드/릴스 커버용 프레임 (이미지 없이 다크 배경에 제목만 정가운데)
    cover_path = None
    try:
        cover_path = build_reel_cover(None, script.title, Path(output_path).parent / "cover.jpg")
    except Exception as e:
        print(f"  ⚠️ 커버 프레임 생성 실패(무시): {e}")

    # 캡션 저장
    caption_path = Path("assets/output/caption.txt")
    caption_path.parent.mkdir(parents=True, exist_ok=True)
    caption_path.write_text(script.instagram_caption, encoding="utf-8")

    # AI 이미지 생성이 실패해 단색 플레이스홀더가 섞인 영상은 자동 게시하지 않습니다.
    # (강제로 게시하려면 ALLOW_PLACEHOLDER_PUBLISH=true)
    block_publish = visual_result.placeholder_count > 0 and not _env_flag("ALLOW_PLACEHOLDER_PUBLISH")
    if block_publish and (publish_insta or publish_youtube):
        print(f"\n⛔ 플레이스홀더 씬 {visual_result.placeholder_count}개 감지 -> Instagram/YouTube 자동 게시를 건너뜁니다.")
        publish_insta = False
        publish_youtube = False

    # 5. Google Drive 업로드 (보관용)
    drive_result = {}
    if upload_gdrive:
        print("\n[5/7] ☁️ Google Drive 업로드 중...")
        t0 = time.time()
        folder_tag = f"{series}_{mbti or element}_{script.title[:15].strip()}"
        drive_result = upload_reels_assets_to_drive(
            video_path=final_video,
            caption_path=caption_path,
            metadata_path=Path(audio_result.timing_json_path),
            custom_folder_name=folder_tag
        )
        print(f"  ✅ Drive 단계 완료 ({time.time() - t0:.1f}초)")

    # 6. Instagram 릴스 자동 게시
    insta_result = {}
    if publish_insta:
        print("\n[6/7] 📸 Instagram 릴스 게시 시도...")
        t0 = time.time()
        host_res = media_host.upload_public(final_video, kind="video", folder="reels")
        video_direct_url = host_res.get("url", "")

        cover_url = None
        if video_direct_url and cover_path:
            cover_res = media_host.upload_public(cover_path, kind="image", folder="reels_cover")
            cover_url = cover_res.get("url")
            if not cover_url:
                print(f"  ⚠️ 커버 업로드 실패(커버 없이 진행): {cover_res.get('error')}")

        if video_direct_url:
            try:
                insta_result = publish_reel_to_instagram(
                    video_url=video_direct_url,
                    caption=script.instagram_caption,
                    cover_url=cover_url,
                )
                print(f"  ✅ Instagram 게시 단계 완료 ({time.time() - t0:.1f}초)")
                if insta_result.get("id"):
                    record_post(
                        insta_result["id"], "reel", series=series, mbti=mbti if series == "MBTI" else "",
                        topic=topic, title=script.title, hook=script.hook, trend_hint=trend_hint,
                        permalink=insta_result.get("link", ""),
                    )
            except Exception as e:
                print(f"  ⚠️ Instagram 게시 실패: {e}")
                insta_result = {"error": str(e)}
        else:
            print(f"  ⚠️ 공개 비디오 URL 생성 실패로 Instagram 게시를 건너뜁니다: {host_res.get('error')}")
            insta_result = {"error": host_res.get("error", "공개 URL 생성 실패")}

    # 7. YouTube Shorts 자동 게시
    youtube_result = {}
    if publish_youtube:
        print("\n[7/7] ▶️ YouTube Shorts 업로드 시도...")
        t0 = time.time()
        refresh_token = os.getenv("YOUTUBE_REFRESH_TOKEN")
        if refresh_token:
            try:
                youtube_result = upload_shorts_to_youtube(
                    video_path=final_video,
                    title=script.title,
                    description=script.instagram_caption
                )
                print(f"  ✅ YouTube Shorts 업로드 완료 ({time.time() - t0:.1f}초)")
            except Exception as e:
                print(f"  ⚠️ YouTube Shorts 업로드 실패: {e}")
                youtube_result = {"error": str(e)}
        else:
            print("  ℹ️ YOUTUBE_REFRESH_TOKEN 이 미설정되어 YouTube 게시를 건너뜁니다.")
            youtube_result = {"skipped": True, "reason": "YOUTUBE_REFRESH_TOKEN not set"}

    total = time.time() - start_total_time
    print("\n" + "=" * 65)
    print(f"🎉 파이프라인 전체 완료! (총 {total:.1f}초)")
    print(f"📁 비디오 파일: {final_video}")
    if drive_result.get("folder_link"):
        print(f"☁️ Google Drive 링크: {drive_result['folder_link']}")
    if insta_result.get("link"):
        print(f"📸 Instagram 릴스 링크: {insta_result['link']}")
    if youtube_result.get("link"):
        print(f"▶️ YouTube Shorts 링크: {youtube_result['link']}")
    print("=" * 65)

    return {
        "video_path": str(final_video),
        "script": script.model_dump(),
        "total_duration": audio_result.total_duration,
        "caption": script.instagram_caption,
        "gdrive": drive_result,
        "instagram": insta_result,
        "youtube": youtube_result,
        "placeholder_scene_count": visual_result.placeholder_count,
        "total_scene_count": len(image_paths),
        "publish_blocked": block_publish,
    }


def _env_flag(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in ("1", "true", "yes")


def run_carousel_pipeline(
    topic: str = "",
    series: str = "MBTI",
    mbti: str = "ENFP",
    element: str = "목(木)",
    trend_hint: str = "",
    mock_images: bool = False,
    publish_insta: bool = True,
    output_dir: str = "assets/output/carousel",
) -> dict:
    """인스타그램 캐러셀(1080x1350, 5~8장) 대본 -> 표지 이미지 -> 슬라이드 렌더 -> 호스팅 -> 게시."""
    from pipeline.carousel_gen import generate_carousel_script
    from pipeline.carousel_composer import render_carousel
    from pipeline.visual_gen import (
        generate_with_gemini_nanobanana, generate_with_pollinations_flux,
    )

    start = time.time()
    print("\n" + "=" * 65)
    print(f"🖼️ 캐러셀 자동 생성 파이프라인 시작 | 시리즈: {series} | {topic or mbti or element}")
    print("=" * 65)

    ctx = {}
    if series == "MBTI":
        ctx = {"mbti": mbti}
        if topic:
            ctx["topic"] = topic
    elif series in ("DAILY", "ELEMENT"):
        ctx = {"element": element}
        if topic:
            ctx["topic"] = topic
    else:
        ctx = {"topic": topic or f"{series} 운세"}
    if trend_hint:
        ctx["trend_hint"] = trend_hint

    print("\n[1/4] 🧠 캐러셀 대본 기획 중 (Gemini)...")
    script = generate_carousel_script(series=series, context=ctx)
    print(f"  ✅ {script.title} | 슬라이드 {len(script.slides)}장")

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("\n[2/3] 🖌️ 슬라이드 렌더링 중 (표지 이미지 생성 X, 제목 표지 적용)...")
    slide_paths = render_carousel(script, out_dir, cover_image=None)

    caption_path = out_dir / "caption.txt"
    caption_path.write_text(script.instagram_caption, encoding="utf-8")

    insta_result = {}
    if publish_insta:
        print("\n[3/3] 📸 슬라이드 호스팅 및 Instagram 캐러셀 게시...")
        urls = []
        for sp in slide_paths:
            up = media_host.upload_public(sp, kind="image", folder="carousel")
            if not up.get("url"):
                insta_result = {"error": f"슬라이드 업로드 실패: {up.get('error')}"}
                break
            urls.append(up["url"])
        if not insta_result:
            try:
                insta_result = publish_carousel_to_instagram(urls, script.instagram_caption)
                if insta_result.get("id"):
                    record_post(
                        insta_result["id"], "carousel", series=series, mbti=mbti if series == "MBTI" else "",
                        topic=topic, title=script.title, hook=script.slides[0].headline,
                        trend_hint=trend_hint, permalink=insta_result.get("link", ""),
                    )
            except Exception as e:
                insta_result = {"error": str(e)}


    print("\n" + "=" * 65)
    print(f"🎉 캐러셀 파이프라인 완료! (총 {time.time() - start:.1f}초) | 슬라이드 {len(slide_paths)}장")
    if insta_result.get("link"):
        print(f"📸 Instagram 캐러셀 링크: {insta_result['link']}")
    print("=" * 65)

    return {
        "slide_paths": slide_paths,
        "script": script.model_dump(),
        "caption": script.instagram_caption,
        "instagram": insta_result,
        "cover_generated": False,
    }


def main():
    parser = argparse.ArgumentParser(
        description="MBTI×사주 인스타그램 릴스 & 유튜브 숏츠(9:16) 원클릭 자동 제작 CLI"
    )
    parser.add_argument("--series", type=str, default="MBTI",
                        choices=["GENERAL", "MBTI", "DAILY", "LOVE", "CAREER", "ELEMENT",
                                 "SAJU", "SHINJEOM", "JAMIDOSU", "TAROT"],
                        help="콘텐츠 시리즈")
    parser.add_argument("--mbti", type=str, default="ENFP",
                        help="MBTI 유형 (MBTI 시리즈용)")
    parser.add_argument("--element", type=str, default="목(木)",
                        help="오행 (DAILY/ELEMENT 시리즈용)")
    parser.add_argument("--topic", type=str, default="",
                        help="릴스 주제 (LOVE/CAREER/SAJU/SHINJEOM/JAMIDOSU/TAROT/GENERAL용)")
    parser.add_argument("--trend-hint", type=str, default="",
                        help="대본에 자연스럽게 녹여낼 실시간 트렌드 헤드라인 (크롤러 연동용)")
    parser.add_argument("--mock-script", action="store_true",
                        help="Gemini API 없이 샘플 대본으로 테스트")
    parser.add_argument("--mock-images", action="store_true",
                        help="Imagen 3 대신 플레이스홀더로 테스트")
    parser.add_argument("--no-gdrive", action="store_true",
                        help="Google Drive 업로드 건너뛰기")
    parser.add_argument("--no-insta", action="store_true",
                        help="Instagram 게시 건너뛰기")
    parser.add_argument("--no-youtube", action="store_true",
                        help="YouTube Shorts 업로드 건너뛰기")
    parser.add_argument("--output", type=str, default="assets/output/final_reel.mp4",
                        help="출력 영상 파일 경로")
    parser.add_argument("--format", type=str, default="reel", choices=["reel", "carousel"],
                        help="콘텐츠 포맷 (reel: 릴스/숏츠, carousel: 인스타 캐러셀)")

    args = parser.parse_args()

    if args.format == "carousel":
        run_carousel_pipeline(
            topic=args.topic, series=args.series, mbti=args.mbti, element=args.element,
            trend_hint=args.trend_hint, mock_images=args.mock_images,
            publish_insta=not args.no_insta,
        )
        return

    run_pipeline(
        topic=args.topic,
        series=args.series,
        mbti=args.mbti,
        element=args.element,
        trend_hint=args.trend_hint,
        mock_script=args.mock_script,
        mock_images=args.mock_images,
        upload_gdrive=not args.no_gdrive,
        publish_insta=not args.no_insta,
        publish_youtube=not args.no_youtube,
        output_path=args.output
    )


if __name__ == "__main__":
    main()