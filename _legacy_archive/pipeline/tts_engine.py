"""
TTS Synthesis Module for Instagram Reels Pipeline.
Primary: Google Cloud Text-to-Speech (Neural2 / Journey) with SSML timepoints.
Fallback: Edge TTS (Korean Neural) with word-level boundary synchronization.
Includes FFmpeg -30dB silence auto-cut (0.1s precision) & optional ElevenLabs plugin.
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


# 영상마다 랜덤 선택되는 목소리 프리셋(남/여 + 톤 변화). rate/pitch는 쇼츠 특유의 쫀쫀한 텐션 연출용.
EDGE_VOICE_PRESETS = [
    {"voice": "ko-KR-SunHiNeural", "rate": "+16%", "pitch": "+0Hz"},     # 여성, 경쾌·쇼츠 호흡
    {"voice": "ko-KR-SunHiNeural", "rate": "+12%", "pitch": "+5Hz"},     # 여성, 하이톤 공감
    {"voice": "ko-KR-InJoonNeural", "rate": "+16%", "pitch": "+0Hz"},    # 남성, 텐션업 팩트폭격
    {"voice": "ko-KR-InJoonNeural", "rate": "+10%", "pitch": "-3Hz"},    # 남성, 몰입감 있는 저음
]
GOOGLE_VOICE_PRESETS = [
    {"voice": "ko-KR-Neural2-A", "rate": 1.16, "pitch": 1.0},   # 여성, 경쾌
    {"voice": "ko-KR-Neural2-B", "rate": 1.12, "pitch": 2.5},   # 여성, 하이톤
    {"voice": "ko-KR-Neural2-C", "rate": 1.16, "pitch": 0.0},   # 남성, 텐션업
    {"voice": "ko-KR-Neural2-C", "rate": 1.10, "pitch": -2.5},  # 남성, 몰입감 저음
]


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


def _synthesize_with_marks(words: List[str], voice_name: str, speaking_rate: float, out_path: Path, pitch: float = 0.0) -> Optional[List[float]]:
    """
    단어별 <mark>가 들어간 SSML로 합성해 out_path에 저장하고, 각 단어 시작 시각(초) 리스트를 반환합니다.
    실패하거나 마크 수가 맞지 않으면 None (호출부가 균등 분할로 대체).
    """
    if not words:
        return None
    try:
        from xml.sax.saxutils import escape
        from google.cloud import texttospeech_v1beta1 as tts

        ssml = "<speak>" + " ".join(f'<mark name="w{i}"/>{escape(w)}' for i, w in enumerate(words)) + "</speak>"
        client = tts.TextToSpeechClient()
        response = client.synthesize_speech(
            request=tts.SynthesizeSpeechRequest(
                input=tts.SynthesisInput(ssml=ssml),
                voice=tts.VoiceSelectionParams(language_code="ko-KR", name=voice_name),
                audio_config=tts.AudioConfig(audio_encoding=tts.AudioEncoding.MP3, speaking_rate=speaking_rate, pitch=pitch),
                enable_time_pointing=[tts.SynthesizeSpeechRequest.TimepointType.SSML_MARK],
            )
        )
        points = {tp.mark_name: tp.time_seconds for tp in response.timepoints}
        if len(points) != len(words):
            return None
        starts = [float(points[f"w{i}"]) for i in range(len(words))]
        with open(out_path, "wb") as f:
            f.write(response.audio_content)
        return starts
    except Exception as e:
        print(f"  [WARN] Google TTS 단어 마크 합성 실패 ({e}). 균등 분할 타이밍으로 대체합니다.")
        return None


def synthesize_with_google_tts(
    scenes: list,
    output_dir: Path,
    voice_name: str = "ko-KR-Neural2-C",
    speaking_rate: float = 1.05,
    pitch: float = 0.0,
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
        pitch=pitch,
    )

    scene_results: List[SceneAudioResult] = []
    current_time_offset = 0.0

    output_dir.mkdir(parents=True, exist_ok=True)

    for sc in scenes:
        scene_id = getattr(sc, "scene_id", sc.get("scene_id") if isinstance(sc, dict) else 1)
        narration = getattr(sc, "narration", sc.get("narration") if isinstance(sc, dict) else "")

        scene_filename = f"scene_{scene_id:02d}.mp3"
        scene_path = output_dir / scene_filename

        # 단어마다 SSML <mark>를 심고 v1beta1 time pointing으로 실측 시각을 받는다
        words = narration.split()
        marks = _synthesize_with_marks(words, voice_name, speaking_rate, scene_path, pitch)
        if marks is None:
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

        word_timings = []
        if words:
            if marks is not None:
                # mark i = i번째 단어 시작 시각, 단어 끝 = 다음 단어 시작(마지막은 씬 끝)
                for idx, w in enumerate(words):
                    w_start = start_time + marks[idx]
                    w_end = start_time + (marks[idx + 1] if idx + 1 < len(words) else duration)
                    word_timings.append(WordTiming(word=w, start_time=round(w_start, 3), end_time=round(w_end, 3)))
            else:
                # 마크 합성 실패 시 균등 분할 추정으로 대체
                word_dur = duration / len(words)
                for idx, w in enumerate(words):
                    w_start = start_time + (idx * word_dur)
                    w_end = w_start + word_dur
                    word_timings.append(WordTiming(word=w, start_time=round(w_start, 3), end_time=round(w_end, 3)))

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


async def _synthesize_edge_tts_scene(narration: str, output_path: Path, voice: str = "ko-KR-SunHiNeural", rate: str = "+5%", pitch: str = "+0Hz") -> List[WordTiming]:
    """
    Edge-TTS를 사용하여 씬 오디오 및 세부 단어 타이밍을 생성합니다.
    """
    import edge_tts

    # edge-tts 7.x 기본값은 SentenceBoundary(문장 단위)이므로 단어 단위 자막을 위해 WordBoundary를 명시
    communicate = edge_tts.Communicate(narration, voice=voice, rate=rate, pitch=pitch, boundary="WordBoundary")
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
    voice_name: str = "ko-KR-SunHiNeural",
    rate: str = "+5%",
    pitch: str = "+0Hz",
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
            raw_timings = loop.run_until_complete(_synthesize_edge_tts_scene(narration, scene_path, voice_name, rate, pitch))
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


def synthesize_with_gtts_fallback(
    scenes: list,
    output_dir: Path,
) -> FullAudioResult:
    """
    Edge-TTS 차단(403 등) 시 100% 무중단 동작을 보장하는 Google 무료 gTTS 폴백 엔진.
    """
    try:
        from gtts import gTTS
    except ImportError:
        import subprocess
        print("[INFO] gTTS 패키지가 없어 자동으로 설치합니다 (pip install gTTS)...")
        subprocess.run([sys.executable, "-m", "pip", "install", "gTTS"], check=True)
        from gtts import gTTS

    output_dir.mkdir(parents=True, exist_ok=True)
    scene_results: List[SceneAudioResult] = []
    current_time_offset = 0.0

    for sc in scenes:
        scene_id = getattr(sc, "scene_id", sc.get("scene_id") if isinstance(sc, dict) else 1)
        narration = getattr(sc, "narration", sc.get("narration") if isinstance(sc, dict) else "")

        scene_filename = f"scene_{scene_id:02d}.mp3"
        scene_path = output_dir / scene_filename

        tts = gTTS(text=narration, lang="ko")
        tts.save(str(scene_path))

        duration = get_audio_duration(str(scene_path))
        start_time = current_time_offset
        end_time = current_time_offset + duration

        # 자막 싱크용 단어 타이밍 균등 분할
        words = narration.split()
        word_count = max(len(words), 1)
        word_dur = duration / word_count
        adjusted_timings = []
        for idx, w in enumerate(words):
            w_start = round(start_time + (idx * word_dur), 3)
            w_end = round(start_time + ((idx + 1) * word_dur), 3)
            adjusted_timings.append(WordTiming(word=w, start_time=w_start, end_time=w_end))

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


# 마지막으로 쓴 TTS 설정 (A/B 변형 기록용). generate_speech가 갱신한다.
LAST_TTS_INFO: dict = {}


def trim_audio_silence_ffmpeg(
    audio_path: Path,
    threshold_db: int = -30,
    stop_duration: float = 0.10,
    leave_silence: float = 0.04,
) -> float:
    """
    보이스 파일의 무음 구간(기본 -30dB 이하)을 FFmpeg silenceremove 필터로 0.1초 단위 자동 컷편집합니다.
    - 문장 시작 앞의 숨소리/공백 제거 + 문장 중간/끝의 늘어지는 호흡을 칼같이 당겨 초반 3초 이탈을 방지합니다.
    - 편집 후 실제 재생 시간(초)을 반환합니다.
    """
    import subprocess
    from utils.ffmpeg_check import get_ffmpeg_path

    if not audio_path.is_file():
        return 0.0

    ffmpeg_bin = get_ffmpeg_path() or "ffmpeg"
    trimmed_tmp = audio_path.parent / f"{audio_path.stem}_trimmed{audio_path.suffix}"
    af_filter = (
        f"silenceremove=start_periods=1:start_duration=0.02:start_threshold={threshold_db}dB:"
        f"stop_periods=-1:stop_duration={stop_duration:.2f}:stop_threshold={threshold_db}dB:"
        f"stop_silence={leave_silence:.2f},"
        f"apad=pad_dur=0.04"
    )
    cmd = [
        ffmpeg_bin, "-y",
        "-i", str(audio_path),
        "-af", af_filter,
        "-c:a", "libmp3lame", "-b:a", "192k",
        str(trimmed_tmp),
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode == 0 and trimmed_tmp.is_file() and trimmed_tmp.stat().st_size > 500:
        new_dur = get_audio_duration(str(trimmed_tmp))
        # 너무 짧게 잘린 비정상 케이스 방어 (최소 0.4초 이상일 때만 교체)
        if new_dur >= 0.4:
            trimmed_tmp.replace(audio_path)
            return new_dur
    if trimmed_tmp.is_file():
        try:
            trimmed_tmp.unlink()
        except Exception:
            pass
    return get_audio_duration(str(audio_path))


def _apply_silence_trim_to_result(result: FullAudioResult, output_dir: Path) -> FullAudioResult:
    """
    생성된 전체 씬 오디오에 -30dB 무음 자동 칼컷을 일괄 적용하고,
    줄어든 길이에 맞춰 씬 타임라인 및 카라오케 단어 타이밍(word_timings)을 정밀 재정렬합니다.
    """
    if os.getenv("TRIM_SILENCE", "true").strip().lower() in ("0", "false", "no"):
        return result

    threshold_db = int(os.getenv("SILENCE_THRESHOLD_DB", "-30"))
    saved_total = 0.0
    current_offset = 0.0

    for sc in result.scene_results:
        old_dur = max(float(sc.duration), 0.001)
        old_start = float(sc.start_time)
        new_dur = trim_audio_silence_ffmpeg(Path(sc.audio_path), threshold_db=threshold_db)
        if new_dur <= 0:
            new_dur = old_dur

        saved_total += max(0.0, old_dur - new_dur)
        scale = new_dur / old_dur

        new_timings: List[WordTiming] = []
        for wt in sc.word_timings:
            rel_s = max(0.0, float(wt.start_time) - old_start) * scale
            rel_e = max(rel_s + 0.02, (float(wt.end_time) - old_start) * scale)
            new_timings.append(
                WordTiming(
                    word=wt.word,
                    start_time=round(current_offset + min(rel_s, new_dur), 3),
                    end_time=round(current_offset + min(rel_e, new_dur), 3),
                )
            )

        sc.start_time = round(current_offset, 3)
        sc.duration = round(new_dur, 3)
        sc.end_time = round(current_offset + new_dur, 3)
        sc.word_timings = new_timings
        current_offset += new_dur

    full_audio_path = output_dir / "full_narration.mp3"
    _concatenate_audio_files([r.audio_path for r in result.scene_results], full_audio_path)
    result.total_duration = round(get_audio_duration(str(full_audio_path)), 3)

    timing_json_path = Path(result.timing_json_path)
    with open(timing_json_path, "w", encoding="utf-8") as f:
        f.write(result.model_dump_json(indent=2))

    print(f"  ✂️ [AUDIO-CUT] -30dB 무음 구간 자동 칼컷 완료 (단축된 늘어짐: -{saved_total:.2f}초 -> 최종 {result.total_duration:.2f}초)")
    return result


def synthesize_with_elevenlabs(
    scenes: list,
    output_dir: Path,
    api_key: str,
    voice_id: str = "EXAVITQu4vr4xnSDxMaL",
) -> FullAudioResult:
    """
    ElevenLabs Multilingual v2 API를 사용해 초고몰입 AI 보이스를 생성합니다.
    (환경변수 ELEVENLABS_API_KEY 설정 시 활성화)
    """
    import requests

    output_dir.mkdir(parents=True, exist_ok=True)
    scene_results: List[SceneAudioResult] = []
    current_time_offset = 0.0
    model_id = os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")

    for sc in scenes:
        scene_id = getattr(sc, "scene_id", sc.get("scene_id") if isinstance(sc, dict) else 1)
        narration = getattr(sc, "narration", sc.get("narration") if isinstance(sc, dict) else "")
        scene_path = output_dir / f"scene_{scene_id:02d}.mp3"

        resp = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            headers={"xi-api-key": api_key, "Content-Type": "application/json"},
            json={
                "text": narration,
                "model_id": model_id,
                "voice_settings": {"stability": 0.45, "similarity_boost": 0.80, "style": 0.35, "use_speaker_boost": True},
            },
            timeout=30,
        )
        if resp.status_code != 200 or len(resp.content) < 1000:
            raise RuntimeError(f"ElevenLabs HTTP {resp.status_code}: {resp.text[:200]}")

        scene_path.write_bytes(resp.content)
        duration = get_audio_duration(str(scene_path))
        start_time = current_time_offset
        end_time = current_time_offset + duration

        words = narration.split()
        word_dur = duration / max(len(words), 1)
        timings = [
            WordTiming(word=w, start_time=round(start_time + i * word_dur, 3), end_time=round(start_time + (i + 1) * word_dur, 3))
            for i, w in enumerate(words)
        ]
        scene_results.append(
            SceneAudioResult(
                scene_id=scene_id,
                audio_path=str(scene_path.resolve()),
                duration=round(duration, 3),
                start_time=round(start_time, 3),
                end_time=round(end_time, 3),
                narration=narration,
                word_timings=timings,
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
        timing_json_path=str(timing_json_path.resolve()),
    )
    with open(timing_json_path, "w", encoding="utf-8") as f:
        f.write(result.model_dump_json(indent=2))
    return result


def generate_speech(scenes: list, output_dir: Optional[str | Path] = None) -> FullAudioResult:
    """
    대본의 씬(scenes) 리스트를 입력받아 음성 및 타이밍 정보를 생성하고,
    -30dB 무음 구간을 0.1초 단위로 자동 칼컷 편집하여 빠른 숏폼 호흡으로 재배열합니다.
    0. (선택) ElevenLabs API 키가 설정된 경우 초고몰입 보이스 우선 시도
    1. Google Cloud Text-to-Speech 우선 시도
    2. GCP 인증 미설정 시 고음질 Edge-TTS 엔진 시도
    3. Edge-TTS 403 차단/실패 시 Google 무료 gTTS 엔진으로 3차 자동 폴백 (100% 무중단 완주)
    """
    if output_dir is None:
        output_dir = Path("assets/audio")
    else:
        output_dir = Path(output_dir)

    import random

    # 0. ElevenLabs 플러그인 (키가 있을 때만 동작)
    eleven_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    if eleven_key and not eleven_key.startswith("your_"):
        eleven_voice = os.getenv("ELEVENLABS_VOICE_ID", "EXAVITQu4vr4xnSDxMaL").strip()
        try:
            print(f"[TTS] ElevenLabs 고몰입 보이스({eleven_voice})로 음성 합성을 진행합니다...")
            LAST_TTS_INFO.clear()
            LAST_TTS_INFO.update(engine="elevenlabs", voice=eleven_voice, rate="1.15")
            res = synthesize_with_elevenlabs(scenes, output_dir, eleven_key, eleven_voice)
            return _apply_silence_trim_to_result(res, output_dir)
        except Exception as e:
            print(f"[WARNING] ElevenLabs TTS 실패 ({e}), 기본 무료/클라우드 TTS로 전환합니다.")

    # TTS_VOICE_NAME을 명시하면 그 목소리로 고정, 없으면 영상마다 남/여 + 톤 프리셋을 랜덤 선택
    forced_voice = os.getenv("TTS_VOICE_NAME", "").strip()
    sa_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

    # Google Cloud TTS 시도 조건 확인
    try_google = bool(sa_path and os.path.isfile(sa_path))

    if try_google:
        gp = random.choice(GOOGLE_VOICE_PRESETS)
        voice_name = forced_voice or gp["voice"]
        speaking_rate = float(os.getenv("TTS_SPEAKING_RATE", gp["rate"]))
        LAST_TTS_INFO.clear()
        LAST_TTS_INFO.update(engine="google", voice=voice_name, rate=str(speaking_rate))
        try:
            print(f"[TTS] Google Cloud TTS({voice_name}, rate={speaking_rate}, pitch={gp['pitch']})로 음성 합성을 진행합니다...")
            res = synthesize_with_google_tts(scenes, output_dir, voice_name, speaking_rate, gp["pitch"])
            return _apply_silence_trim_to_result(res, output_dir)
        except Exception as e:
            print(f"[WARNING] Google Cloud TTS 실패 ({e}), 폴백 엔진(Edge-TTS)으로 전환합니다.")

    ep = random.choice(EDGE_VOICE_PRESETS)
    edge_voice = forced_voice if forced_voice.startswith("ko-KR-") and forced_voice.endswith("Neural") and "Neural2" not in forced_voice else ep["voice"]
    LAST_TTS_INFO.clear()
    LAST_TTS_INFO.update(engine="edge", voice=edge_voice, rate=ep["rate"])
    print(f"[TTS] Edge-TTS({edge_voice}, rate={ep['rate']}, pitch={ep['pitch']})로 음성 합성을 진행합니다...")
    try:
        res = synthesize_with_edge_tts_fallback(scenes, output_dir, edge_voice, ep["rate"], ep["pitch"])
        return _apply_silence_trim_to_result(res, output_dir)
    except Exception as e:
        print(f"\n[WARNING] Edge-TTS 요청 거부/실패 감지 ({e})")
        print("[TTS] ➔ Google 무료 gTTS 엔진으로 안전하게 자동 전환하여 음성을 합성합니다...")
        LAST_TTS_INFO.clear()
        LAST_TTS_INFO.update(engine="gtts", voice="gtts", rate="default")
        res = synthesize_with_gtts_fallback(scenes, output_dir)
        return _apply_silence_trim_to_result(res, output_dir)


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
