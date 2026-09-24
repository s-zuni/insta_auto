"""
Instagram Reels Automation Pipeline CLI.
End-to-End Orchestrator:
Topic -> Gemini Script Planning -> TTS Audio & Timings -> Imagen 3 Visuals -> FFmpeg Ken Burns & Subtitle Composition
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
from pipeline.tts_engine import generate_speech, FullAudioResult
from pipeline.visual_gen import generate_scene_images
from pipeline.composer import compose_reels_video


def run_pipeline(
    topic: str,
    mock_script: bool = False,
    mock_images: bool = False,
    output_path: str = "assets/output/final_reel.mp4"
) -> dict:
    """
    인스타그램 릴스 생성 파이프라인 전체를 원스톱으로 실행합니다.
    """
    start_total_time = time.time()
    print("\n" + "=" * 65)
    print("🚀 인스타그램 릴스(9:16) 자동 생성 파이프라인을 시작합니다.")
    print(f"📌 주제: '{topic}'")
    print("=" * 65)

    # 0. 시스템 사전 점검 (FFmpeg)
    if not check_ffmpeg():
        raise RuntimeError("FFmpeg가 준비되지 않았습니다. 설치를 완료한 후 다시 시도하세요.")

    # 1. 대본 기획 (Gemini 2.5/3.1 Structured Outputs)
    print("\n[1/4] 🧠 릴스 대본 및 씬 기획 중 (Gemini)...")
    t0 = time.time()
    try:
        if mock_script:
            print("  ℹ️  --mock-script 모드로 동작합니다.")
            script: ReelsScript = create_sample_script(topic)
        else:
            script: ReelsScript = generate_script(topic)
        print(f"  ✅ 대본 생성 완료 ({time.time() - t0:.1f}초)")
        print(f"     제목: {script.title}")
        print(f"     후킹 대사: {script.hook}")
        print(f"     총 씬 수: {len(script.scenes)}개")
    except Exception as e:
        print(f"  ⚠️ Gemini API 호출 실패 ({e}). 오프라인 샘플 대본으로 자동 대체합니다.")
        script = create_sample_script(topic)

    # 2. 음성 합성 및 타이밍 분석 (Google Cloud TTS / Neural Fallback)
    print("\n[2/4] 🎙️ 한국어 내레이션 음성 합성 및 자막 싱크 추출 중...")
    t0 = time.time()
    audio_result: FullAudioResult = generate_speech(script.scenes)
    print(f"  ✅ 음성 합성 완료 ({time.time() - t0:.1f}초)")
    print(f"     전체 오디오 길이: {audio_result.total_duration:.2f}초")
    print(f"     오디오 파일: {audio_result.audio_path}")

    # 3. 비주얼 이미지 생성 (Vertex AI Imagen 3)
    print("\n[3/4] 🎨 9:16 세로형 비주얼 에셋(Imagen 3) 생성 중...")
    t0 = time.time()
    image_paths = generate_scene_images(script.scenes, force_mock=mock_images)
    print(f"  ✅ 비주얼 에셋 준비 완료 ({time.time() - t0:.1f}초)")

    # 4. FFmpeg 영상 합성 & 자막 하드코딩
    print("\n[4/4] 🎬 Ken Burns 모션 적용 및 스타일 자막 하드코딩 렌더링 중...")
    t0 = time.time()
    final_video = compose_reels_video(
        image_paths=image_paths,
        scene_results=audio_result.scene_results,
        output_video_path=output_path
    )
    print(f"  ✅ 최종 영상 렌더링 완료 ({time.time() - t0:.1f}초)")

    total_elapsed = time.time() - start_total_time
    print("\n" + "=" * 65)
    print(f"🎉 릴스 제작이 모두 완료되었습니다! (총 소요 시간: {total_elapsed:.1f}초)")
    print(f"📁 최종 완성본: {final_video}")
    print("=" * 65)
    print("\n📋 [인스타그램 업로드용 본문 캡션]")
    print("-" * 50)
    print(script.instagram_caption)
    print("-" * 50)

    # 캡션을 텍스트 파일로도 저장
    caption_path = Path("assets/output/caption.txt")
    caption_path.write_text(script.instagram_caption, encoding="utf-8")
    print(f"💡 캡션이 텍스트 파일로 저장되었습니다 -> {caption_path.resolve()}\n")

    return {
        "video_path": str(final_video),
        "script": script.model_dump(),
        "total_duration": audio_result.total_duration,
        "caption": script.instagram_caption
    }


def main():
    parser = argparse.ArgumentParser(
        description="인스타그램 릴스(9:16) 원클릭 자동 제작 CLI 파이프라인"
    )
    parser.add_argument(
        "--topic",
        type=str,
        default="AI로 생산성 10배 올리는 3가지 비밀",
        help="제작할 릴스의 주제"
    )
    parser.add_argument(
        "--mock-script",
        action="store_true",
        help="Gemini API 호출 없이 샘플 대본으로 빠른 파이프라인 테스트"
    )
    parser.add_argument(
        "--mock-images",
        action="store_true",
        help="Imagen 3 API 대신 플레이스홀더 그래픽으로 빠른 테스트"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="assets/output/final_reel.mp4",
        help="출력할 최종 영상 파일 경로"
    )

    args = parser.parse_args()

    run_pipeline(
        topic=args.topic,
        mock_script=args.mock_script,
        mock_images=args.mock_images,
        output_path=args.output
    )


if __name__ == "__main__":
    main()

