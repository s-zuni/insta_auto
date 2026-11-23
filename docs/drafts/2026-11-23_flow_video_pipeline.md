# Flow 기반 숏츠 영상 자동화 파이프라인 — 초안 v2

- 담당: 이세림 (B) / 작성일: 2026-11-23 / 상태: **설계 초안 (코드 미구현)**
- v2 확정 사항 (대표 결정)
  1. 연동은 **Playwright 로 Flow 웹 UI 자동화** (공식 API 없음)
  2. **TTS 사용 안 함** — 음성은 Flow 영상 자체 오디오
  3. **자막 넣지 않음**
  4. 로직: **기획 → (병렬) Flow 영상 / 쓰레드 글 / 네이버 블로그 글 → 채널별 업로드**

## 1. 전체 흐름

```
주제 입력 (GenerateRequest)
   │
   ▼
[1] 기획 (Plan)  ─ 1회 LLM 호출, 3종 콘텐츠의 공통 뼈대
   │   훅 · 핵심 포인트 · CTA · 영상 장면(샷 설명 + 장면별 음성 대사)
   │
   ├──────────────┬───────────────────┐   asyncio.gather  (서로 독립)
   ▼              ▼                   ▼
[2a] Flow 영상  [2b] 쓰레드 글      [2c] 네이버 블로그 글
 (Playwright)    (generators)        (generators)
 수 분 소요      수 초               수 초
   │              │                   │
   ▼              ▼                   ▼
[3a] 인스타 릴스 [3b] 쓰레드 업로드  [3c] 네이버 블로그 업로드
     + 유튜브 쇼츠                        (사람이 확인 후 · dry_run 기본)
```

- 기획은 기존 `matrix_prompt.Brief` 가 이미 같은 역할(훅/핵심/CTA)이다. **Brief 에 "영상 장면" 만 확장**하면 된다.
- 2a/2b/2c 는 **한쪽이 실패해도 다른 쪽을 막지 않는다** (원칙 3·4). 영상은 가장 오래 걸리므로 **텍스트 2종은 먼저 화면에 보여준다.**
- 3 단계 업로드는 기존 `/api/publish` 그대로 채널별 독립 실행. 영상 완료 전에도 쓰레드·블로그는 먼저 발행 가능.

## 2. Flow 영상 생성 (Playwright)

### 2-1. 30초 분량
- Flow 클립은 한 번에 약 8초 안팎(실제 값은 구현 시 UI 에서 확인). **장면 4개 × ~8초 ≈ 30초**를 기본으로, 3~5개로 제한.
- 장면 클립을 FFmpeg 로 **단순 concat 만** 한다 (TTS·자막 합성 없음). 필요하면 세로 9:16 크롭/스케일(1080x1920)과 오디오 길이 맞춤 정도만.
- Flow 에 이어 만들기(Extend)류 기능이 있으면 장면 간 연속성이 좋아진다 → **UI 에 있는지 확인 후 1순위로 시도**, 없으면 concat.

### 2-2. 음성 (TTS 없음)
- 음성은 Flow 가 영상과 함께 만든다. 그래서 **기획 단계의 "장면별 음성 대사"를 영상 프롬프트에 직접 넣는다.**
- ⚠ **한국어 음성 품질·발음·정확도는 미검증.** 오늘 스모크에서 반드시 확인:
  - 한국어 대사가 그대로 나오는가 / 영어로 나오는가
  - 대사가 8초 안에 들어가는가 (한 장면 대사는 **20~25자 안팎**으로 짧게 제한 권장)
  - 장면마다 목소리가 달라지지 않는가 (달라지면 concat 시 어색함 → 프롬프트에 목소리 설명 고정, 또는 장면 수 축소)
- 최종 결과가 별로면 후속 대안: 대사 없는 영상 + BGM, 또는 영어 음성 + 한국어 캡션(지금은 자막 금지라 보류).
- 영상 속에 글자(간판·자막 등)가 나오지 않도록 프롬프트에서 금지 (한글 깨짐).

### 2-3. 브라우저 세션
- 고객 PC 의 **전용 크롬 프로필**(`apps/agent/.flow_profile/`, 커밋 금지)로 Flow 에 **사용자가 최초 1회 직접 로그인**. 비밀번호/쿠키를 코드가 다루지 않는다 (네이버 블로그와 같은 방식, `naver_blog` 프로필과 **별도 폴더**).
- 로그인 안 됨 / Flow 접근 불가 / 크레딧 소진 → 예외가 아니라 한국어 사유로 `warnings`.
- 헤드리스 대신 `headless=False` 기본 (로그인·캡차·UI 변경 디버깅 용이). 생성 중 사용자가 창을 건드리면 깨질 수 있으니 UI 에 안내 문구.

