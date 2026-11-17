---
name: publisher-tester
description: 4대 플랫폼(인스타 릴스/유튜브 쇼츠/쓰레드/네이버 블로그) 업로더를 Dry-run 으로 점검하고 네이버 에디터 셀렉터 깨짐을 진단한다. "발행 테스트", "dry-run", "셀렉터 점검", "업로더 확인" 요청 시 사용.
---

# publisher-tester

대상: `apps/agent/publishers/*.py`. **실제 발행은 절대 자동으로 하지 않는다** (사람이 UI에서 직접).

## 1. Dry-run 계약 점검 (항상 먼저)
```bash
apps/agent/.venv/Scripts/python -m pytest apps/agent/tests -q      # Windows
# macOS: apps/agent/.venv/bin/python -m pytest apps/agent/tests -q
```
각 채널이 `dry_run` 또는 **명확한 한국어 실패 사유**를 돌려주는지 확인. 채널별 검증 항목:
| 채널 | 검증 |
|---|---|
| threads | 글당 ≤500자, 키 설정 여부 |
| instagram | 영상 파일 존재, 캡션 ≤2200자, `IG_USER_ID/IG_ACCESS_TOKEN` |
| youtube | 영상 존재, 길이 ≤60초, `#Shorts` 포함, 공개범위(기본 private) |
| naver_blog | 제목·본문(≥300자), `NAVER_BLOG_ID`, 로그인 세션 폴더 존재 |

## 2. 네이버 셀렉터 점검 (UI가 바뀌었을 때)
1. 사용자에게 `python -m apps.agent.publishers.naver_blog login` 으로 로그인 세션이 있는지 확인.
2. Playwright 로 **글쓰기 화면까지만** 열고(발행 버튼 클릭 금지) `naver_blog.SELECTORS` 의 각 셀렉터에 대해 `locator.count()` 를 출력:
   `OK(≥1) / MISSING(0)`.
3. MISSING 이 있으면 페이지의 해당 영역 DOM 을 확인해 대체 셀렉터 후보 2~3개를 제안하고, **텍스트·aria-label 기반**(클래스 해시 의존 최소화) 셀렉터를 우선한다.
4. 수정은 `SELECTORS` dict 한 곳에서만 한다. 수정 후 다시 `count()` 로 확인.

## 3. 실계정 테스트 (사람이 승인했을 때만)
- 인스타: 테스트 계정, 유튜브: `YT_PRIVACY=private`, 쓰레드: 테스트 계정, 네이버: 비공개 발행 옵션으로.
- 토큰/세션 값은 출력·로그·커밋에 절대 포함하지 않는다.

## 보고 형식
채널별 한 줄 표(`dry_run OK / 실패 사유 / 셀렉터 MISSING 목록`) + 다음 조치. 확인하지 못한 항목은 "미검증"이라고 명시한다.
