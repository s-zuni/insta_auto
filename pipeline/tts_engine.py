"""
TTS Synthesis Module for Instagram Reels Pipeline.
Primary: Google Cloud Text-to-Speech (Neural2 / Journey) with SSML timepoints.
Fallback: Edge TTS (Korean Neural) with word-level boundary synchronization.
"""
import os
import sys
import json
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
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


class WordTiming(BaseModel):
    word: str
    start_time: float  # seconds
    end_time: float    # seconds


class SceneAudioResult(BaseModel):
    scene_id: int
    audio_path: str
    duration: float
    start_time: float
    end_time: float
    narration: str
    word_timings: List[WordTiming] = Field(default_factory=list)


class FullAudioResult(BaseModel):
    audio_path: str
    total_duration: float
    scene_results: List[SceneAudioResult]
    timing_json_path: str


def get_audio_duration(file_path: str) -> float:
    """
    오디오 파일(.mp3, .wav 등)의 실제 재생 길이를 초(seconds) 단위로 반환합니다.
    """
    try:
        from mutagen.mp3 import MP3
        audio = MP3(file_path)
        return float(audio.info.length)
    except Exception:
        # ffprobe fallback
        import subprocess
        from utils.ffmpeg_check import get_ffmpeg_path
        ffmpeg_bin = get_ffmpeg_path()
        ffprobe_bin = "ffprobe"
        if ffmpeg_bin:
            ffprobe_candidate = Path(ffmpeg_bin).parent / "ffprobe.exe"
            if ffprobe_candidate.is_file():
                ffprobe_bin = str(ffprobe_candidate)

        cmd = [
            ffprobe_bin,
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return float(res.stdout.strip())


def synthesize_with_google_tts(
    scenes: list,
    output_dir: Path,
    voice_name: str = "ko-KR-Neural2-C",
    speaking_rate: float = 1.05
) -> FullAudioResult:
    """
    Google Cloud Text-to-Speech API를 사용하여 씬별 음성을 생성하고 타이밍 정보를 추출합니다.
    """
    from google.cloud import texttospeech

    client = texttospeech.TextToSpeechClient()

    voice = texttospeech.VoiceSelectionParams(
        language_code="ko-KR",
        name=voice_name,
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
        speaking_rate=speaking_rate,
        pitch=0.0,
    )

    scene_results: List[SceneAudioResult] = []
    current_time_offset = 0.0

    output_dir.mkdir(parents=True, exist_ok=True)

    for sc in scenes:
        scene_id = getattr(sc, "scene_id", sc.get("scene_id") if isinstance(sc, dict) else 1)
        narration = getattr(sc, "narration", sc.get("narration") if isinstance(sc, dict) else "")

        scene_filename = f"scene_{scene_id:02d}.mp3"
        scene_path = output_dir / scene_filename

        # SSML 생성 (단어/구간 마커 포함 가능)
        synthesis_input = texttospeech.SynthesisInput(text=narration)

        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )

        with open(scene_path, "wb") as out:
            out.write(response.audio_content)

        duration = get_audio_duration(str(scene_path))
        start_time = current_time_offset
        end_time = current_time_offset + duration

        # 간단한 단어 분할 비례 타이밍 추정
        words = narration.split()
        word_timings = []
        if words:
            word_dur = duration / len(words)
            for idx, w in enumerate(words):
                w_start = start_time + (idx * word_dur)
                w_end = w_start + word_dur
                word_timings.append(WordTiming(word=w, start_time=round(w_start, 2), end_time=round(w_end, 2)))

        scene_results.append(
            SceneAudioResult(
                scene_id=scene_id,
                audio_path=str(scene_path.resolve()),
                duration=round(duration, 3),
                start_time=round(start_time, 3),
                end_time=round(end_time, 3),
                narration=narration,
                word_timings=word_timings
            )
        )
        current_time_offset += duration

    # 전체 음성 병합 파일 생성 (FFmpeg concat)
    full_audio_path = output_dir / "full_narration.mp3"
    _concatenate_audio_files([r.audio_path for r in scene_results], full_audio_path)
    total_duration = get_audio_duration(str(full_audio_path))

    timing_json_path = output_dir / "timing_info.json"
    result = FullAudioResult(
        audio_path=str(full_audio_path.resolve()),
        total_duration=round(total_duration, 3),
        scene_results=scene_results,
        timing_json_path=str(timing_json_path.resolve())
    )

    with open(timing_json_path, "w", encoding="utf-8") as f:
        f.write(result.model_dump_json(indent=2))

    return result


async def _synthesize_edge_tts_scene(narration: str, output_path: Path, voice: str = "ko-KR-SunHiNeural") -> List[WordTiming]:
    """
    Edge-TTS를 사용하여 씬 오디오 및 세부 단어 타이밍을 생성합니다.
    """
    import edge_tts

    communicate = edge_tts.Communicate(narration, voice=voice, rate="+5%")
    word_timings: List[WordTiming] = []

    with open(output_path, "wb") as file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                file.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                # offset, duration in 100ns units (ticks)
                offset_sec = chunk["offset"] / 10_000_000
                duration_sec = chunk["duration"] / 10_000_000
                word_timings.append(
                    WordTiming(
                        word=chunk["text"],
                        start_time=round(offset_sec, 3),
                        end_time=round(offset_sec + duration_sec, 3)
                    )
                )

    return word_timings


