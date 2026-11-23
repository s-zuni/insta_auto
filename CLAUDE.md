# CLAUDE.md — insta_auto 프로젝트 헌법

소상공인·1인 사업가용 **올인원 AI 마케팅 자동화 하이브리드 패키지**.
사용자가 *주제 × 스타일*을 고르면 AI가 **숏폼 MP4(Google Flow 생성, 음성 포함·자막 없음) + 쓰레드 체인 + 네이버 블로그 원고**를 동시에 만들고,
검수 후 **인스타 릴스 · 유튜브 쇼츠 · 쓰레드 · 네이버 블로그**에 원클릭 발행한다.

## 1. 아키텍처 & 모노레포 경계
```
apps/web   (Next.js 14, TS, Tailwind)  ──HTTP JSON──▶  apps/agent (FastAPI, Python 3.11+)
  화면 · 인증 · 라이선스 입력 · DB                      기획 · 글 생성 · Flow 영상 자동화 · 4채널 업로드
  demo 모드: agentClient.ts 의 Mock                     local 모드: 고객 PC 에서 실행 (고객 IP·크롬 세션·FFmpeg)
```
**경계 규칙 (어기면 리뷰에서 반려)**
| | `apps/web` 가 하는 일 | `apps/web` 가 **하지 않는** 일 |
|---|---|---|
| ✅ | UI, 3분할 에디터, Supabase 인증/라이선스 조회, 사용자 입력 검증 | ❌ LLM 호출, 영상 처리, SNS/네이버 API 호출, 플랫폼 토큰 보관 |

| | `apps/agent` 가 하는 일 | `apps/agent` 가 **하지 않는** 일 |
|---|---|---|
| ✅ | 프롬프트·생성(`generators`), Flow 영상 자동화(Playwright)·FFmpeg 이어붙이기(`media`), 업로드(`publishers`), 라이선스 검증(`core/license`) | ❌ HTML/UI 렌더링, Supabase 사용자 테이블 직접 수정, 결제 처리 |

- 두 앱은 **§3 의 JSON 계약으로만** 대화한다. 서로의 파일을 import 하지 않는다.
- **demo** (`NEXT_PUBLIC_APP_MODE=demo`): Vercel 배포, Mock 응답, 실제 업로드 없음.
- **local** (`NEXT_PUBLIC_APP_MODE=local`): `scripts/start_local.*` 로 Agent(8787) + Web(3000) 동시 기동.
- 플로우: `POST /api/generate` → **기획 1회 → (병렬) Flow 영상 · 쓰레드 글 · 블로그 글** → 3분할 에디터에서 수정 → `POST /api/publish` (채널별 독립 실행).
  - 영상은 **Google Flow 를 Playwright 로 자동화**(공식 API 없음)하고 **Flow 가 만든 음성을 그대로 쓴다. TTS·자막은 쓰지 않는다.**
  - 영상은 수 분 걸리므로 텍스트 2종을 먼저 돌려주고 영상은 비동기로 이어진다. 상세 설계: `docs/drafts/2026-11-23_flow_video_pipeline.md`.
- `_legacy_archive/` 는 폐기된 사주/MBTI 봇 코드. **읽기 전용 참고용, 수정·import 금지.**

## 2. 팀 소유권 & 충돌 방지 (3인 / 8주)
| 담당 | 사람 | 영역 | 디렉토리 |
|---|---|---|---|
| **A** Web·발행 코드 | 박영준 | 화면, 3분할 에디터, 온보딩 모달, 4채널 업로더 코드 | `apps/web/**`, `apps/agent/publishers/**` |
| **B** AI·영상 | 이세림 | 프롬프트 매트릭스, Claude API, 기획, Flow 영상 자동화(Playwright), FFmpeg 이어붙이기 | `apps/agent/generators/**`, `apps/agent/media/**`, `apps/agent/assets/**` |
| **C** 인프라·하네스·리뷰 | 이승준 | Vercel·Supabase·GitHub·Slack·Notion 세팅, 키·계정 발급, CI, 하네스, PR 리뷰/머지 | `.claude/**`, `.github/**`, `scripts/**`, 인프라 설정 |
| 공동 | 전원 | 계약·설정 | `apps/agent/core/**`, `apps/web/src/lib/types.ts`, `CLAUDE.md` |

> **현재 스프린트 포커스**: A(박영준)=쓰레드(글 생성 품질·업로더·웹 폴링 UI), B(이세림)=Flow 영상 자동화. 디렉토리 소유권은 위 표 그대로. 오늘 할 일: `docs/drafts/` 의 today 문서.
> 1차 배정이며 킥오프에서 바뀔 수 있다. 바뀌면 이 표와 `.claude/team.json` 을 같이 고친다.
> **키·계정은 C, 코드는 A·B**: 플랫폼 앱 등록·토큰 발급·Supabase 프로젝트 생성은 C 가 하고, A·B 는 `.env.example` 의 변수 이름만 보고 코드를 짠다.

