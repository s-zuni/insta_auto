# insta_auto — 올인원 AI 마케팅 자동화 패키지

소상공인·1인 사업가를 위한 **웹 UI(Next.js) + 로컬 에이전트(FastAPI)** 하이브리드 제품.
주제와 스타일만 고르면 **숏폼 영상 · 쓰레드 체인 · 네이버 블로그 원고**를 한 번에 만들고,
**인스타 릴스 · 유튜브 쇼츠 · 쓰레드 · 네이버 블로그**에 원클릭 발행합니다.

## 아키텍처
```
┌────────────── apps/web (Next.js) ──────────────┐        ┌──────────── apps/agent (FastAPI) ────────────┐
│ TopicStyleSelector → PreviewEditor(3분할) → 발행 │ ─HTTP─▶│ /api/generate: matrix_prompt → threads/blog  │
│ agentClient.ts  (demo: Mock / local: Agent 호출) │        │               + tts_subtitle → shorts_composer│
└─────────────────────────────────────────────────┘        │ /api/publish : instagram|youtube|threads|naver│
                                                            │ core: config · schemas(계약) · license(HWID) │
                                                            └───────────────────────────────────────────────┘
```
| 모드 | 용도 | 설정 |
|---|---|---|
| **demo** | Vercel 시연·랜딩. 목 데이터, 업로드 없음 | `NEXT_PUBLIC_APP_MODE=demo` |
| **local** | 고객 PC. 고객 IP·크롬 세션·FFmpeg 로 실제 생성/업로드 | `NEXT_PUBLIC_APP_MODE=local` + `scripts/start_local.*` |

## 빠른 시작
### 고객/데모용 (원클릭)
- Windows: `scripts\start_local.bat` · macOS: `./scripts/start_local.sh`
- 첫 실행 시 `.env` 가 생성되면 키를 채우고 다시 실행 → 브라우저가 `http://localhost:3000` 으로 열립니다.
- 필요: Python 3.11+, Node 20+, FFmpeg (없으면 영상만 비활성화)

### 개발자용
```bash
cp .env.example .env
python -m venv apps/agent/.venv
apps/agent/.venv/Scripts/pip install -r apps/agent/requirements.txt     # macOS: .venv/bin
apps/agent/.venv/Scripts/python -m pytest -q
apps/agent/.venv/Scripts/python -m uvicorn apps.agent.main:app --port 8787 --reload

cd apps/web && npm install && npm run dev                                # http://localhost:3000
```
Vercel 배포: Root Directory = `apps/web`, 환경변수 `NEXT_PUBLIC_APP_MODE=demo`.

## 현재 구현 상태 (초기 세팅)
| 영역 | 상태 |
|---|---|
| Web 대시보드 · 3분할 에디터 · Demo Mock | ✅ 동작 (typecheck/lint/build 통과) |
| Agent API · 스키마 · Mock 파이프라인 · 테스트 6종 | ✅ 통과 |
| 라이선스(Ed25519 + HWID) 오프라인 검증 | ✅ + 발급 CLI `scripts/issue_license.py` |
| TTS(edge-tts) + FFmpeg 숏폼 렌더링 | ✅ 단일 컬러 배경 + 자막 (1080×1920 확인) |
| AI 이미지 배경 / BGM 믹싱 | ⏳ 미구현 (팀원 B) |
| Threads · Instagram · YouTube 업로더 | 🟡 실호출 코드 작성, **실계정 미검증** (Dry-run만 검증) |
| 네이버 블로그 업로더 | 🟡 골격·셀렉터 **미검증** (팀원 C) |
| Supabase 라이선스 폐기/DB 연동 | ⏳ 미구현 (팀원 A) |

## 8주 로드맵 (제안)
| 주 | A (Web/DB) | B (AI/Media) | C (Publisher/Harness) |
|---|---|---|---|
| 1 | 레포 세팅·디자인 시스템 | 프롬프트 매트릭스 v1 | 하네스·CI·Slack·Notion 연동 |
| 2 | 대시보드·에디터 완성 | 한국어 품질 튜닝 | 쓰레드 업로더 실검증 |
| 3 | Supabase 스키마·인증 | TTS·자막 싱크 개선 | 유튜브 OAuth·업로드 검증 |
| 4 | 라이선스 서버 연동 | 이미지 배경 + 템플릿 | 인스타 Graph API 검증 |
| 5 | 데모 사이트/랜딩 | BGM·효과음 믹싱 | 네이버 에디터 자동화 |
| 6 | 설치 UX·에러 화면 | 업종별 프리셋 확장 | 실패 재시도·로그 |
| 7 | 통합 QA | 통합 QA | 패키징(zip/인스톨러) |
| 8 | 시연·문서 | 시연·문서 | 배포·운영 가이드 |

## 폴더
```
apps/web/            Next.js 대시보드        apps/agent/generators/  콘텐츠 기획·생성
apps/agent/core/     설정·스키마·라이선스     apps/agent/media/       TTS·자막·FFmpeg
apps/agent/publishers/ 4대 채널 업로더        .claude/                 하네스(settings·skills)
scripts/             실행기·훅·라이선스 발급   _legacy_archive/         기존 코드 보관(미사용)
```
팀 규칙과 계약 동기화 원칙은 [CLAUDE.md](./CLAUDE.md) 참고.
