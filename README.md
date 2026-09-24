# 🎬 인스타그램 릴스(Instagram Reels) 원클릭 자동 제작 파이프라인

단일 Python 스크립트 실행으로 **"주제 입력 ➔ Gemini 대본 기획 ➔ TTS 음성 및 자막 싱크 생성 ➔ Imagen 3 9:16 비주얼 에셋 생성 ➔ FFmpeg Ken Burns & 자막 하드코딩 영상 합성"**까지 원스톱으로 처리하는 자동화 시스템입니다.

---

## 📁 프로젝트 구조

```text
insta_auto/
├── .env                  # API 키 및 환경 변수 설정
├── .env.example          # 환경 변수 설정 템플릿
├── requirements.txt      # 의존성 패키지 목록
├── main.py               # 파이프라인 전체를 구동하는 메인 CLI 실행 파일
│
├── pipeline/             # 핵심 처리 모듈
│   ├── __init__.py
│   ├── script_gen.py     # Gemini Structured Outputs 기반 릴스 대본 생성
│   ├── tts_engine.py     # Google Cloud TTS 및 타이밍/자막 싱크 추출
│   ├── visual_gen.py     # Vertex AI Imagen 3 9:16 이미지 생성
│   └── composer.py       # FFmpeg 기반 Ken Burns 효과 + ASS 자막 번인 영상 합성
│
├── utils/                # 시스템 유틸리티
│   ├── __init__.py
│   └── ffmpeg_check.py   # 시스템 FFmpeg 탐색 및 정상 동작 검증
│
└── assets/               # 생성 결과물 디렉토리
    ├── images/           # 씬별 생성된 9:16 세로 이미지 (.jpg)
    ├── audio/            # 씬별 및 전체 TTS 오디오 (.mp3, timing_info.json)
    ├── subtitles/        # 생성된 자막 파일 (.ass, .srt)
    └── output/           # 최종 완성된 인스타 릴스 (.mp4) 및 캡션 (.txt)
```

---

## 🛠️ 요구 사양 및 설치

1. **Python**: 3.10 이상
2. **FFmpeg**: 설치 완료 (Scoop, WinGet, Choco 등)
3. **가상환경 활성화 및 패키지 설치**:
   ```bash
   # 가상환경 활성화 (Windows PowerShell)
   .\.venv\Scripts\Activate.ps1

   # 의존성 설치
   pip install -r requirements.txt
   ```

---

## ⚙️ 환경 변수 설정 (`.env`)

`.env` 파일에 발급받은 키와 설정을 입력합니다:
```env
# Google Gemini API Key (대본 기획용)
GEMINI_API_KEY=AIzaSy...

# Google Cloud & Vertex AI 설정 (Imagen 3 및 Cloud TTS용)
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_APPLICATION_CREDENTIALS=path/to/service_account.json
GCP_LOCATION=us-central1

# 모델 및 음성 설정
GEMINI_MODEL=gemini-2.5-flash
IMAGEN_MODEL=imagen-3.0-generate-002
TTS_VOICE_NAME=ko-KR-Neural2-C
TTS_SPEAKING_RATE=1.05
```

> **스마트 폴백(Fallback) 기능 제공:**
> - GCP 인증이 아직 준비되지 않은 환경에서도 무중단 테스트가 가능하도록 **한국어 고음질 Neural TTS(Edge-TTS)** 및 **Aesthetic 9:16 그래픽 생성기**가 내장되어 있어 즉시 테스트가 가능합니다.

---

## 🚀 실행 방법

### 1. 기본 원클릭 실행 (전 과정 자동 수행)
```bash
python main.py --topic "퇴근 후 30분, 나만의 릴스 자동화 만들기"
```

### 2. 오프라인 / 빠른 테스트 모드 (API 요금 절약)
```bash
python main.py --topic "AI 생산성 꿀팁" --mock-script --mock-images
```

### 3. 개별 모듈 단위 테스트
- **대본 생성 모듈 테스트**:
  ```bash
  python pipeline/script_gen.py --topic "자기계발 습관"
  ```
- **음성 합성 모듈 테스트**:
  ```bash
  python pipeline/tts_engine.py
  ```
- **비주얼 생성 모듈 테스트**:
  ```bash
  python pipeline/visual_gen.py
  ```
- **영상 합성 엔진 단독 테스트**:
  ```bash
  python pipeline/composer.py
  ```

---

## 🎬 최종 출력 사양
- **해상도**: 1080 x 1920 (9:16 세로 릴스 규격)
- **프레임레이트**: 30 FPS
- **영상 효과**: 씬별 교차 부드러운 Ken Burns(줌인 / 줌아웃) 모션 적용
- **자막**: 인스타그램 UI(하단 버튼, 프로필 영역)를 가리지 않는 최적화된 마진(320px)과 볼드 테두리 스타일 적용
- **출력 파일**: `assets/output/final_reel.mp4` 및 인스타그램 업로드용 해시태그 본문 `assets/output/caption.txt`