**충돌 방지 규칙**
1. **내 디렉토리만 수정**한다. 다른 사람 영역을 고쳐야 하면 ① PR 설명에 이유 ② 해당 담당을 리뷰어로 지정.
2. **공동 파일**(`core/**`, `types.ts`, `CLAUDE.md`)은 작게, 단독 PR 로. 팀 단체방에 "schemas 수정 PR 올림" 한 줄 공지.
3. 하루 1번 이상 `git pull origin main` → 내 브랜치에 반영. 브랜치는 **3일 넘기지 않고** PR.
4. 같은 파일을 둘이 동시에 고쳐야 하면 먼저 단체방에서 순서를 정한다 (먼저 머지 → 나중 사람이 rebase/merge).
5. 새 의존성(`requirements.txt`, `package.json`) 추가는 PR 제목에 `[deps]` 표시.

## 3. Web ↔ Agent JSON API 계약
정본: `apps/agent/core/schemas.py`(Pydantic) ⇄ `apps/web/src/lib/types.ts`. 아래는 요약이며 **필드가 다르면 코드가 맞다**.

```jsonc
// POST /api/generate  — GenerateRequest
{ "business_type": "카페", "topic": "원두 보관법",         // topic 2자 이상
  "style": "info|story|review|promo|empathy",
  "brand_name": "", "extra_context": "", "render_video": true }

// 200 — GenerateResponse
{ "job_id": "a1b2c3d4e5f6",
  "content": {
    "shorts":  { "title": "", "scenes": [{ "narration": "", "on_screen_text": "", "image_prompt": "" }],
                 "caption": "", "hashtags": [""], "video_path": null, "duration_sec": null },
    "threads": { "posts": ["첫 글(500자 이내)", "이어쓰기…"] },
    "blog":    { "title": "", "body_markdown": "## 소제목…", "tags": [""], "meta_description": "" } },
  "video_url": "/api/video/{job_id} | null",
  "warnings": ["영상 생성 실패: …"],        // 영상 실패해도 텍스트는 200 으로 반환
  "mock": false }                           // API 키 없으면 true

// POST /api/publish  — PublishRequest
{ "job_id": "", "channels": ["instagram","youtube","threads","naver_blog"],   // 1개 이상
  "content": { /* 에디터에서 수정한 GeneratedContent */ }, "dry_run": true }

// 200 — PublishResponse  (채널 하나가 실패해도 전체는 200)
{ "job_id": "", "results": [{ "channel": "threads", "status": "ok|failed|dry_run|skipped",
                              "url": null, "message": "한국어 사유" }] }
```
- 기타: `GET /health`(라이선스 없이도 항상 열림), `GET /api/video/{job_id}`(MP4).
- **도입 예정 (하위호환 추가, 코드에 들어가기 전까지는 코드가 정본)**: `Scene.video_prompt`·`Scene.dialogue`, `GenerateResponse.video_status("none|pending|ready|failed", 기본 none)`, `GET /api/video/{job_id}/status`. 넣는 PR 은 §3 동기화 규칙대로 양쪽+테스트+Mock 을 한 번에.
- 에러: 입력 오류 `422`, 라이선스 없음 `403`. 그 외 채널 오류는 예외가 아니라 `status:"failed"`.

**계약 동기화 규칙 (가장 중요)**
- 한쪽을 바꾸면 **같은 PR** 에서 반대쪽 + `tests/test_api_contract.py` + `agentClient.ts` 의 Mock 까지 고친다.
- 스타일 id 는 `matrix_prompt.py: STYLE_MATRIX` 와 `lib/presets.ts: STYLES` 에서 동일해야 한다.
- 필드 **추가**는 기본값을 줘서 하위호환으로. 필드 **삭제·이름 변경**은 전원 합의 후.

## 4. 명령어
```bash
# Agent (저장소 루트)
python -m venv apps/agent/.venv && apps/agent/.venv/Scripts/pip install -r apps/agent/requirements.txt
apps/agent/.venv/Scripts/python -m pytest -q
apps/agent/.venv/Scripts/python -m uvicorn apps.agent.main:app --port 8787 --reload
apps/agent/.venv/Scripts/python -m apps.agent.core.copy_rules <원고.md>   # 금지어 검사
# Web
cd apps/web && npm install && npm run dev        # typecheck / lint / build 도 있음
# 로컬 패키지 통합 실행
scripts\start_local.bat        # macOS: ./scripts/start_local.sh
```
(macOS/Linux 는 `.venv/Scripts` → `.venv/bin`)

