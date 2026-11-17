# CLAUDE.md — insta_auto 프로젝트 헌법

소상공인·1인 사업가용 **올인원 AI 마케팅 자동화 하이브리드 패키지**.
사용자가 *주제 × 스타일*을 고르면 AI가 **숏폼 MP4 + 쓰레드 체인 + 네이버 블로그 원고**를 동시에 만들고,
검수 후 **인스타 릴스 · 유튜브 쇼츠 · 쓰레드 · 네이버 블로그**에 원클릭 발행한다.

## 1. 아키텍처 한눈에
```
apps/web   (Next.js 14, TS, Tailwind)  ──HTTP──▶  apps/agent (FastAPI, Python 3.11+)
  demo 모드: agentClient.ts 의 Mock          local 모드: 고객 PC 에서 generators/media/publishers 실행
```
- **demo** (`NEXT_PUBLIC_APP_MODE=demo`): Vercel 배포, 목 데이터, 실제 업로드 없음.
- **local** (`NEXT_PUBLIC_APP_MODE=local`): `scripts/start_local.*` 로 Agent(8787) + Web(3000) 동시 기동. 고객 IP·크롬 세션·FFmpeg 사용.
- 플로우: `POST /api/generate` → 3종 콘텐츠 → 3분할 에디터에서 수정 → `POST /api/publish` (채널별 독립 실행).
- `_legacy_archive/` 는 폐기된 사주/MBTI 봇 코드. **읽기 전용 참고용, 수정·import 금지.**

## 2. 팀 소유권 (3인 / 8주)
| 담당 | 영역 | 디렉토리 |
|---|---|---|
| **A** Web/DB/Vercel | 프론트, 3분할 에디터, Supabase 라이선스/DB | `apps/web/**` |
| **B** AI/Media | 프롬프트 매트릭스, TTS, 자막, FFmpeg 렌더링 | `apps/agent/generators/**`, `apps/agent/media/**`, `apps/agent/assets/**` |
| **C** Publisher/Harness | 4대 채널 업로더, 하네스·Notion·Slack | `apps/agent/publishers/**`, `.claude/**`, `.github/**`, `scripts/**` |
| 공동 | 계약·설정 | `apps/agent/core/**`, `apps/web/src/lib/types.ts`, `CLAUDE.md` |

내 영역 밖을 고쳐야 하면 PR 설명에 이유를 적고 해당 담당을 리뷰어로 지정한다.

## 3. 계약 동기화 규칙 (가장 중요)
- Web ↔ Agent 입출력은 `apps/agent/core/schemas.py` (Pydantic) 와 `apps/web/src/lib/types.ts` 가 **1:1** 이다.
- 한쪽을 바꾸면 **같은 PR** 에서 반대쪽 + `tests/test_api_contract.py` + `agentClient.ts` 의 Mock 까지 고친다.
- 스타일 id(`info|story|review|promo|empathy`)는 `matrix_prompt.py: STYLE_MATRIX` 와 `lib/presets.ts: STYLES` 에서 동일해야 한다.

## 4. 명령어
```bash
# Agent (저장소 루트)
python -m venv apps/agent/.venv && apps/agent/.venv/Scripts/pip install -r apps/agent/requirements.txt
apps/agent/.venv/Scripts/python -m pytest -q
apps/agent/.venv/Scripts/python -m uvicorn apps.agent.main:app --port 8787 --reload
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
5. **셀렉터는 한 곳에**: Playwright 셀렉터는 `naver_blog.SELECTORS` 에만 둔다.
6. 타입 힌트 필수(Python/TS strict), 새 로직엔 테스트 추가, 주석·UI 문구는 한국어.

## 6. 보안 / 금지 사항
- `.env`, `*.key`, `apps/agent/.browser_profile/`, `*.mp4`, `apps/agent/output/` 는 **커밋 금지** (훅이 차단).
- 라이선스 **비밀키**는 판매자 PC 에만. 고객 배포본에는 **공개키만**. `SUPABASE_SERVICE_ROLE_KEY` 도 고객 배포본 금지.
- 로그/에러/PR 에 토큰·쿠키·고객 상호를 출력하지 않는다.
- 플랫폼 약관·허위/과장 광고: 생성 프롬프트는 효능 단정·허위 후기를 만들지 않는다.

## 7. Git / PR 규칙
- 브랜치: `feat/<A|B|C>-<설명>`, `fix/...`. `main` 직접 push 금지, force push 금지.
- 커밋: `feat:`, `fix:`, `chore:`, `docs:` 접두어. PR 전 **`harness-verify` 스킬** 실행 → CI(`pr-check-and-slack.yml`)가 Slack 으로 결과 알림.

## 8. 스킬 (`.claude/skills/`)
| 스킬 | 언제 |
|---|---|
| `notion-spec-sync` | Notion PRD/티켓 → 스키마·타입 동기화 |
| `prompt-tuner` | 한국어 원고 품질 채점·프롬프트 튜닝 |
| `publisher-tester` | 업로더 Dry-run, 네이버 셀렉터 점검 |
| `harness-verify` | PR 전 검증 + Slack 브리핑 생성 |

## 9. 한국어 원고 기준 (생성 프롬프트 공통)
번역투(`~에 대해/~를 통해/~것이 가능`) 금지 · 한 문장 40자 안팎 · 첫 문장이 훅 · 채널별 톤(숏폼=또렷, 쓰레드=반말·친근·이모지 거의 없음, 블로그=정보형·소제목 3~4개).
