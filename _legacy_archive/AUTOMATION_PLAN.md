# 텔레그램 → 인스타 릴스 자동화 : 현황 분석 & 완성 계획

> 작성일: 2026-09-25
> 목표: 매일 17:30 KST에 Gemini가 사주/MBTI 릴스 기획안 2개를 텔레그램으로 전송 →
> 사용자가 버튼으로 하나를 선택 → 대본/TTS/이미지/영상이 자동 생성되어 Google Drive에 업로드되고
> 인스타그램 릴스로 자동 게시됨. 전체가 Railway에서 24시간 무인 운영.

---

## 1. 현재 구현 현황 (As-Is)

### 파이프라인 모듈 (동작함)
| 모듈 | 상태 | 비고 |
|---|---|---|
| `pipeline/script_gen.py` | ✅ 동작 | Gemini 구조화 출력으로 대본(JSON) 생성, mock 폴백 있음 |
| `pipeline/mbti_saju_content.py` | ✅ 동작 | MBTI/오행 시리즈 전용 대본 생성 |
| `pipeline/tts_engine.py` | ✅ 존재 (미검토 상세) | 한국어 TTS + 타이밍 추출 |
| `pipeline/visual_gen.py` | ✅ 동작 | Pollinations FLUX(무료) → Vertex Imagen 3 → 그라데이션 플레이스홀더 순서로 폴백 |
| `pipeline/composer.py` | ✅ 동작 | FFmpeg Ken Burns + 자막 번인 → `final_reel.mp4` |
| `pipeline/gdrive_uploader.py` | ✅ 동작 | 서비스 계정으로 Drive 업로드, 공유 폴더 필요 |
| `pipeline/insta_publisher.py` | ⚠️ **어디서도 호출되지 않음** | Graph API 릴스 게시 함수만 존재, 파이프라인에 미연결 |
| `main.py` | ✅ 동작 | 위 모듈을 순서대로 실행하는 CLI (1~5단계) |

### 텔레그램 봇 (핵심 문제 지점)
| 파일 | 상태 |
|---|---|
| `send_proposals.py` (루트) | 거의 동일한 로직의 **중복 구현 #1** |
| `pipeline/telegram_bot_worker.py` | 거의 동일한 로직의 **중복 구현 #2** (18:00 자동 발송 스케줄 포함) |
| `bot.py` | **0바이트 빈 파일** |
| `pipeline/topic_suggester.py` | **0바이트 빈 파일** |
| `pipeline/uploader.py` | **0바이트 빈 파일** |
| `bot_output.txt`, `test_pollinations.jpg` | 테스트 산출물, 저장소에 들어가 있으면 안 됨 |

두 봇 파일이 동시에 실행되면 같은 `TELEGRAM_BOT_TOKEN`으로 `getUpdates` 롱폴링을 이중으로 호출하게 되어 Telegram API가 `409 Conflict`를 반환합니다. **반드시 하나만 남겨야 함.**

---

## 2. 발견된 핵심 문제점

### 🔴 Critical — 자동화 목표를 달성하지 못하는 구조적 결함

1. **선택 → 업로드 연결이 끊어져 있음.**
   `telegram_bot_worker.py`의 `run_pipeline_subprocess()`가 `main.py`를 호출할 때
   `--mock-images --no-gdrive` 플래그를 **항상 고정으로** 붙입니다.
   → 사용자가 텔레그램에서 기획안을 선택해도 실제로는:
   - AI 이미지 대신 그라데이션 플레이스홀더만 생성됨
   - Google Drive 업로드가 **아예 일어나지 않음**
   사용자가 원하는 "선택 즉시 구글드라이브 업로드"가 지금 코드에서는 발생하지 않습니다.

2. **인스타그램 자동 게시가 파이프라인에 연결되지 않음.**
   `insta_publisher.py`의 `publish_reel_to_instagram()`은 어디에서도 import/호출되지 않습니다.
   또한 이 함수는 `video_url`(공개적으로 접근 가능한 URL)을 요구하는데,
   `gdrive_uploader.py`가 반환하는 `webViewLink`는 Instagram Graph API가 다운로드할 수 있는
   직접 스트리밍 URL이 아닙니다(뷰어 페이지 링크). 실제 게시가 되려면
   - Drive 파일을 "링크가 있는 모든 사용자"로 공유하고
   - `uc?export=download&id=...` 형태의 직접 다운로드 URL을 만들거나
   - Google Cloud Storage(GCS) 공개 버킷처럼 진짜 스트리밍 가능한 URL을 써야 합니다.

