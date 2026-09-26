"""
Video Composition Engine using FFmpeg.
Features:
- Smooth Ken Burns motion effect (zoom-in / zoom-out per scene)
- High-efficiency encoding optimized for Railway/Cloud and Local environments
- ASS / SRT subtitle generation and hardsub burn-in
- 1080x1920 9:16 vertical Reels formatting
"""
import os
import sys
import json
import subprocess
from pathlib import Path
from typing import List, Optional
from dotenv import load_dotenv

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.ffmpeg_check import get_ffmpeg_path


def format_ass_timestamp(seconds: float) -> str:
    """초 단위를 ASS 타임스탬프 형식 (H:MM:SS.cs)으로 변환"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centis = int(round((seconds - int(seconds)) * 100))
    if centis == 100:
        secs += 1
        centis = 0
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"


def format_srt_timestamp(seconds: float) -> str:
    """초 단위를 SRT 타임스탬프 형식 (HH:MM:SS,mmm)으로 변환"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    if millis == 1000:
        secs += 1
        millis = 0
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _get_field(obj, key, default=None):
    if hasattr(obj, key):
        return getattr(obj, key)
    if isinstance(obj, dict):
        return obj.get(key, default)
    return default


def generate_subtitles(
    scene_results: list,
    output_ass_path: Path,
    output_srt_path: Optional[Path] = None
):
    """
    씬별 타임스탬프와 대사를 바탕으로 모바일 가독성이 뛰어난 ASS 및 SRT 자막을 생성합니다.
    """
    output_ass_path.parent.mkdir(parents=True, exist_ok=True)
    if output_srt_path:
        output_srt_path.parent.mkdir(parents=True, exist_ok=True)

    ass_header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: ReelsSub,Sans,62,&H00FFFFFF,&H000000FF,&H00000000,&H90000000,-1,0,0,0,100,100,1,0,1,5,3,2,80,80,340,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ass_dialogues = []
    srt_entries = []
    srt_counter = 1

    for sc in scene_results:
        start_t = float(_get_field(sc, "start_time", 0.0))
        end_t = float(_get_field(sc, "end_time", 0.0))
        duration = float(_get_field(sc, "duration", 0.0))
        narration = str(_get_field(sc, "narration", "")).strip()

        words = narration.split()
        if len(words) > 7 and duration > 3.0:
            mid = len(words) // 2
            part1 = " ".join(words[:mid])
            part2 = " ".join(words[mid:])
            mid_t = start_t + (duration * 0.5)
            chunks = [
                (start_t, mid_t, part1),
                (mid_t, end_t, part2)
            ]
        else:
            chunks = [(start_t, end_t, narration)]

        for c_start, c_end, c_text in chunks:
            ass_start = format_ass_timestamp(c_start)
            ass_end = format_ass_timestamp(c_end)
            ass_dialogues.append(f"Dialogue: 0,{ass_start},{ass_end},ReelsSub,,0,0,0,,{c_text}")

            srt_start = format_srt_timestamp(c_start)
            srt_end = format_srt_timestamp(c_end)
            srt_entries.append(f"{srt_counter}\n{srt_start} --> {srt_end}\n{c_text}\n")
            srt_counter += 1

    with open(output_ass_path, "w", encoding="utf-8") as f:
        f.write(ass_header + "\n".join(ass_dialogues) + "\n")

    if output_srt_path:
        with open(output_srt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(srt_entries) + "\n")

    print(f"[SUBTITLE] 자막 생성 완료: {output_ass_path.name}")


def render_scene_clip(
    image_path: str,
    audio_path: str,
    duration: float,
    output_clip_path: Path,
    scene_id: int,
    ffmpeg_bin: str,
    fps: int = 30
):
    """
    단일 씬에 대해 Ken Burns 효과와 오디오를 합성합니다.
    d=1 설정을 통해 OOM(메모리 초과) 및 프레임 폭발 현상을 방지합니다.
    """
    if scene_id % 2 == 1:
        zoom_expr = "min(pzoom+0.0015,1.15)"
    else:
        zoom_expr = "max(1.15-0.0015*on/100,1.0)"

    filter_graph = (
        "scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,"
        f"zoompan=z='{zoom_expr}':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1920:fps={fps}"
    )

    cmd = [
        ffmpeg_bin,
        "-y",
        "-loop", "1",
        "-t", f"{duration:.3f}",
        "-i", str(image_path),
        "-i", str(audio_path),
        "-vf", filter_graph,
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        str(output_clip_path)
    ]

    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        err_msg = res.stderr[-600:] if res.stderr else "알 수 없는 FFmpeg 오류"
        raise RuntimeError(f"FFmpeg 씬 {scene_id} 클립 생성 실패 (code {res.returncode}):\n{err_msg}")


