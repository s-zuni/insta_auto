"""
Instagram Reels Automation Pipeline Orchestrator.
MBTI x Saju Content -> TTS -> Visuals -> FFmpeg Composition -> Google Drive Upload -> Instagram Reels Publish
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
from pipeline.tts_engine import generate_speech, FullAudioResult
from pipeline.visual_gen import generate_scene_images
from pipeline.composer import compose_reels_video
from pipeline.gdrive_uploader import upload_reels_assets_to_drive
from pipeline.insta_publisher import publish_reel_to_instagram


def run_pipeline(
    topic: str = "",
    series: str = "MBTI",
    mbti: str = "ENFP",
    element: str = "목(木)",
    mock_script: bool = False,
    mock_images: bool = False,
    upload_gdrive: bool = True,
    publish_insta: bool = True,
    output_path: str = "assets/output/final_reel.mp4"
) -> dict:
    """인스타그램 릴스 생성 및 배포 파이프라인 전체를 원스톱으로 실행합니다."""
    start_total_time = time.time()
    print("\n" + "=" * 65)
    print("🚀 MBTI × 사주 인스타그램 릴스(9:16) 자동 생성 파이프라인 시작")
    print(f"📌 시리즈: {series} | {topic or mbti or element}")
    print("=" * 65)

    if not check_ffmpeg():
        raise RuntimeError("FFmpeg가 준비되지 않았습니다. 설치를 완료한 후 다시 시도하세요.")

    # 1. 대본 기획
    print("\n[1/6] 🧠 릴스 대본 기획 중 (Gemini)...")
    t0 = time.time()
    try:
        if mock_script:
            print("  ℹ️  --mock-script 모드")
            script: ReelsScript = create_sample_script(topic or f"{series} {mbti}")
        elif series != "GENERAL":
            ctx = {}
            if series == "MBTI":
                ctx = {"mbti": mbti}
            elif series in ("DAILY", "ELEMENT"):
                ctx = {"element": element}
            elif series in ("LOVE", "CAREER"):
                ctx = {"topic": topic or f"{series} 운세"}
            script: ReelsScript = generate_mbti_saju_script(series=series, context=ctx)
        else:
            script: ReelsScript = generate_script(topic)
        print(f"  ✅ 대본 생성 완료 ({time.time() - t0:.1f}초) | {script.title}")
    except Exception as e:
        print(f"  ⚠️ 대본 생성 실패 ({e}). 폴백 대본 사용.")
        script = create_sample_script(topic or f"{series} {mbti}")

    # 2. 음성 합성
    print("\n[2/6] 🎙️ 한국어 내레이션 음성 합성 중...")
    t0 = time.time()
    audio_result: FullAudioResult = generate_speech(script.scenes)
    print(f"  ✅ 음성 합성 완료 ({time.time() - t0:.1f}초) | {audio_result.total_duration:.1f}초 분량")

    # 3. 비주얼 생성
    print("\n[3/6] 🎨 9:16 비주얼 에셋 생성 중...")
    t0 = time.time()
    image_paths = generate_scene_images(script.scenes, force_mock=mock_images)
    print(f"  ✅ 비주얼 준비 완료 ({time.time() - t0:.1f}초)")

    # 4. 영상 합성
    print("\n[4/6] 🎬 Ken Burns + 자막 하드코딩 영상 합성 중...")
    t0 = time.time()
    final_video = compose_reels_video(
        image_paths=image_paths,
        scene_results=audio_result.scene_results,
        output_video_path=output_path
    )
    print(f"  ✅ 영상 렌더링 완료 ({time.time() - t0:.1f}초)")

    # 캡션 저장
    caption_path = Path("assets/output/caption.txt")
    caption_path.parent.mkdir(parents=True, exist_ok=True)
    caption_path.write_text(script.instagram_caption, encoding="utf-8")

    # 5. Google Drive 업로드
    drive_result = {}
    if upload_gdrive:
        print("\n[5/6] ☁️ Google Drive 업로드 중...")
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
        print("\n[6/6] 📸 Instagram 릴스 게시 시도...")
        t0 = time.time()
        # Drive의 직접 다운로드 URL 확보
        video_direct_url = ""
        if isinstance(drive_result, dict) and "video" in drive_result:
            video_direct_url = drive_result["video"].get("direct_url", "")

        if video_direct_url:
            try:
                insta_result = publish_reel_to_instagram(
                    video_url=video_direct_url,
                    caption=script.instagram_caption
                )
                print(f"  ✅ Instagram 게시 단계 완료 ({time.time() - t0:.1f}초)")
            except Exception as e:
                print(f"  ⚠️ Instagram 게시 실패: {e}")
                insta_result = {"error": str(e)}
        else:
            print("  ℹ️ 공개 비디오 다운로드 URL이 없어 Instagram 게시를 건너뜁니다.")
            insta_result = {"skipped": True, "reason": "No public video URL from Drive"}

    total = time.time() - start_total_time
    print("\n" + "=" * 65)
    print(f"🎉 파이프라인 전체 완료! (총 {total:.1f}초)")
    print(f"📁 비디오 파일: {final_video}")
    if drive_result.get("folder_link"):
        print(f"☁️ Google Drive 링크: {drive_result['folder_link']}")
    if insta_result.get("link"):
        print(f"📸 Instagram 릴스 링크: {insta_result['link']}")
    print("=" * 65)

    return {
        "video_path": str(final_video),
        "script": script.model_dump(),
        "total_duration": audio_result.total_duration,
        "caption": script.instagram_caption,
        "gdrive": drive_result,
        "instagram": insta_result
    }


def main():
    parser = argparse.ArgumentParser(
        description="MBTI×사주 인스타그램 릴스(9:16) 원클릭 자동 제작 CLI"
    )
    parser.add_argument("--series", type=str, default="MBTI",
                        choices=["GENERAL", "MBTI", "DAILY", "LOVE", "CAREER", "ELEMENT"],
                        help="콘텐츠 시리즈")
    parser.add_argument("--mbti", type=str, default="ENFP",
                        help="MBTI 유형 (MBTI 시리즈용)")
    parser.add_argument("--element", type=str, default="목(木)",
                        help="오행 (DAILY/ELEMENT 시리즈용)")
    parser.add_argument("--topic", type=str, default="",
                        help="릴스 주제 (LOVE/CAREER/GENERAL용)")
    parser.add_argument("--mock-script", action="store_true",
                        help="Gemini API 없이 샘플 대본으로 테스트")
    parser.add_argument("--mock-images", action="store_true",
                        help="Imagen 3 대신 플레이스홀더로 테스트")
    parser.add_argument("--no-gdrive", action="store_true",
                        help="Google Drive 업로드 건너뛰기")
    parser.add_argument("--no-insta", action="store_true",
                        help="Instagram 게시 건너뛰기")
    parser.add_argument("--output", type=str, default="assets/output/final_reel.mp4",
                        help="출력 영상 파일 경로")

    args = parser.parse_args()

    run_pipeline(
        topic=args.topic,
        series=args.series,
        mbti=args.mbti,
        element=args.element,
        mock_script=args.mock_script,
        mock_images=args.mock_images,
        upload_gdrive=not args.no_gdrive,
        publish_insta=not args.no_insta,
        output_path=args.output
    )


if __name__ == "__main__":
    main()