3. **Windows 전용 경로가 Railway(Linux)에서 깨짐.**
   두 봇 파일 모두 하위 프로세스로 `main.py`를 실행할 때
   `Path(...) / ".venv" / "Scripts" / "python.exe"` 를 하드코딩합니다.
   Railway 컨테이너는 Linux이므로 이 경로가 존재하지 않아 **즉시 실패**합니다.
   → `sys.executable`을 쓰거나, 아예 subprocess 대신 파이프라인 함수를 같은 프로세스 내에서
   직접 import하여 호출하는 구조로 바꿔야 합니다.

4. **서비스 계정 키 파일이 Railway에 존재하지 않음.**
   `GOOGLE_APPLICATION_CREDENTIALS`가 로컬 JSON 파일 경로를 가리키는데,
   Railway에는 이 파일이 배포되지 않습니다(`.gitignore`에도 제외되어 있어 정상).
   → Railway 환경변수에 JSON **내용 전체**를 넣고, 앱 시작 시 임시 파일로 써서
   `GOOGLE_APPLICATION_CREDENTIALS`가 그 경로를 가리키게 하는 부트스트랩 코드가 필요합니다.

5. **FFmpeg가 Railway 컨테이너에 기본 설치되어 있지 않음.**
   `nixpacks.toml` 또는 `Aptfile` 등으로 빌드 시 ffmpeg를 설치하는 설정이 없습니다.
   이게 없으면 `composer.py`의 영상 합성 단계에서 전부 실패합니다.

### 🟠 High — 24시간 무인 운영 시 반드시 터지는 문제

6. **인메모리 상태 저장.** `PENDING = {}` 딕셔너리가 프로세스 메모리에만 존재합니다.
   Railway는 재배포/크래시/OOM 시 컨테이너를 재시작하므로, 그 시점에 대기 중이던
   기획안 선택 정보가 전부 사라집니다. 최소한 SQLite 파일이나 Google Sheets/Drive에
   상태를 영속화해야 합니다.

7. **타임존 버그.** `datetime.datetime.now()`가 시스템 로컬 타임존을 사용합니다.
   Railway 컨테이너는 기본적으로 **UTC**로 동작하므로, "매일 18:00(또는 17:30)"
   체크 로직이 실제로는 KST가 아닌 UTC 18:00(=KST 새벽 3시)에 발동합니다.
   `zoneinfo.ZoneInfo("Asia/Seoul")`을 명시적으로 사용해야 합니다.

8. **분(minute) 단위 폴링으로 스케줄을 흉내내는 방식의 취약성.**
   `now.hour == 18 and now.minute < 2` 같은 조건은 그 2분 사이에 프로세스가
   재시작되거나 blocking 작업(영상 렌더링 등)으로 루프가 멈춰 있으면 그날 발송을
   통째로 건너뜁니다. Railway의 Cron Job 기능이나 APScheduler + 영속 상태로 대체가 필요합니다.

9. **`subprocess.run(..., timeout=300)`으로 영상 생성을 실행.**
   TTS+이미지 생성+FFmpeg 렌더링이 5분을 넘기면(특히 이미지 생성 API가 느릴 때) 무조건
   타임아웃되어 실패 처리됩니다. 반면 봇의 메인 루프는 `time.sleep(1)`으로 폴링하면서
   동시에 무거운 렌더링 작업을 백그라운드 스레드로 돌리는데, 동시 여러 요청이 오면
   순서 보장이나 동시 실행 제한이 없습니다.

### 🟡 Medium

10. **Gemini 모델명 미검증.** `.env`에 `GEMINI_MODEL=gemini-3.1-flash-lite`,
    코드 내 폴백값으로 `gemini-3.8-flash`가 하드코딩되어 있습니다. 실제 Gemini API에
    존재하는 모델 ID인지 최신 문서 기준으로 재확인이 필요합니다(오탈자/추측성 이름일 가능성).
11. **Telegram `parse_mode: Markdown` 이스케이프 누락.** Gemini가 생성한 `title`/`hook`/`summary`에
    `_`, `*`, `[`, `` ` `` 같은 문자가 섞이면 `sendMessage`가 400 에러로 실패할 수 있습니다.
12. **중복 코드베이스.** `send_proposals.py`와 `pipeline/telegram_bot_worker.py`가
    사실상 동일한 로직을 두 번 구현 — 유지보수 시 한쪽만 고치면 다른 쪽은 그대로 버그로 남음.
13. **에러 처리 불일치.** `send_proposals.py`의 `gemini_plan()`은 실패 시 빈 dict를 반환하지만
    `telegram_bot_worker.py`는 폴백 콘텐츠를 반환함 — 동작이 서로 다름.

### 🟢 Low
14. `bot_output.txt`, `test_pollinations.jpg`가 저장소 루트에 커밋 대상으로 남아있음(정리 필요).
15. `bot.py`, `pipeline/topic_suggester.py`, `pipeline/uploader.py` 빈 파일 — 스캐폴딩 잔재, 삭제 또는 용도 확정 필요.
16. MBTI/오행 랜덤 선택에 최근 N일 중복 방지 로직이 없음 (선택 사항).

---

## 3. 목표 아키텍처 (To-Be)

```
[Railway Cron/Scheduler, Asia/Seoul 17:30]
        │
        ▼
