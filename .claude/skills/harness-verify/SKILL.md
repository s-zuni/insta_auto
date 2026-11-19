---
name: harness-verify
description: PR 올리기 전 타입체크·린트·빌드·테스트를 한 번에 검증하고, 결과를 Slack 에 붙여넣을 브리핑 메시지로 만든다. "PR 전 검증", "검증 돌려줘", "슬랙 브리핑" 요청 시 사용.
---

# harness-verify

## 실행 순서 (하나라도 실패하면 이후 단계는 계속하되 최종 결과는 FAIL)
```bash
# Web
cd apps/web && npm run typecheck && npm run lint && npm run build
# Agent (저장소 루트에서)
apps/agent/.venv/Scripts/python -m ruff check apps/agent      # macOS: .venv/bin/python
apps/agent/.venv/Scripts/python -m pytest -q
```
추가 점검:
1. **계약 동기화**: `git diff --name-only` 에 `core/schemas.py` 와 `lib/types.ts` 중 **한쪽만** 있으면 경고.
2. **시크릿**: `git diff` 에 `sk-`, `AIza`, `EAA`, `-----BEGIN`, `.env` 가 포함되면 FAIL.
3. **생성물**: `*.mp4`, `apps/agent/output/`, `.browser_profile/` 이 staged 인지 확인.
4. **소유권**: `git diff --name-only origin/main...HEAD` 의 파일을 CLAUDE.md §2 표(또는 `.claude/team.json` 의 `dirs`)와 대조해, 브랜치 담당(`feat/<A|B|C>-…`) 영역 밖 파일이 있으면 ⚠️ + "PR 설명에 이유 적고 해당 담당 리뷰어 지정" 안내. 공동 파일 수정이면 "단체방 공지" 안내.
5. **금지어**: 프롬프트(`generators/**`)나 Mock(`agentClient.ts`) 이 바뀌었으면 `pytest apps/agent/tests/test_copy_rules.py` 결과를 따로 표기.

## Slack 브리핑 메시지 (코드블록으로 출력, 직접 전송하지 않음)
```
*[insta_auto] PR 검증 결과: ✅ PASS | ❌ FAIL*
• 브랜치: <branch> / 담당: <A|B|C>
• Web: typecheck ✅ lint ✅ build ✅
• Agent: ruff ✅ pytest ✅ (N passed)
• 계약 동기화: ✅ | ⚠️ <사유>
• 소유권/금지어: ✅ | ⚠️ <영역 밖 파일 / 위반 표현>
• 변경 요약: <3줄 이내, 사용자 관점>
• 리뷰 요청 / 남은 이슈: <있으면>
```
- 사용자가 요청하면 `SLACK_WEBHOOK_URL` 이 아니라 **Slack MCP** 로 지정 채널에 전송 (webhook URL 은 읽지 않는다).
- 실패 시 원인 로그의 핵심 10줄 이내와 수정 제안을 함께 적는다.

## 설명 방식
팀원 대부분이 개발 초보다. 실패·경고는 **무엇이 / 왜 / 다음에 칠 명령어** 순서로 쉬운 말로 설명하고, 전문용어는 처음 한 번 괄호로 풀어 쓴다.
