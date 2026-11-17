---
name: google-flow-video
description: 구글 제미나이 Flow (labs.google/fx/ko/tools/flow) 브라우저 자동화(Playwright/Computer Use) 및 무료 HD 스톡 영상(Pexels/Pixabay)을 결합해 비용 0원으로 릴스 영상 소스를 자동 추출·합성할 때 사용하는 스킬.
---

# Google Gemini Flow & Free Video Source Automation Skill

이 스킬은 정지 사진 위주의 릴스를 **실제 움직이는 고화질 영상(Veo / HD B-roll)**이 포함된 하이브리드 릴스로 업그레이드하면서 API 비용을 **0원~최소화**하는 방법을 정의합니다.

## 1. 왜 Google Gemini Flow 브라우저 자동화인가?

- Google Cloud / Vertex AI의 공식 Veo API(`veo-2.0-generate-001` / `veo-3.0`)를 API로 직접 호출하면 초당 약 `$0.35~$0.50`(릴스 1편당 1~2만 원)의 높은 과금이 발생합니다.
- 반면 Google Labs의 웹 서비스인 **Google Flow (`https://labs.google/fx/ko/tools/flow`)**에 로그인된 크롬 브라우저 세션(Playwright / Computer Use)으로 접속해 프롬프트를 입력하면 **구글 계정/AI Pro 웹 크레딧으로 추가 API 과금 없이** 초고화질 Veo 영상과 Imagen 이미지를 생성·다운로드할 수 있습니다.

## 2. 사용법 (`pipeline/flow_automation.py`)

### Step 1: 최초 1회 구글 로그인 세션 저장 (로컬 PC)
```bash
python -m pipeline.flow_automation --login
```
- 실행하면 전용 크롬 창(`assets/chrome_flow_profile`)이 열리고 `https://labs.google/fx/ko/tools/flow`로 이동합니다.
- 구글 계정으로 로그인한 뒤 창을 닫으면 세션 쿠키가 영구 보존됩니다.

### Step 2: 파이프라인에서 자동 실행 활성화 (`.env`)
```env
# 구글 제미나이 Flow 브라우저 자동화 활성화 (로컬 PC 실행 시)
USE_GOOGLE_FLOW=true
# 초반 몇 개 씬에 영상을 넣을지 설정 (기본 2: 씬 1~2 핵심 후킹 구간)
VIDEO_HOOK_SCENES=2

# 서버(Railway 등) 무인 가동 또는 Flow 폴백용 무료 고화질 영상 API (100% 무료)
PEXELS_API_KEY=your_free_pexels_api_key
PIXABAY_API_KEY=your_free_pixabay_api_key
```

### Step 3: 단독 클립 생성 테스트
```bash
python -m pipeline.flow_automation --scene-id 1 --prompt "Candid smartphone video of a Korean woman in her late 20s at a cozy cafe looking up from her phone, natural daylight"
```
- 생성된 영상은 `assets/videos/scene_01_raw.mp4`에 저장되며, `pipeline/composer.py`가 자동으로 감지해 1080x1920 릴스 프레임의 중앙 16:9 영역(`y=656`)에 오버레이합니다.

