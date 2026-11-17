---
name: notion-spec-sync
description: Notion MCP로 PRD/티켓(스펙)을 읽어 apps/agent/core/schemas.py 와 apps/web/src/lib/types.ts 를 동기화하고 구현 체크리스트를 만든다. "노션 스펙 반영", "티켓 구현", "PRD 동기화" 요청 시 사용.
---

# notion-spec-sync

Notion 의 PRD·티켓을 **단일 진실 공급원(SSOT)** 으로 삼아 코드의 계약(타입·스키마)을 맞춘다.

## 사전 조건
- Notion MCP 연결됨 (`notion-search`, `notion-fetch` 도구 사용 가능). 없으면 중단하고 사용자에게 연결을 요청.
- 스펙 DB 위치: `.env` 의 `NOTION_SPEC_DB_ID` 또는 사용자가 준 URL. (`.env` 는 읽지 말고 사용자에게 ID 요청)

## 절차
1. **조회**: 사용자가 준 티켓 ID/제목으로 `notion-search` → `notion-fetch` 로 본문 전체 읽기.
2. **추출**: 아래 표로 정리해 사용자에게 먼저 보여준다 (코드 수정 전 확인).
   | 항목 | 내용 |
   |---|---|
   | 입출력 필드 | 추가/변경/삭제되는 필드명·타입·필수 여부 |
   | 영향 모듈 | web / agent-generators / agent-media / agent-publishers |
   | 담당 | 팀원 A·B·C (CLAUDE.md 의 소유권 표 참고) |
   | 완료 조건 | 티켓의 Acceptance Criteria |
3. **동기화** (계약 변경이 있을 때만):
   - `apps/agent/core/schemas.py` 수정 → 같은 커밋에서 `apps/web/src/lib/types.ts` 수정
   - `apps/agent/tests/test_api_contract.py` 에 새 필드 검증 추가
   - Web 의 Mock(`agentClient.ts` 의 mockGenerate) 도 새 필드를 채우도록 수정
4. **검증**: `harness-verify` 스킬 실행.
5. **보고**: 변경 파일, 스펙과 코드 간 **불일치/모호한 점**(추측으로 메우지 말고 목록화), 남은 TODO.

## 규칙
- 스펙에 없는 필드를 임의로 추가하지 않는다. 모호하면 구현하지 말고 질문 목록으로 돌려준다.
- 다른 팀원 소유 디렉토리를 건드려야 하면 PR 설명에 명시한다.
- Notion 페이지는 **읽기 전용**으로 취급한다. 상태 변경·코멘트 작성은 사용자가 요청할 때만.