### 2-4. 자동화 단계
1. 프로필로 Flow 열기 → 로그인 상태 확인 (`check_session()`)
2. 새 프로젝트 만들기, 세로(9:16) 설정
3. 장면 프롬프트 입력 → 생성 시작
4. 완료 대기 (폴링, 타임아웃 `FLOW_CLIP_TIMEOUT_SEC`) → 결과 다운로드
5. 장면 반복 (같은 프로젝트 안에서 **순차**, 같은 세션을 병렬로 두드리지 않는다)
6. 다운로드한 클립 → FFmpeg concat → `shorts.mp4`

- **셀렉터는 `flow_web.FLOW_SELECTORS` 한 곳에만** (원칙 5). 네이버처럼 원격 셀렉터 JSON 갱신(`naver_selectors_url` 방식)도 재사용 가능한지 검토.
- 각 단계마다 실패 시 **스크린샷을 `output/<job_id>/debug/` 에 저장**(개발자 모드에서만, 로그엔 경로만, 고객 정보 노출 주의).
- 장면 단위 재시도 1회. 한 장면이 끝내 실패하면 → 그 장면만 건너뛰고(길이가 짧아짐) `warnings`, 전부 실패하면 `video_url=null` + 텍스트는 정상 반환.

## 3. 파일 설계 (B 영역 `apps/agent/media/**`)

```
media/
  flow_web.py        # Playwright 자동화 (FLOW_SELECTORS, check_session, generate_clip)
  flow_prompt.py     # 기획의 장면 → Flow 프롬프트 (대사 포함)
  video_assemble.py  # 클립 concat · 9:16 정규화  (기존 shorts_composer 대체/분리)
  video_provider.py  # Protocol + FakeProvider(ffmpeg color 클립, 테스트·키 없음 폴백)
```

```python
class ClipRequest(BaseModel):
    prompt: str                     # 샷 설명 + 음성 대사
    aspect: str = "9:16"

class VideoProvider(Protocol):
    async def check(self) -> tuple[bool, str]: ...          # (사용 가능, 한국어 사유)
    async def generate_clip(self, req: ClipRequest, out: Path) -> Path: ...
```

- 기존 `tts_subtitle.py` 는 **영상 경로에서 호출 제거**. 파일은 삭제 전에 다른 사용처 확인 후 정리(별도 PR).
- `FakeProvider`: CI/키 없음 환경에서 파이프라인 전체가 네트워크 없이 통과하도록. (원칙 2)

## 4. 계약(JSON) 영향 — 하위호환으로

영상이 수 분 걸리면 `/api/generate` 동기 응답으론 텍스트까지 늦어진다. **영상만 비동기로 분리**한다.

| 항목 | 변경 | 비고 |
|---|---|---|
| `Scene` | `video_prompt: str = ""`, `dialogue: str = ""` 추가 | 기존 `narration` 은 호환용 유지 (대사로 재사용 가능) |
| `GenerateResponse` | `video_status: "none"\|"pending"\|"ready"\|"failed" = "none"` 추가 | 기본 `none` → 기존 클라이언트 무영향 |
| 신규 | `GET /api/video/{job_id}/status` → `{status, message, video_url?}` | 웹이 폴링 |
| `GET /api/video/{job_id}` | 그대로 | 완료 후 MP4 |
| `ShortsContent.video_path` | 그대로 | 완료 시 채워짐 |

- 동작: `/api/generate` 는 기획 + 텍스트 2종을 끝내고 즉시 200 (`video_status="pending"`), 영상은 **백그라운드 태스크**로 계속. 웹은 status 를 폴링해 완료되면 미리보기 갱신.
- 한 PC 에서 영상 잡은 **동시에 1개만** (Flow 세션 1개). 두 번째 요청은 큐 대기 또는 `warnings`.
- 필드 추가뿐이라 하위호환. 그래도 `schemas.py` ⇄ `types.ts` ⇄ `agentClient.ts` Mock ⇄ `test_api_contract.py` 를 **같은 PR** 에서 맞추고 단체방 공지 (`CLAUDE.md` §3).
- 업로드(`/api/publish`)는 영상이 `ready` 가 아니면 instagram/youtube 를 `skipped` + "영상 생성 중" 한국어 사유로 반환.

## 5. 기획 프롬프트 — 영상 장면 확장 (골격)

