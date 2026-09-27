---
name: reels-composer
description: insta_auto 저장소의 MBTI×사주 릴스/숏츠 파이프라인을 만들거나 수정할 때 따라야 할 디자인/엔지니어링 스펙(프레임 레이아웃, 폰트/한자 처리, 자막 줄바꿈, 씬 전환, 운세 크롤링 도메인). "릴스 레이아웃/자막/폰트/전환 고쳐줘", "영상이 미숙해 보인다", "크롤링 주제 바꿔줘" 같은 요청에 사용.
---

# Reels Composer 스펙

이 파일은 `insta_auto` 파이프라인이 생성하는 영상의 디자인/동작 규격을 정의합니다. 아래 수치와
규칙은 이번 프로젝트에서 여러 차례 시행착오(카드형 박스 디자인 거부, 한자 중복 발음 버그, 단어수
기반 자막 분할의 부자연스러움 등)를 거쳐 확정된 것이므로, 코드를 다시 설계하기 전에 먼저 읽으세요.

## 1. 프레임 레이아웃 (`pipeline/visual_gen.py :: compose_reels_frame`)

캔버스 1080x1920 (9:16). 세 구역으로 고정:

1. **상단 고정 제목 헤더** — 영상 전체에서 동일한 카테고리 태그 + 영상 주제 제목을 매 씬 동일하게
   표시 (씬마다 바뀌지 않음). 카드형 배경 박스/테두리는 사용하지 않는다 — 배경에 직접 텍스트를
   얹는 방식(레퍼런스: 실제 바이럴 릴스 계정들의 헤드라인 스타일)이 사용자가 원하는 디자인이며,
   둥근 사각형 카드 박스는 명시적으로 거부된 디자인이다.
   - 태그: `[ {category_tag} ]`, 30px, accent 색상(`#FFBB40` 부근), 배경/테두리 없음.
   - 제목: 56px bold, 흰색, 중앙 정렬, 최대 3줄. 줄바꿈은 반드시 `wrap_by_pixel_width()`
     (`pipeline/text_utils.py`)로 실측 픽셀 폭 기준 — `textwrap.wrap(width=N)` 같은 글자 수
     기준 줄바꿈은 한글에서 부정확하므로 사용 금지.
   - 헤더 높이는 제목 줄 수에 따라 동적으로 계산(`top_pad+tag_h+gap+line_h*lines+bottom_pad`),
     `max(380, min(h, 620))`로 클램프. 고정 높이로 되돌리지 말 것(1줄 제목과 3줄 제목이 같은
     여백을 가지면 어색해짐).
2. **중앙 16:9 비주얼** — 헤더 바로 아래 폭 1080 x 높이 608(=1080*9/16)로 배치. 위/아래 경계에
   3px accent 라인. 이미지 생성 엔진(나노바나나→FLUX→Imagen3)은 모두 16:9로 요청한다 — 9:16으로
   되돌리면 이 레이아웃이 깨진다.
3. **하단 자막 영역** — 이미지 아래 남은 공간은 깔끔한 다크 그라디언트(사진 블러 배경 아님)로
   채우고, 여기에 `composer.py`가 ASS 자막을 하드번인한다. `ass 스타일의 MarginV=340`이 이 영역
   중간쯤에 자막이 앉도록 튜닝되어 있음 — 헤더/이미지 치수를 바꾸면 이 값도 함께 재검토.

색상: 배경 그라디언트 `#111121` → `#08080d`(위→아래), accent `#FFBB40`.

## 2. 폰트 / 한자 처리

- 사용 폰트: `assets/fonts/NanumGothic-Bold.ttf` (제목/태그/자막 공통).
- **나레이션(narration)에는 한자를 절대 포함하지 않는다.** TTS 엔진이 같은 발음의 한글+한자를
  중복으로 읽는 버그가 있었음(`"토(土)사주"` → 음성 `"토토 사주"`). 방어는 2중:
  1. 프롬프트 지시: `script_gen.py` SYSTEM_PROMPT, `mbti_saju_content.py` REELS_PERSONA에
     한자 금지 문구가 있음.
  2. 코드 세이프넷: `pipeline/text_utils.sanitize_narration()`을 대본 생성 직후
     (`main.py` run_pipeline 1단계 이후) 모든 `scene.narration`에 적용.
  - 새 series/프롬프트를 추가해도 이 두 방어는 그대로 유지할 것. 반대로 제목(title)은 화면
    표시용이라 한자가 남아 있어도 무방(TTS로 읽히지 않음).

## 3. 자막 (`pipeline/composer.py`, `pipeline/text_utils.py`)