def compose_reels_video(
    image_paths: List[str],
    scene_results: list,
    output_video_path: Optional[str | Path] = None,
    keep_temp: bool = False
) -> Path:
    """
    씬별 이미지와 음성을 합성하고, 자막을 번인(Hardcode)하여 최종 릴스 영상을 출력합니다.
    """
    ffmpeg_bin = get_ffmpeg_path()
    if not ffmpeg_bin:
        raise RuntimeError("FFmpeg 실행 파일을 찾을 수 없습니다. utils.ffmpeg_check를 확인하세요.")

    if output_video_path is None:
        output_video_path = Path("assets/output/final_reel.mp4")
    else:
        output_video_path = Path(output_video_path)

    output_video_path.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = output_video_path.parent / "temp_clips"
    temp_dir.mkdir(parents=True, exist_ok=True)

    print(f"[COMPOSER] 총 {len(scene_results)}개 씬 비디오 클립 렌더링 시작...")
    clip_paths: List[Path] = []

    # 1. 씬별 개별 클립 렌더링
    for idx, (img_p, sc) in enumerate(zip(image_paths, scene_results)):
        scene_id = int(_get_field(sc, "scene_id", idx + 1))
        duration = float(_get_field(sc, "duration", 5.0))
        audio_p = str(_get_field(sc, "audio_path", ""))

        clip_p = temp_dir / f"clip_{scene_id:02d}.mp4"
        print(f"  [RENDER] 씬 {scene_id} ({duration:.2f}초) Ken Burns 클립 생성 중...")
        render_scene_clip(
            image_path=img_p,
            audio_path=audio_p,
            duration=duration,
            output_clip_path=clip_p,
            scene_id=scene_id,
            ffmpeg_bin=ffmpeg_bin
        )
        clip_paths.append(clip_p)

    # 2. 클립 목록 병합 (Concat demuxer)
    concat_list_file = temp_dir / "concat_list.txt"
    with open(concat_list_file, "w", encoding="utf-8") as f:
        for cp in clip_paths:
            escaped_path = str(cp.resolve()).replace("\\", "/")
            f.write(f"file '{escaped_path}'\n")

    merged_temp_video = temp_dir / "merged_no_subs.mp4"
    print("[COMPOSER] 씬별 클립을 연속 영상으로 병합 중...")
    concat_cmd = [
        ffmpeg_bin,
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_list_file),
        "-c", "copy",
        str(merged_temp_video)
    ]
    res_concat = subprocess.run(concat_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res_concat.returncode != 0:
        raise RuntimeError(f"FFmpeg 클립 병합 실패:\n{res_concat.stderr[-600:]}")

    # 3. 자막 파일 생성 (.ass 및 .srt)
    subtitles_dir = Path("assets/subtitles")
    ass_path = subtitles_dir / "reels_subtitles.ass"
    srt_path = subtitles_dir / "reels_subtitles.srt"
    generate_subtitles(scene_results, ass_path, srt_path)

    # 4. 자막 번인(Hardsub) 최종 인코딩
    print(f"[COMPOSER] 자막 하드코딩 및 최종 릴스 렌더링 -> {output_video_path}...")
    escaped_ass = str(ass_path.resolve()).replace("\\", "/").replace(":", "\\:")
    subtitle_filter = f"ass='{escaped_ass}'"

    final_cmd = [
        ffmpeg_bin,
        "-y",
        "-i", str(merged_temp_video),
        "-vf", subtitle_filter,
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "20",
        "-c:a", "aac",
        "-b:a", "192k",
        str(output_video_path)
    ]
    res_final = subprocess.run(final_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
    # 만약 ass 필터가 지원되지 않거나 폰트 문제로 실패한 경우 자막 없이 원본 저장
    if res_final.returncode != 0:
        print(f"  [WARN] 자막 번인 실패 ({res_final.stderr[-300:]}). 무자막 원본으로 대체합니다.")
        import shutil
        shutil.copy2(merged_temp_video, output_video_path)

    # 임시 파일 정리
    if not keep_temp:
        try:
            for c in clip_paths:
                if c.is_file():
                    c.unlink()
            if merged_temp_video.is_file():
                merged_temp_video.unlink()
            if concat_list_file.is_file():
                concat_list_file.unlink()
        except Exception:
            pass

    print(f"[SUCCESS] 인스타그램 릴스 최종 영상 합성 완료!\n  -> {output_video_path.resolve()}")
    return output_video_path.resolve()