```
소상공인 사장님 숏폼. 주제와 스타일에 맞춰 장면 4개를 설계하세요.
각 장면: shot(영어, 한 컷·단순한 카메라 움직임·실제로 촬영 가능한 소재),
        dialogue(한국어, 20~25자 이내 한 문장, 사장님 말투, 번역투/과장 표현 금지)
규칙: 영상 속 글자·로고·실제 브랜드명 없음, 얼굴 클로즈업 없음,
      수치·효능·전후비교 약속 없음, 첫 장면 대사가 훅.
```
- 대사는 `copy_rules.find_violations()` 로 **영상 생성 전에 검사**한다 (생성 후엔 못 고침, 크레딧 낭비).
- `BUSINESS.md` 숏폼 규칙(한자 병기 금지, 첫 문장 MBTI 4글자 직접 호명 금지 등)은 대사에 그대로 적용.

## 6. 안전·리스크
1. **약관**: Flow UI 자동화가 약관상 허용되는지 **확인 필요** (대표/이승준). 불가 판정이면 이 설계는 중단하고 수동 업로드 방식으로 전환. 고객 본인 PC·본인 계정·본인 크레딧으로만 실행하고, 판매자가 계정을 대리 운영하지 않는다.
2. **UI 변경에 취약**: 셀렉터 한 곳 + 스모크 스크립트 + 실패 시 한국어 안내. 네이버와 같은 유지보수 부담을 전제.
3. **크레딧 소모**: 생성 전 "영상 N개 생성됩니다" 확인 UI, 장면 수 상한, 재시도 1회.
4. **AI 생성 표시**: 인스타/유튜브의 AI 생성 콘텐츠 표시 정책 확인 → publishers(A)와 공유.
5. 로그에 쿠키·토큰·고객 상호 금지 (§6). `.flow_profile/` 는 `.gitignore` + 훅 차단 목록에 추가 (C, `.claude/**`).
6. 테스트는 외부 네트워크·실계정 없이: `FakeProvider` 로 파이프라인·상태 전이·concat 검증. 실제 Flow 스모크는 별도 수동 스크립트(스위트 제외).

## 7. 설정 (`.env.example` — 변수 이름만 공유, 값은 C 가 전달)
```
VIDEO_PROVIDER=fake                          # fake | flow_web
FLOW_PROFILE_DIR=apps/agent/.flow_profile    # 커밋 금지
FLOW_CLIP_TIMEOUT_SEC=300
FLOW_SCENE_COUNT=4
```
`config.py` 는 공동 영역 → 필드 추가는 단독 PR + 공지.

## 8. 이세림 오늘 할 일 (순서)
- [ ] **수동 스모크 먼저**: 브라우저에서 Flow 로 세로 8초 클립을 직접 만들어 보고 확인 → ① 한국어 대사 음성 품질 ② 클립 길이·해상도 ③ Extend 기능 유무 ④ 다운로드 경로(UI 단계) ⑤ 크레딧 소모량
- [ ] 위 결과를 이 문서 §2 에 반영 (특히 한국어 음성이 쓸 만한지가 **go / no-go**)
- [ ] `video_provider.py` (Protocol + `FakeProvider`) + 테스트
- [ ] `flow_web.py` 뼈대: 프로필 열기 · `check_session()` · 클립 1개 생성/다운로드 (셀렉터 상수화)
- [ ] `video_assemble.py`: concat + 9:16 정규화 + 테스트 (`ffmpeg_available()` 가드)
- [ ] 기획 프롬프트에 장면(shot/dialogue) 확장, 대사 `copy_rules` 검사 연결

## 9. 박영준·이승준과 맞출 것
- 박영준: 웹에서 `video_status` 폴링 UI, 영상 미완료 시 업로드 버튼 상태, "영상 생성 중 창을 건드리지 마세요" 안내. 쓰레드/블로그는 영상과 무관하게 먼저 발행 가능해야 함.
- 이승준: 약관 확인, `.flow_profile/` 차단, `.env.example` 반영, 공유 PR 순서(계약 변경 PR 먼저).

## 10. 열린 질문
1. Flow 한국어 음성이 품질 미달이면 → 대사 없는 영상 + BGM 으로 갈지, 영어 음성 허용할지?
2. 영상 완료까지 수 분 → 비동기 잡 방식(§4)에 전원 동의?
3. 인스타·유튜브 업로드는 영상 `ready` 후 자동 진행이 아니라 **사람이 UI 에서 확인 후 직접** (원칙 1) 맞는지 재확인.
