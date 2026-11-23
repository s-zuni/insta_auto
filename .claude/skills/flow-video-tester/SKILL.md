---
name: flow-video-tester
description: Google Flow(Playwright) 영상 파이프라인을 Fake 로 검증하고, Flow 로그인 세션·셀렉터를 점검하고, 수동 스모크 체크리스트를 돌린다. "Flow 테스트", "영상 파이프라인 점검", "flow 셀렉터", "영상 스모크" 요청 시 사용.
---

# flow-video-tester

대상: `apps/agent/media/{flow_web,flow_prompt,video_assemble,video_provider}.py`.
설계 정본: `docs/drafts/2026-11-23_flow_video_pipeline.md`. **설계와 코드가 다르면 코드가 맞다** (설계가 낡았으면 문서를 고친다).

## 불변 규칙 (어기면 중단하고 알린다)
- 영상 음성은 **Flow 가 만든 것**을 쓴다. TTS·자막(ASS)·`tts_subtitle.py` 를 영상 경로에 다시 넣지 않는다.
- Flow 셀렉터는 `flow_web.FLOW_SELECTORS` **한 곳에만**.
- 로그인은 **사용자가 직접** 한다. 비밀번호·쿠키를 읽거나 출력·저장하지 않는다. `apps/agent/.flow_profile/` 는 읽기·커밋 금지.
- **Claude/CI/테스트는 실제 Flow 생성을 호출하지 않는다** (크레딧 소모). 실제 생성은 사람이 수동 스모크로만.
- 테스트는 외부 네트워크·실계정 없이 통과해야 한다 → 기본 `VIDEO_PROVIDER=fake`.

## 1. Fake 검증 (항상 먼저, 자동 실행 OK)
```bash
apps/agent/.venv/Scripts/python -m pytest apps/agent/tests -q        # macOS: .venv/bin/python
```
확인할 것:
| 항목 | 기대 |
|---|---|
| FakeProvider 로 장면 N개 → concat → `shorts.mp4` | 생성됨, 1080x1920, 길이 ≈ 장면 수 × 클립 길이 (`ffmpeg_available()` 가드, 없으면 skip 표시) |
| 한 장면 실패 | 그 장면만 건너뛰고 `warnings` 한국어 사유, 나머지 진행 |
| 전부 실패 / 세션 없음 | 예외 아님. `video_url=null`, 텍스트 콘텐츠는 정상 반환 |
| 상태 전이 | `pending → ready/failed`, 동시 영상 잡 1개 제한 |
| 대사 검사 | 영상 생성 **전에** `copy_rules.find_violations()` 호출, 위반 시 생성 안 함 |

## 2. 세션·셀렉터 점검 (UI 가 바뀌었을 때, 사람이 로그인 완료한 상태에서만)
1. 사용자에게 Flow 전용 프로필로 로그인돼 있는지 확인 요청 (안 돼 있으면 로그인 안내 후 중단).
2. Playwright 로 **Flow 편집 화면까지만** 열고 **생성 버튼은 누르지 않는다.** `FLOW_SELECTORS` 각 항목에 `locator.count()` → `OK / MISSING`.
3. MISSING 이면 텍스트·aria-label 기반 대체 후보 2~3개 제안 (클래스 해시 의존 최소화). 수정은 `FLOW_SELECTORS` 한 곳에서만, 수정 후 다시 `count()`.

## 3. 수동 스모크 (사람이 직접, 크레딧 소모 — 기록만 도와준다)
1장면 세로 클립 1개를 사람이 생성하게 하고 결과를 설계 문서 §2 에 기록:
- [ ] 한국어 대사가 한국어 음성으로 나오는가 (go/no-go)
- [ ] 대사 20~25자가 클립 길이 안에 들어가는가
- [ ] 장면이 바뀌어도 목소리가 유지되는가
- [ ] 클립 길이·해상도, 크레딧 소모량
- [ ] Extend(이어 만들기) 기능 유무, 다운로드 UI 단계

## 설명 방식
팀원 대부분이 개발 초보다. 실패·경고는 **무엇이 / 왜 / 다음에 칠 명령어** 순서로 쉬운 말로, 전문용어는 처음 한 번 괄호로 풀어 쓴다.