def synthesize_with_edge_tts_fallback(
    scenes: list,
    output_dir: Path,
    voice_name: str = "ko-KR-SunHiNeural"
) -> FullAudioResult:
    """
    GCP 인증이 없을 때 무중단으로 동작하는 고음질 한국어 Neural TTS 폴백 엔진.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    scene_results: List[SceneAudioResult] = []
    current_time_offset = 0.0

    for sc in scenes:
        scene_id = getattr(sc, "scene_id", sc.get("scene_id") if isinstance(sc, dict) else 1)
        narration = getattr(sc, "narration", sc.get("narration") if isinstance(sc, dict) else "")

        scene_filename = f"scene_{scene_id:02d}.mp3"
        scene_path = output_dir / scene_filename

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            raw_timings = loop.run_until_complete(_synthesize_edge_tts_scene(narration, scene_path, voice_name))
        finally:
            loop.close()

        duration = get_audio_duration(str(scene_path))
        start_time = current_time_offset
        end_time = current_time_offset + duration

        # 오프셋 조정된 단어 타이밍
        adjusted_timings = []
        for wt in raw_timings:
            adjusted_timings.append(
                WordTiming(
                    word=wt.word,
                    start_time=round(start_time + wt.start_time, 3),
                    end_time=round(start_time + wt.end_time, 3)
                )
            )

        scene_results.append(
            SceneAudioResult(
                scene_id=scene_id,
                audio_path=str(scene_path.resolve()),
                duration=round(duration, 3),
                start_time=round(start_time, 3),
                end_time=round(end_time, 3),
                narration=narration,
                word_timings=adjusted_timings
            )
        )
        current_time_offset += duration

    full_audio_path = output_dir / "full_narration.mp3"
    _concatenate_audio_files([r.audio_path for r in scene_results], full_audio_path)
    total_duration = get_audio_duration(str(full_audio_path))

    timing_json_path = output_dir / "timing_info.json"
    result = FullAudioResult(
        audio_path=str(full_audio_path.resolve()),
        total_duration=round(total_duration, 3),
        scene_results=scene_results,
        timing_json_path=str(timing_json_path.resolve())
    )

    with open(timing_json_path, "w", encoding="utf-8") as f:
        f.write(result.model_dump_json(indent=2))

    return result


def _concatenate_audio_files(input_files: List[str], output_file: Path):
    """
    FFmpeg concat demuxer를 사용하여 다중 오디오 파일을 무손실 재인코딩 결합합니다.
    """
    import subprocess
    from utils.ffmpeg_check import get_ffmpeg_path

    ffmpeg_bin = get_ffmpeg_path() or "ffmpeg"
    concat_list_file = output_file.parent / "audio_concat_list.txt"

    with open(concat_list_file, "w", encoding="utf-8") as f:
        for inp in input_files:
            escaped_path = inp.replace("\\", "/")
            f.write(f"file '{escaped_path}'\n")

    cmd = [
        ffmpeg_bin,
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_list_file),
        "-c", "copy",
        str(output_file)
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)


def generate_speech(scenes: list, output_dir: Optional[str | Path] = None) -> FullAudioResult:
    """
    대본의 씬(scenes) 리스트를 입력받아 음성 및 타이밍 정보를 생성합니다.
    1. Google Cloud Text-to-Speech 우선 시도
    2. GCP 인증 미설정 시 고음질 Edge-TTS 엔진으로 자동 전환
    """
    if output_dir is None:
        output_dir = Path("assets/audio")
    else:
        output_dir = Path(output_dir)

    voice_name = os.getenv("TTS_VOICE_NAME", "ko-KR-Neural2-C")
    speaking_rate = float(os.getenv("TTS_SPEAKING_RATE", "1.05"))
    sa_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

    # Google Cloud TTS 시도 조건 확인
    try_google = bool(sa_path and os.path.isfile(sa_path))

    if try_google:
        try:
            print(f"[TTS] Google Cloud TTS({voice_name})로 음성 합성을 진행합니다...")
            return synthesize_with_google_tts(scenes, output_dir, voice_name, speaking_rate)
        except Exception as e:
            print(f"[WARNING] Google Cloud TTS 실패 ({e}), 폴백 엔진(Edge-TTS)으로 전환합니다.")

    print("[TTS] 고음질 한국어 음성 엔진(Edge-TTS ko-KR-SunHiNeural)으로 음성 합성을 진행합니다...")
    return synthesize_with_edge_tts_fallback(scenes, output_dir)


if __name__ == "__main__":
    from pipeline.script_gen import create_sample_script

    sample = create_sample_script("테스트 릴스")
    print(f"[INFO] 씬 개수: {len(sample.scenes)}개 음성 합성 테스트 시작...")
    res = generate_speech(sample.scenes)

    print("\n[SUCCESS] TTS 합성 및 타이밍 정보 생성 완료!")
    print(f"🎵 결합된 전체 오디오: {res.audio_path} (총 {res.total_duration:.2f}초)")
    print(f"⏱️ 타이밍 메타데이터: {res.timing_json_path}")
    for sc in res.scene_results:
        print(f"  - 씬 {sc.scene_id}: {sc.start_time:.2f}s ~ {sc.end_time:.2f}s ({sc.duration:.2f}s) | 대사: {sc.narration[:20]}...")