## 5. 개발 원칙
1. **안전한 기본값**: 발행은 `dry_run=true` 가 기본. 실제 발행은 사람이 UI에서 확인 후 직접. Claude/CI/테스트가 `dry_run=false` 를 호출하지 않는다.
2. **키 없이도 동작**: `ANTHROPIC_API_KEY` 등이 없으면 Mock/Dry-run 으로 폴백한다. 테스트는 외부 네트워크·실계정 없이 통과해야 한다.
3. **채널 독립성**: 한 채널 실패가 다른 채널을 막지 않는다. 실패는 예외 대신 `PublishResult(status="failed", message=한국어 사유)` 로 반환.
4. **영상 실패 ≠ 전체 실패**: 렌더링 오류는 `warnings` 로 알리고 텍스트 콘텐츠는 반환한다.
5. **셀렉터는 한 곳에**: Playwright 셀렉터는 네이버는 `naver_blog.SELECTORS`, Flow 는 `flow_web.FLOW_SELECTORS` 에만 둔다.
6. 타입 힌트 필수(Python/TS strict), 새 로직엔 테스트 추가, 주석·UI 문구는 한국어.
7. **영상 음성은 Flow 가 만든다**: TTS·자막(ASS)·`tts_subtitle.py` 를 영상 경로에 다시 끌어들이지 않는다. 대사는 기획 단계에서 정하고 **생성 전에** `copy_rules` 로 검사한다(생성 후엔 못 고치고 크레딧만 낭비).
8. **병렬 단계는 서로 독립**: 영상·쓰레드·블로그 중 하나가 실패/지연돼도 다른 결과는 즉시 반환·발행 가능. Flow 세션은 하나라서 영상 잡은 PC당 동시 1개, 장면은 순차 생성.
9. **외부 서비스 자동화는 사용자 본인 계정·PC·세션으로만**: 로그인은 사용자가 직접 1회, 코드는 비밀번호·쿠키를 다루지 않는다. Flow 자동화 약관 확인 전에는 `VIDEO_PROVIDER=fake` 가 기본.

## 6. 보안 / 금지 사항
- `.env`, `*.key`, `apps/agent/.browser_profile/`, `apps/agent/.flow_profile/`, `*.mp4`, `apps/agent/output/` 는 **커밋 금지** (훅이 차단).
- 라이선스 **비밀키**는 판매자 PC 에만. 고객 배포본에는 **공개키만**. `SUPABASE_SERVICE_ROLE_KEY` 도 고객 배포본·`NEXT_PUBLIC_*` 금지.
- 로그/에러/PR 에 토큰·쿠키·고객 상호를 출력하지 않는다. 키는 Slack·카톡으로 주고받지 않는다(C 가 직접 전달).

## 7. Git / PR 규칙
- 브랜치: `feat/<기능명>` (예: `feat/thread`, `feat/flow`), `fix/<설명>`. `main` 직접 push 금지, force push 금지.
- 커밋: `feat:`, `fix:`, `chore:`, `docs:` 접두어. PR 전 **`harness-verify` 스킬** 실행 → CI(`pr-check-and-slack.yml`)가 Slack 으로 결과 알림.
- 머지는 C 리뷰 1명 승인 후. 내 영역 밖을 건드린 PR 은 해당 담당 승인도 필요.

## 8. 스킬 (`.claude/skills/`)
| 스킬 | 언제 | 주 사용자 |
|---|---|---|
| `notion-spec-sync` | Notion PRD/티켓 → 스키마·타입 동기화 | 전원 |
| `prompt-tuner` | 한국어 원고 품질 채점·금지어 검사·프롬프트 튜닝 | B |
| `publisher-tester` | 업로더 Dry-run, 네이버 셀렉터 점검 | A |
| `flow-video-tester` | Flow 영상 파이프라인 Fake 검증, 세션·셀렉터 점검, 수동 스모크 체크리스트 | B |
| `harness-verify` | PR 전 검증 + Slack 브리핑 생성 | 전원 |
| `start` | `/start` 데일리 킥오프: git → 점검 → Notion 할 일 → 팀원별 Slack (설정: `.claude/team.json`) | C |

## 9. 한국어 카피라이팅 규칙 (생성 프롬프트 공통)
**정본은 `apps/agent/core/copy_rules.py`** — 프롬프트(`prompt_rules()`)와 검사기(`find_violations()`)가 같은 목록을 쓴다. 규칙을 바꾸면 이 표도 고친다.

| 분류 | 금지 | 이렇게 |
|---|---|---|
| AI 번역투 | `~에 대해`, `~를 통해`, `~것이 가능`, `~하는 것이 중요`, `~로 인해`, `~되어지다/되어졌다`, `~하도록 하겠습니다`, `~에 있어서`, `~를 가지고 있다` | 원두 보관법 / 앱으로 예약 / ~할 수 있어요 / 꼭 ~하세요 / ~때문에 / 돼요 / ~할게요 |
| 과장 광고 (표시광고법) | 근거 없는 `업계·국내 1위/최초/유일`, `최고의·최상의·역대급`, `100% 만족/효과/보장`, `무조건`, `완벽한`, `평생 보장` | 확인 가능한 사실 ("매일 아침 직접 로스팅", "이번 주 금요일까지") |
| 효능 단정 | `치료/완치됩니다`, `살이 빠집니다`, `부작용 없음`, `피부·탈모 개선 보장` | 경험·과정 묘사, "개인차가 있어요" |
| 허위 | 가짜 후기, 없는 수치·고객 수 | 실제 정보만, 모르면 `(사장님 확인 필요)` 표시 |

스타일: 한 문장 40자 안팎 · 첫 문장이 훅 · 채널별 톤(숏폼=또렷, 쓰레드=반말·친근·이모지 거의 없음, 블로그=정보형 존댓말·소제목 3~4개).
