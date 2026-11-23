# 오늘(2026-11-23) 역할별 할 일 — 이승준 확인용 (팀 공유 전)

주제: "1인 사업·소상공인을 위한 마케팅 자동화"
목표: **쓰레드 글 2건 확정 + Flow 영상 자동화 파이프라인 첫 뼈대**
로직: 주제 → 기획 → (병렬) Flow 영상 / 쓰레드 / 블로그 → 채널별 업로드. 음성은 Flow, TTS·자막 없음.

## 머지 순서 (의존 관계)
1. **하네스 PR (이승준)** — CLAUDE.md·스킬·훅 갱신. 먼저 머지해야 팀원 Claude 가 새 규칙을 읽는다.
2. **계약 PR (이승준)** — `video_status` 등 하위호환 필드 추가 (스키마+타입+Mock+테스트 한 번에). A·B 가 이걸 기다린다.
3. A·B 기능 PR — 각자 브랜치, 서로 다른 디렉토리라 충돌 없음.

## 공통 유의사항 (확정)
1. 시작 전 `main` 에서 `git pull origin main`.
2. Flow 는 하루 무료 크레딧이 지급되므로 요금 지출 없음 → 각자 본인 구글 계정으로 로그인 가능 (로그인은 직접).
3. 오늘은 **자동화 코드만**. 테스트 계정과 API 는 **수요일(11/25) 안으로 이승준이 따로 안내**. 그 전엔 `VIDEO_PROVIDER=fake`, Flow 실호출·`dry_run=false` 금지.
4. 완성되면 각자 브랜치(박영준 `feat/thread`, 이세림 `feat/flow`) → `harness-verify` → 이승준에게 PR. (브랜치 규칙은 CLAUDE.md §7 에 `feat/<기능명>` 으로 반영됨)

## 박영준 (A) — 쓰레드
| 순서 | 할 일 | 산출물 / 완료 기준 |
|---|---|---|
| 1 | 쓰레드 글 2건 검수·확정 (`docs/drafts/2026-11-23_threads_posts.md`): 1인칭 페르소나, 링크, 마지막 질문형 | `copy_rules` 통과, 확정본 |
| 2 | `publisher-tester` 로 threads 업로더 Dry-run 점검 (글당 ≤500자, 체인 발행 흐름, 키 없음 폴백) | pytest 통과, 한국어 실패 사유 확인 |
| 3 | 쓰레드 체인 업로더 보강이 필요하면 `publishers/threads.py` 수정 + 테스트 | dry_run 기준 통과 (**실발행 금지**) |
| 4 | 웹: 영상이 늦게 오는 상태 처리 — 텍스트 먼저 표시, 영상 `pending` 표시, 영상 미완료 시 인스타/유튜브 발행 버튼 비활성, "생성 중 창을 건드리지 마세요" 안내 | 계약 PR 머지 후 Mock 으로 동작 (`agentClient.ts`) |
| 5 | (선택) `threads_gen.py` 프롬프트를 `prompt-tuner` 로 점검 | ⚠ 이 파일은 B 영역 → 아래 "결정 필요" 1번 |

## 이세림 (B) — 영상 자동화
| 순서 | 할 일 | 산출물 / 완료 기준 |
|---|---|---|
| 1 | **Flow 수동 스모크 먼저** (`flow-video-tester` §3 체크리스트): 세로 클립 1개를 직접 생성 | 한국어 음성 품질·클립 길이·Extend 유무를 설계 문서 §2 에 기록 → **go/no-go** |
| 2 | `media/video_provider.py` — Protocol + `FakeProvider` + 테스트 | 키·계정 없이 pytest 통과 |
| 3 | `media/video_assemble.py` — 클립 concat + 9:16 정규화 (TTS·자막 없음) | `ffmpeg_available()` 가드 테스트 |
| 4 | `media/flow_web.py` 뼈대 — 전용 프로필 열기, `check_session()`, 클립 1개 생성·다운로드, `FLOW_SELECTORS` 상수화 | 실제 Flow 호출은 수동만, 테스트엔 미포함 |
| 5 | 기획 프롬프트에 장면 확장 (`shot` 영어, `dialogue` 한국어 20~25자) + 대사 `copy_rules` 사전 검사 | 위반 시 영상 생성 안 함 |

⚠ 스모크 결과가 "한국어 음성 품질 미달"이면 2~5 를 진행하기 전에 단체방에서 대안(대사 없는 영상+BGM 등) 먼저 합의.

## 이승준 (C)
| 순서 | 할 일 |
|---|---|
| 1 | **Flow 자동화 약관 확인** (불허면 설계 중단 → 수동 업로드 방식). 확인 전 `VIDEO_PROVIDER=fake` 기본 |
| 2 | 하네스 PR 올리기: `CLAUDE.md`, `.claude/skills/flow-video-tester/`, `.claude/settings.json`, `.claude/team.json`, `scripts/hooks/guard_bash.py`, `.gitignore` → `harness-verify` 후 머지 |
| 3 | 계약 PR (공동 파일, 단독): `Scene.video_prompt/dialogue`, `video_status`, `GET /api/video/{job_id}/status` — `schemas.py` ⇄ `types.ts` ⇄ `agentClient.ts` Mock ⇄ `test_api_contract.py` 같은 PR. 단체방에 한 줄 공지 |
| 4 | `.env.example` 에 `VIDEO_PROVIDER / FLOW_PROFILE_DIR / FLOW_CLIP_TIMEOUT_SEC / FLOW_SCENE_COUNT` 변수 이름 추가 |
| 5 | A·B PR 리뷰·머지 (영역 밖 변경 PR 은 해당 담당 승인 포함) |

## 결정 필요 (이승준)
1. `threads_gen.py` 는 규칙상 B(`generators/**`). 쓰레드 글 품질을 박영준이 맡으려면 **이번 스프린트 한정으로 이 파일을 A 에 이관**할지, B 가 수정하고 A 가 리뷰할지.
2. 계약 PR 을 이승준이 직접 쓸지, 이세림에게 맡길지 (웹 파일 포함이라 C 가 쓰는 걸 권장).
3. 영상 완료 후 인스타·유튜브 업로드는 자동 진행이 아니라 **사람이 UI 에서 확인 후 직접** (CLAUDE.md 원칙 1) — 이대로 확정?

## 단체방 공지 초안 (승인하면 보낼 내용 — 아직 전송 안 함)
> 오늘 목표: 쓰레드 글 2건 확정 + Flow 영상 자동화 뼈대.
> 순서: ① 하네스 PR(승준) → ② 계약 PR(승준) → ③ 각자 기능 PR. 각자 시작 전 `git pull origin main`.
> 영준님/세림님 할 일은 `docs/drafts/2026-11-23_today_plan.md` 참고. 영상 음성은 Flow, TTS·자막은 안 씁니다. 실발행(dry_run=false)은 사람이 UI에서만.
