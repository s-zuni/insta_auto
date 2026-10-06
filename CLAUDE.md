# CLAUDE.md

MBTI×사주 인스타그램 릴스/유튜브 숏츠 자동 생성 파이프라인. 설치/실행 방법은 `README.md`,
텔레그램 봇 아키텍처 히스토리는 `AUTOMATION_PLAN.md` 참고.

## 이 저장소에서 작업할 때 반드시 먼저 로드할 스킬

**릴스 영상의 레이아웃/폰트/자막/전환/크롤링 중 하나라도 건드리는 작업이면, 코드를 보기 전에
`.claude/skills/reels-composer/SKILL.md`를 먼저 읽으세요.** 그 문서가 이 프로젝트의 디자인 스펙
(캔버스 치수, 색상, 폰트 규칙, 자막 줄바꿈 로직, 트랜지션 파라미터, 운세 크롤링 도메인 목록)의
단일 소스입니다. 여기서 새로 추측하거나 재설계하지 마세요.

## 파이프라인 한눈에 보기

```
main.py run_pipeline()
  1. script_gen.py / mbti_saju_content.py  → LLM 대본(JSON, ReelsScript; Gemini 무료 티어 우선, 실패 시 OpenAI gpt-4o-mini 폴백 — script_gen.generate_json)
  2. text_utils.sanitize_narration()        → 나레이션 한자 제거 (TTS 중복 발음 방지)
  3. tts_engine.py                          → TTS 음성 + 씬별 word_timings
  4. visual_gen.py                          → 16:9 이미지 생성 + compose_reels_frame()으로
                                               1080x1920 릴스 프레임(상단 고정 제목 헤더 +
                                               중앙 16:9 비주얼) 합성
  5. composer.py                            → Ken Burns + 씬간 디졸브 전환 + ASS 자막 하드번인
  6. gdrive_uploader / insta_publisher / youtube_publisher → 배포
```

텔레그램 봇(`telegram_bot.py`)은 `pipeline/topic_crawler.py`로 사주/MBTI/신점/자미두수/타로
도메인의 실시간 뉴스를 크롤링해 기획안 2개를 만들고, 버튼 클릭 시 위 파이프라인을 그대로 호출합니다.

## 절대 어기면 안 되는 규칙 (이번 세션에서 확정된 결정)

- **나레이션에 한자 금지.** `narration` 필드는 TTS로 읽히므로 한자가 섞이면 한글+한자가 중복
  발음됩니다(예: "토(土)" → "토토"). 프롬프트 지시(`script_gen.py`, `mbti_saju_content.py`)와
  `text_utils.sanitize_narration()` 2중 방어가 이미 걸려 있으니, 새 series/프롬프트를 추가할 때도
  이 규칙을 유지하세요. 제목(title)은 화면에만 표시되고 읽히지 않으므로 한자 표기가 남아 있어도 무방.
- **크롤링은 운세 도메인으로 한정.** `topic_crawler.py`의 `FORTUNE_DOMAINS`(사주/MBTI/신점/자미두수/
  타로)만 검색합니다. 범용 핫이슈(정치/연예/스포츠)를 다시 끌어오는 방향으로 되돌리지 마세요 —
  사용자가 명시적으로 원치 않는다고 확인한 방식입니다.
- **자막은 문장부호 기준 절 단위 + 실측 픽셀 폭 래핑.** 단어 개수로 대충 반으로 자르는 방식(예전
  구현)으로 되돌리지 마세요. `composer.py`의 `build_caption_chunks`(`text_utils.py`)가 이를 담당.
- **레이아웃 변경은 `compose_reels_frame()` 하나만 수정.** 카드형 박스(둥근 사각형 배경)는 사용자가
  "구려 보인다"고 명시적으로 거부한 디자인입니다. 재도입하지 마세요.

## 테스트 팁

- LLM/TTS/이미지 생성을 다시 호출하지 않고 합성 로직만 빠르게 반복 검증하려면
  `assets/audio/timing_info.json`과 `assets/images/scene_*.jpg`가 이미 있는 상태에서
  `pipeline.composer.compose_reels_video()`를 직접 호출하세요 (스크립트/TTS/이미지 재생성 생략).
- `--mock-images`는 단색 그라디언트 플레이스홀더를 만듭니다. 실제 비주얼 품질을 판단할 때는
  반드시 `--mock-images` 없이 돌린 결과로 확인하세요 — 목업 결과만 보고 "화질이 별로다"라고
  판단하면 잘못된 진단입니다.
