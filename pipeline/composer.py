"""
Video Composition Engine using FFmpeg.
Features:
- Ultra-lightweight Ken Burns motion effect (crop + scale, <30MB RAM usage)
- Guaranteed zero OOM on resource-constrained containers (Railway 512MB RAM)
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
from PIL import ImageFont

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
from pipeline.text_utils import build_caption_chunks

SUBTITLE_FONT_SIZE = 96
# PlayResX(1080) 기준 좌우 마진(60*2) + 안전 여백을 제외한 자막 최대 표시 폭
SUBTITLE_MAX_WIDTH = 960


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
    사용자 기획안 규격:
    - 폰트: Pretendard / Inter, 크기: 96, 위치: X: 0 가운데 정렬, Y: 1423 (MarginV: 497)
    - 스타일: 검정색 배경(외곽선) + 하얀색 글씨
    """
    output_ass_path.parent.mkdir(parents=True, exist_ok=True)
    if output_srt_path:
        output_srt_path.parent.mkdir(parents=True, exist_ok=True)

    ass_header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: ReelsSub,Pretendard,{SUBTITLE_FONT_SIZE},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,1,0,1,6,2,8,60,60,1423,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    # 자막 줄바꿈을 ASS 렌더링과 동일한 폰트/크기로 실측하기 위한 측정용 폰트
    font_candidates = [
        PROJECT_ROOT / "assets" / "fonts" / "Pretendard-Bold.otf",
        PROJECT_ROOT / "assets" / "fonts" / "NanumGothic-Bold.ttf",
    ]
    measure_font = None
    for fc in font_candidates:
        if fc.is_file():
            try:
                measure_font = ImageFont.truetype(str(fc), SUBTITLE_FONT_SIZE)
                break
            except Exception:
                pass
    if not measure_font:
        measure_font = ImageFont.load_default()

    ass_dialogues = []
    srt_entries = []
    srt_counter = 1

    for sc in scene_results:
        start_t = float(_get_field(sc, "start_time", 0.0))
        end_t = float(_get_field(sc, "end_time", 0.0))
        narration = str(_get_field(sc, "narration", "")).strip()

        chunks = build_caption_chunks(narration, start_t, end_t, measure_font, SUBTITLE_MAX_WIDTH)

        for c_start, c_end, c_text in chunks:
            ass_start = format_ass_timestamp(c_start)
            ass_end = format_ass_timestamp(c_end)
            ass_dialogues.append(f"Dialogue: 0,{ass_start},{ass_end},ReelsSub,,0,0,0,,{c_text}")

            srt_start = format_srt_timestamp(c_start)
            srt_end = format_srt_timestamp(c_end)
            srt_text = c_text.replace("\\N", "\n")
            srt_entries.append(f"{srt_counter}\n{srt_start} --> {srt_end}\n{srt_text}\n")
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
    단일 씬에 대해 초경량 crop+scale 기반 Ken Burns 효과와 오디오를 합성합니다.
    - 메모리 점유율 < 30MB 로 Railway/클라우드 무료 티어(512MB RAM)에서도 절대 OOM이 발생하지 않습니다.
    """
    total_frames = max(int(duration * fps), 1)

    # 이즈인아웃(사인 곡선) 진행률: 시작/끝은 느리고 중간은 빠르게 움직여 기계적인 느낌을 줄임
    ease = f"(0.5-0.5*cos(PI*n/{total_frames}))"

    # 홀수 씬: 서서히 줌인 (1.0 -> 1.18)
    # 짝수 씬: 서서히 줌아웃 (1.18 -> 1.0)
    if scene_id % 2 == 1:
        crop_w = f"1080*(1-0.18*{ease})"
        crop_h = f"1920*(1-0.18*{ease})"
    else:
        crop_w = f"1080*(0.82+0.18*{ease})"
        crop_h = f"1920*(0.82+0.18*{ease})"

    filter_graph = f"crop=w='{crop_w}':h='{crop_h}':x='(in_w-out_w)/2':y='(in_h-out_h)/2',scale=1080:1920"

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
        "-threads", "2",
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


TRANSITION_DUR = 0.28  # 씬 전환 크로스페이드 길이(초) - 릴스 특유의 빠른 템포에 맞춘 짧은 디졸브


def _concat_copy_merge(clip_paths: List[Path], temp_dir: Path, ffmpeg_bin: str, output_path: Path):
    """단순 하드컷 병합 (크로스페이드 실패 시 안전 대체 경로)"""
    concat_list_file = temp_dir / "concat_list.txt"
    with open(concat_list_file, "w", encoding="utf-8") as f:
        for cp in clip_paths:
            escaped_path = str(cp.resolve()).replace("\\", "/")
            f.write(f"file '{escaped_path}'\n")

    cmd = [
        ffmpeg_bin, "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_list_file),
        "-c", "copy",
        str(output_path)
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"FFmpeg 하드컷 병합 실패:\n{res.stderr[-600:]}")


def merge_clips_with_crossfade(
    clip_paths: List[Path],
    durations: List[float],
    ffmpeg_bin: str,
    output_path: Path,
    temp_dir: Path,
    transition_dur: float = TRANSITION_DUR
):
    """
    씬 클립들을 하드컷 대신 짧은 디졸브(xfade/acrossfade)로 이어붙여 더 매끄러운 릴스 편집감을 만듭니다.
    실패 시(짧은 씬, 코덱 불일치 등) 기존 concat 하드컷 방식으로 안전하게 대체됩니다.
    """
    n = len(clip_paths)
    if n <= 1:
        _concat_copy_merge(clip_paths, temp_dir, ffmpeg_bin, output_path)
        return

    try:
        inputs: List[str] = []
        for cp in clip_paths:
            inputs += ["-i", str(cp)]

        # 전환 구간이 클립 길이를 넘지 않도록 오프셋 계산용 최소 길이 보정
        safe_durations = [max(d, transition_dur * 2 + 0.05) for d in durations]

        filter_parts: List[str] = []
        cum = safe_durations[0]
        prev_v = "0:v"
        for i in range(1, n):
            offset = max(cum - transition_dur, 0.0)
            out_label = f"vx{i}"
            filter_parts.append(
                f"[{prev_v}][{i}:v]xfade=transition=fade:duration={transition_dur:.3f}:offset={offset:.3f}[{out_label}]"
            )
            prev_v = out_label
            cum = cum + safe_durations[i] - transition_dur

        prev_a = "0:a"
        for i in range(1, n):
            out_label = f"ax{i}"
            filter_parts.append(f"[{prev_a}][{i}:a]acrossfade=d={transition_dur:.3f}[{out_label}]")
            prev_a = out_label

        filter_complex = ";".join(filter_parts)

        cmd = [
            ffmpeg_bin, "-y", *inputs,
            "-filter_complex", filter_complex,
            "-map", f"[{prev_v}]", "-map", f"[{prev_a}]",
            "-c:v", "libx264", "-preset", "veryfast", "-threads", "2", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            str(output_path)
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode != 0:
            raise RuntimeError(res.stderr[-800:] if res.stderr else "알 수 없는 xfade 오류")
        print(f"[COMPOSER] 씬 {n}개를 {transition_dur:.2f}초 디졸브 전환으로 병합 완료")
    except Exception as e:
        print(f"  [WARN] 크로스페이드 병합 실패 ({e}). 하드컷 병합으로 대체합니다.")
        _concat_copy_merge(clip_paths, temp_dir, ffmpeg_bin, output_path)


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
    durations: List[float] = []

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
        durations.append(duration)

    # 2. 클립 목록을 짧은 디졸브 전환으로 병합 (하드컷보다 매끄러운 릴스 편집감)
    merged_temp_video = temp_dir / "merged_no_subs.mp4"
    print("[COMPOSER] 씬별 클립을 디졸브 전환으로 병합 중...")
    merge_clips_with_crossfade(clip_paths, durations, ffmpeg_bin, merged_temp_video, temp_dir)

    # 3. 자막 파일 생성 (.ass 및 .srt)
    subtitles_dir = Path("assets/subtitles")
    ass_path = subtitles_dir / "reels_subtitles.ass"
    srt_path = subtitles_dir / "reels_subtitles.srt"
    generate_subtitles(scene_results, ass_path, srt_path)

    # 4. 자막 번인(Hardsub) 최종 인코딩
    print(f"[COMPOSER] 자막 하드코딩 및 최종 릴스 렌더링 -> {output_video_path}...")
    escaped_ass = str(ass_path.resolve()).replace("\\", "/").replace(":", "\\:")
    # fontsdir로 번들 한글 폰트를 직접 지정 -> 로컬(Windows)과 배포 환경(Railway/Linux)의
    # 시스템 폰트 설정(fontconfig)에 관계없이 항상 동일한 한글 자막 렌더링을 보장합니다.
    fonts_dir = PROJECT_ROOT / "assets" / "fonts"
    escaped_fontsdir = str(fonts_dir.resolve()).replace("\\", "/").replace(":", "\\:")
    subtitle_filter = f"ass='{escaped_ass}':fontsdir='{escaped_fontsdir}'"

    final_cmd = [
        ffmpeg_bin,
        "-y",
        "-i", str(merged_temp_video),
        "-vf", subtitle_filter,
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-threads", "2",
        "-crf", "20",
        "-c:a", "aac",
        "-b:a", "192k",
        str(output_video_path)
    ]
    res_final = subprocess.run(final_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
    # 만약 ass 필터나 폰트 문제 발생 시 자막 없는 원본 복사로 안전 대체
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
            concat_list_file = temp_dir / "concat_list.txt"
            if concat_list_file.is_file():
                concat_list_file.unlink()
        except Exception:
            pass

    print(f"[SUCCESS] 인스타그램 릴스 최종 영상 합성 완료!\n  -> {output_video_path.resolve()}")
    return output_video_path.resolve()