---
name: start
description: 매일 아침 `/start` 로 실행하는 데일리 킥오프. git 최신 상태 확인 → 코드 점검 → Notion 오늘 할 일 조회 → 팀원별 Slack 메시지 전송까지 진행한다.
disable-model-invocation: true
argument-hint: "[auto]  (auto = 미리보기 확인 없이 Slack 바로 전송)"
---

# /start — 데일리 킥오프

실행 대상 설정은 `.claude/team.json` 에서 읽는다. 순서대로 진행하고, 단계가 실패해도 **다음 단계는 계속**하되 최종 보고에 실패를 명시한다.
**추측으로 빈칸을 채우지 않는다.** 확인하지 못한 항목은 "미확인"이라고 쓴다.

## 0. 설정 로드
- `.claude/team.json` 을 읽는다. 값이 `TODO` 이거나 비어 있으면(팀원 Slack ID, Notion DB 등) 해당 단계를 건너뛰지 말고
  사용자에게 **필요한 값만 짧게 질문**한다. 답을 받으면 `team.json` 에 저장해 다음부터 묻지 않는다.
- Slack/Notion MCP 가 미인증이면 그 단계의 `authenticate` 도구로 로그인 안내를 하고, 해당 단계만 "미실행"으로 표시한다.

## 1. Git 코드 확인 (읽기 전용)
```bash
git fetch --prune
git status -sb
git log --oneline --since="24 hours ago" origin/main
git log --oneline --since="24 hours ago" --all --author-date-order   # 브랜치별 어제 작업
```
- 현재 브랜치, `origin/main` 대비 ahead/behind, 작업 중 변경(미커밋) 여부를 요약.
- 어제 커밋을 `team.json` 의 `git_authors` 로 팀원에 매핑하고 **소유 디렉토리**(CLAUDE.md §2) 기준으로 정리.
- `gh` 가 있으면 열린 PR 목록·리뷰 대기를 함께 확인. 없으면 "PR 목록 미확인"으로 표기.
- **자동으로 pull/checkout/merge/reset 하지 않는다.** behind 이면 사용자에게 `git pull --ff-only` 를 제안만 한다.

## 2. 코드 점검
`harness-verify` 스킬의 검증 절차를 **현재 체크아웃 기준**으로 실행한다 (Web typecheck/lint/build, Agent ruff/pytest, 계약 동기화, 시크릿 점검).
- 실패 항목은 핵심 로그 10줄 이내 + 담당 팀원(소유 디렉토리 기준)을 붙인다.
- 작업 트리가 dirty 이거나 `main` 이 아니면 결과 앞에 그 사실을 적는다.

## 3. Notion 오늘 할 일 조회 (읽기 전용)
- `team.json` 의 `notion.tasks_database_url` 이 있으면 `notion-fetch` 로 DB 스키마를 확인하고 `notion-query-data-sources` 로 조회.
  없으면 `notion-search` 로 후보("오늘 할 일", "Tasks", "티켓")를 찾아 사용자에게 **어느 DB 인지 확인**받고 저장.
- 조회 조건: `담당자`(select: A/B/C/공동) = 팀원 키, 그리고 (상태 ∈ `active_statuses` 이거나 마감일 ≤ 오늘). `공동` 작업은 팀 전체 메시지에 넣는다. Notion 워크스페이스에 팀원이 멤버로 없어서 담당자는 People 이 아니라 select 다.
- 팀원별로 `제목 / 상태 / 마감 / 링크` 를 정리. 오늘 배정이 없으면 "배정된 작업 없음"으로 두고 지어내지 않는다.
- Notion 페이지는 **수정·코멘트하지 않는다.**

## 4. 팀원별 메시지 작성
팀원마다 한국어로 짧게 (Slack mrkdwn, 10줄 이내):
```
좋은 아침이에요 {이름}님 ☀️ ({날짜})
*오늘 할 일*
• {Notion 작업 제목} (마감 {날짜}) <{링크}|열기>
*참고*
• 어제 main 변경: {내 영역과 관련된 변경 1~2줄 / 없음}
• 검증 상태: {내 영역에서 실패한 점검 / 모두 통과}
막히는 부분 있으면 스레드로 남겨주세요!
```
- 내 영역과 무관한 실패·변경은 넣지 않는다. 과도한 이모지·압박 표현 금지.
- 전체 공유용 요약(어제 요약, 점검 결과, 오늘 목표)은 `team.json` 의 `slack.team_summary.channel_id`(팀 단체 그룹 DM)에 별도 1건. 개인별 할 일은 각자 DM 으로 따로 보낸다.

## 5. 전송
- **기본**: 위 메시지 전체를 표로 미리보기(수신자 · 채널 · 본문)로 보여주고 **"이대로 보낼까요?"** 로 확인받은 뒤 Slack MCP 로 전송한다. 수정 요청이 있으면 반영 후 다시 확인.
- **`/start auto`**: 확인 없이 전송.
- 전송 방식은 `team.json` 의 `slack.mode`: `dm` 이면 팀원 개인 DM(`slack_create_conversation` 으로 열기) + 그룹 DM(`team_summary`)에 요약 1건, `channel` 이면 공용 채널에서 멘션. 
- 오늘 이미 같은 내용을 보냈는지(채널 최근 메시지)를 확인하고, 이미 보냈다면 재전송 전에 사용자에게 묻는다.
- webhook URL·토큰은 읽거나 출력하지 않는다. Slack MCP 만 사용.

## 6. 사용자에게 최종 보고
```
📋 /start 결과 ({날짜})
• Git: {브랜치, ahead/behind, 어제 커밋 N개}
• 점검: ✅/❌ {실패 항목 요약}
• Notion: 팀원별 작업 {A n건 / B n건 / C n건}
• Slack: {전송 완료 N건 / 실패·미실행 사유}
• 오늘 주의할 점: {1~3줄}
```