┌─────────────────────────┐
│ telegram_bot.py (단일 프로세스, 상시 실행) │
│  - getUpdates 롱폴링 루프                 │
│  - 17:30 KST 기획안 2건 자동 발송           │
│  - PENDING 상태는 SQLite/파일에 영속화       │
└───────────┬─────────────┘
            │ 사용자가 인라인 버튼 클릭 (callback_query)
            ▼
┌─────────────────────────────────────────────┐
│ run_full_pipeline(plan)  (같은 프로세스 내 함수 호출, │
│  subprocess 대신 직접 import)                    │
│                                                 │
│  1. script_gen / mbti_saju_content → 대본       │
│  2. tts_engine → 음성 + 타이밍                    │
│  3. visual_gen → 씬 이미지                        │
│  4. composer → final_reel.mp4                   │
│  5. gdrive_uploader → Drive 업로드 + 공개 공유 링크  │
│  6. insta_publisher → Drive 직접다운로드 URL로      │
│     Instagram Graph API 릴스 게시                 │
│  7. 텔레그램으로 "완료 + Drive 링크 + IG 링크" 회신   │
└─────────────────────────────────────────────┘
```

### 핵심 설계 변경 사항
- **subprocess → in-process 함수 호출**: Windows 전용 경로 문제 해결 + 에러 핸들링/타임아웃 제어 용이.
- **상태 영속화**: `PENDING` 선택 정보 + "오늘 발송했는가" 플래그를 SQLite(`state.db`) 또는 최소한 로컬 JSON 파일 + 주기적 백업으로 저장.
- **타임존 명시**: 모든 `datetime.now()` → `datetime.now(ZoneInfo("Asia/Seoul"))`.
- **스케줄러**: `time.sleep(1)` 폴링 대신 `APScheduler`의 `BackgroundScheduler` + cron 트리거(`hour=17, minute=30, timezone="Asia/Seoul"`) 사용을 권장. 텔레그램 polling과 스케줄러를 한 프로세스에서 함께 실행(asyncio 기반 `python-telegram-bot` 라이브러리 사용 추천).
- **Drive → Instagram 연결**: Drive 파일을 `anyone with link, reader` 권한으로 설정 후
  `https://drive.google.com/uc?export=download&id=<FILE_ID>` 형태의 URL을 Instagram 컨테이너 생성에 사용.
  (용량이 크거나 안정성이 더 필요하면 GCS 공개 버킷 서명 URL로 대체 고려.)
- **자격 증명 부트스트랩**: 앱 시작 시 `GOOGLE_SERVICE_ACCOUNT_JSON`(전체 JSON 문자열) 환경변수를 읽어
  `/tmp/service_account.json`으로 기록 후 `GOOGLE_APPLICATION_CREDENTIALS`를 그 경로로 설정.
- **Railway 빌드 설정**: `nixpacks.toml`에 `ffmpeg` apt 패키지 추가, `Procfile` 또는 `railway.json`의
  `startCommand`를 단일 봇 프로세스(`python telegram_bot.py`)로 고정.

---

## 4. 정리/삭제 대상
- `send_proposals.py` 또는 `pipeline/telegram_bot_worker.py` 중 **하나로 통합**, 나머지 삭제.
- `bot.py`, `pipeline/topic_suggester.py`, `pipeline/uploader.py` — 빈 파일, 용도 없으면 삭제.
- `bot_output.txt`, `test_pollinations.jpg` — 저장소에서 제거 (필요 시 `.gitignore` 추가).

## 5. Railway 배포 전 체크리스트
- [ ] 단일 봇 엔트리포인트로 통합 (중복 제거)
- [ ] subprocess 호출 제거 → in-process 함수 호출로 전환
- [ ] `GOOGLE_APPLICATION_CREDENTIALS` Railway용 부트스트랩 코드 추가
- [ ] `nixpacks.toml`/`Aptfile`로 ffmpeg 설치 보장
- [ ] PENDING 상태 영속화 (SQLite 등)
- [ ] 타임존 명시 (`Asia/Seoul`)
- [ ] 17:30 스케줄 로직을 APScheduler cron으로 교체
- [ ] Google Drive 업로드 → 공개 다운로드 URL 생성 로직 추가
- [ ] `insta_publisher.py`를 파이프라인 끝에 연결
- [ ] `--mock-images --no-gdrive` 하드코딩 제거, 실제 운영 시 실제 이미지+업로드 사용
- [ ] Gemini/Imagen 모델명 실제 존재 여부 재검증
- [ ] Telegram 메시지 마크다운 이스케이프 처리
- [ ] 테스트 산출물/빈 파일 정리