- 단어 개수 기반으로 대충 반으로 자르는 방식은 폐기됨. 현재 로직:
  1. `split_into_clauses()` — 문장부호(`. ! ? ,`)와 한국어 어미(`~요/~죠/~다` 뒤) 기준으로
     나레이션을 자연스러운 구(clause) 단위로 분할. 6자 미만 조각은 앞 구절에 병합.
  2. `wrap_by_pixel_width()` — 각 구절을 ASS 스타일과 동일한 폰트/크기(NanumGothic 62px)로
     실측하여 픽셀 폭(880px, `SUBTITLE_MAX_WIDTH`) 기준 줄바꿈.
  3. 한 자막 블록 최대 2줄(`max_lines`). 줄바꿈은 ASS `\N`.
  4. 각 블록의 재생 구간은 전체 씬 duration을 글자 수 비례로 배분 (`build_caption_chunks`).
- 자막 폭/폰트 크기를 바꾸면 `SUBTITLE_FONT_SIZE`/`SUBTITLE_MAX_WIDTH`(composer.py 상단 상수)와
  `compose_reels_frame`의 제목 폰트 크기가 서로 다른 값이어도 무방하지만, 측정용 폰트 객체는
  항상 ASS Style의 `Fontsize`와 같은 값으로 만들어야 실제 렌더와 줄바꿈 계산이 어긋나지 않는다.

## 4. 씬 전환 & 모션 (`pipeline/composer.py`)

- Ken Burns: 사인 이즈인아웃 곡선(`0.5-0.5*cos(PI*n/total_frames)`)으로 18% 줌 (홀수 씬 줌인,
  짝수 씬 줌아웃). 선형(`n/total_frames`) 방식으로 되돌리면 기계적으로 보임 — 이즈 곡선 유지.
- 씬 간 하드컷 대신 `TRANSITION_DUR = 0.28`초 디졸브(`xfade`+`acrossfade`)로 병합
  (`merge_clips_with_crossfade`). 크로스페이드가 실패하면(짧은 클립 등) 자동으로 기존 하드컷
  concat 방식(`_concat_copy_merge`)으로 안전하게 대체됨 — 이 폴백을 제거하지 말 것.

## 5. 운세 도메인 크롤링 (`pipeline/topic_crawler.py`)

- 크롤링은 **막연한 범용 핫이슈가 아니라 운세 콘텐츠 도메인으로 한정**한다. 이것은 사용자가
  명시적으로 요구한 제약이며, 이전 구현(구글 뉴스/트렌드 전체를 긁어와 억지로 MBTI/오행 틀에
  끼워 맞추는 방식)은 의도적으로 폐기되었다.
- `FORTUNE_DOMAINS`: `사주 운세`→`SAJU`, `MBTI 운세`→`MBTI`, `신점`→`SHINJEOM`,
  `자미두수`→`JAMIDOSU`, `타로 카드 운세`→`TAROT`. 검색어에 "운세/카드"를 덧붙인 것은 동음이의어
  오탐(드라마의 "~를 사주하다", 인명 "하카세 타로" 등)을 줄이기 위함 — 검색어를 다시 단순화하면
  오탐이 늘어난다.
- 도메인별 헤드라인이 하나도 안 잡히면 `FALLBACK_TOPICS`의 고정 시드로 대체.
- `get_crawled_reels_proposals()`가 서로 다른 2개 도메인을 뽑아 Gemini로 A안/B안을 만든다.
  MBTI가 선택되면 `mbti` 필드에 랜덤 MBTI 유형이 채워지고, 나머지 도메인은 `topic`/`trend_hint`
  필드로 전달된다.
- `main.py`의 `series` 선택지: `MBTI`, `DAILY`(오행, element 기반, 크롤러는 사용 안 함),
  `SAJU`/`SHINJEOM`/`JAMIDOSU`/`TAROT`(topic 기반), `LOVE`/`CAREER`(topic 기반, 레거시),
  `GENERAL`(크롤링/시리즈 프레임 없이 자유 주제). `mbti_saju_content.build_series_prompt()`의
  `context.get("trend_hint")`는 모든 series 공통으로 프롬프트 끝에 부착되어 실시간 화제를
  자연스럽게 반영하도록 유도한다.
- 텔레그램 봇(`telegram_bot.py :: generate_and_send_proposals`)은 이제 랜덤 MBTI/오행을 직접
  뽑지 않고 반드시 `topic_crawler.get_crawled_reels_proposals()`를 통해서만 기획안을 만든다.
  `state.db`의 `pending_proposals` 테이블에 `topic`/`trend_hint` 컬럼이 추가되어 있다(마이그레이션
  은 `init_db()`에서 `ALTER TABLE`로 자동 처리됨).

## 6. 품질 확인 시 주의

- `--mock-images`는 단색 그라디언트 플레이스홀더이므로 실제 비주얼 품질 판단에 쓰지 말 것.
- 합성 로직(레이아웃/자막/전환)만 반복 검증할 때는 이미 생성된
  `assets/audio/timing_info.json` + `assets/images/scene_*.jpg`를 재사용해
  `pipeline.composer.compose_reels_video()`를 직접 호출하면 Gemini/TTS/이미지 생성 API를
  다시 호출하지 않아도 되어 빠르다.
