---
name: reels-composer
description: insta_auto 저장소의 MBTI×사주 릴스/숏츠 파이프라인을 만들거나 수정할 때 따라야 할 디자인/엔지니어링 스펙(프레임 레이아웃, 폰트/한자 처리, 자막 줄바꿈, 씬 전환, 운세 크롤링 도메인). "릴스 레이아웃/자막/폰트/전환 고쳐줘", "영상이 미숙해 보인다", "크롤링 주제 바꿔줘" 같은 요청에 사용.
---

# Reels Composer 스펙

이 파일은 `insta_auto` 파이프라인이 생성하는 영상의 디자인/동작 규격을 정의합니다. 아래 수치와
규칙은 이번 프로젝트에서 여러 차례 시행착오(카드형 박스 디자인 거부, 한자 중복 발음 버그, 단어수
기반 자막 분할의 부자연스러움 등)를 거쳐 확정된 것이므로, 코드를 다시 설계하기 전에 먼저 읽으세요.

## 1. 프레임 레이아웃 (`pipeline/visual_gen.py :: compose_reels_frame`) — 2차 기획안 확정

캔버스 1080x1920 (9:16). 카드형 박스는 사용하지 않는다(거부된 디자인).

- **제목**: Pretendard Bold 128px, 가운데 정렬, 텍스트 상단 Y=265, 검정 외곽선(stroke 8). 최대 2줄
  (이미지 침범 방지) — 2줄을 넘으면 폰트를 8px씩 줄여(최소 88) 맞춘다. 줄바꿈은 `wrap_by_pixel_width()`.
  카테고리 태그/액센트 라인은 제거됨.
- **이미지**: 16:9(1080x608)를 캔버스 세로 정중앙(y=656)에 배치.
- **자막**: `composer.py` ASS 하드번인. 96px, 흰 글씨 + 검정 박스(BorderStyle=3), 상단 Y=1423
  (Alignment=8, MarginV=`SUBTITLE_Y`), 가운데 정렬. 단어 하이라이트 색은 쓰지 않음(흰색 고정).
  Inter는 한글 글리프가 없어 Inter 기반 한글 폰트인 Pretendard Bold로 대체.
- 배경: 다크 그라디언트 `#111121` → `#08080d`.

## 2. 폰트 / 한자 처리

- 사용 폰트: `assets/fonts/Pretendard-Bold.otf` (제목/태그/자막/커버/캐러셀 공통, 파일이 없으면 NanumGothic-Bold로 대체). ASS Fontname은 `Pretendard`.
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
  2. `wrap_by_pixel_width()` — 각 구절을 ASS 스타일과 동일한 폰트/크기(Pretendard 96px)로
     실측하여 픽셀 폭(900px, `SUBTITLE_MAX_WIDTH`) 기준 줄바꿈.
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

## 5. 주제 기획 (`pipeline/topic_planner.py`) — 크롤링 폐기

- `topic_crawler.py`는 삭제됨(타사 상품/뉴스가 주제로 유입). `get_planned_reels_proposals()`가 A/B안을 만든다.
- 승자 공식: "을목 여자 특징? 이거 모르면" (1일 만에 조회 1,300+, 타 콘텐츠 6배) = 일간(10)+성별 정체성 타겟 + 결론을 숨긴 궁금증 갭.
  씨앗은 (일간, 성별, 포맷) 로테이션(최근 게시와 겹치면 가중치 하락, 을목/갑목/병화/정화 가중). 사주 70% / MBTI 30%.
- `classify_custom_topic`(사용자 직접 입력 분류)은 planner로 이동. `main.py`의 series 선택지/`trend_hint` 필드는 호환용으로 유지(빈 값).
- 이미지: `visual_gen.REALISM_SUFFIX`(스마트폰 스냅·자연광·피부결) 사용, 대본 visual_prompt도 실제 한국인 일상 장면으로 작성.

## 6. 품질 확인 시 주의

- `--mock-images`는 단색 그라디언트 플레이스홀더이므로 실제 비주얼 품질 판단에 쓰지 말 것.
- 합성 로직(레이아웃/자막/전환)만 반복 검증할 때는 이미 생성된
  `assets/audio/timing_info.json` + `assets/images/scene_*.jpg`를 재사용해
  `pipeline.composer.compose_reels_video()`를 직접 호출하면 LLM/TTS/이미지 생성 API를
  다시 호출하지 않아도 되어 빠르다.

## 7. 단어 단위 자막 / BGM / 커버 / 캐러셀 (추가 스펙)

- **자막은 단어 단위 카라오케(ASS kf 태그)**: `text_utils.build_karaoke_blocks`가 TTS `word_timings`를 어절에
  `align_word_times`로 정렬한다(글자 누적 위치 기반, 실패 시 글자 수 비례). (현재는 Primary/Secondary 모두 흰색이라 색 변화 없음). 블록 분할 규칙(구 단위 + 실측 폭 + 최대 2줄)은 그대로.
  - TTS 타이밍: Edge-TTS는 `boundary="WordBoundary"` 필수(7.x 기본은 문장 단위), Google TTS는 단어별 SSML
    `<mark>` + v1beta1 time pointing으로 실측(실패 시 균등 분할 폴백).
  - **디졸브 보정**: 씬 전환 xfade/acrossfade가 타임라인을 (씬 수-1)*0.28초 줄이므로 씬 k의 자막은 `k*TRANSITION_DUR`만큼
    앞당긴다(`generate_subtitles(transition_shift=...)`). 하드컷 폴백이면 0.
- **BGM**: `pipeline/bgm.py`가 `assets/bgm/<mood>/`에서 시리즈별 트랙을 고르고(영상 제목 seed로 고정),
  `composer`의 최종 인코딩에서 sidechaincompress로 나레이션 구간에 자동 덕킹 후 amix. 실패하면 BGM 없이 재인코딩.
  볼륨 `BGM_VOLUME`(기본 0.18). 음원이 없으면 BGM 생략.
- **커버**: `pipeline/cover.py`가 합성 전 16:9 원본(`scene_01_raw.jpg`, `generate_scene_images`가 보존)으로 1080x1920 커버를
  만든다. 제목은 프로필 그리드 3:4 크롭 안전 영역(y 240~1680) 안에 배치. Cloudinary에 올려 Reels API `cover_url`로 전달.
  `compose_reels_frame()` 레이아웃과는 별개.
- **이미지 비율**: 릴스 visual_prompt는 반드시 16:9 가로(landscape). 세로 구도를 요청하지 말 것.
- **캐러셀**: `carousel_gen.py`(대본) + `carousel_composer.py`(1080x1350 렌더, 릴스용 compose_reels_frame과 별개) +
  `insta_publisher.publish_carousel_to_instagram`. 호스팅은 Cloudinary 전용(`media_host.py`).
- **Insights 루프**: `pipeline/insights.py`가 게시물 메타를 `state.db`(published_posts)에 기록하고 24h/72h/7d 성과를
  수집. 성과 상위 게시물은 기획안/캐러셀 프롬프트의 '참고 예시'로만 쓰이며(도메인 선택은 계속 무작위),
  집계 게시물이 `INSIGHTS_MIN_POSTS`(기본 5) 미만이면 예시를 쓰지 않는다.
- **사용자 지정 주제**: 텔레그램 `/topic 주제` 또는 기획안 메시지의 '직접 주제 입력' 버튼 →
  `topic_planner.classify_custom_topic`이 MBTI/TAROT/SHINJEOM/JAMIDOSU/SAJU로 분류(운세 도메인 제약 유지).

## 8. 주제 / 나레이션 톤 (2차 기획안)

- '오늘의 운세'식 일일 주제 금지. 순위·특성 중심(예: "슬프면 눈물 흘리는 MBTI 1위", "잘 어울리는 사주&MBTI 조합 1위").
  프롬프트: `mbti_saju_content.REELS_PERSONA`, `topic_planner.get_planned_reels_proposals`. 제목은 16자 이내.
- TTS: `tts_engine.EDGE_VOICE_PRESETS`/`GOOGLE_VOICE_PRESETS`에서 영상마다 남/여+톤(rate/pitch) 랜덤 선택.
  `TTS_VOICE_NAME` 환경변수를 지정하면 고정.

## 9. 캐러셀 표지 (Figma MJ_1, node 292:180 — 확정)

`carousel_composer.render_cover`: 1080x1350 풀블리드 이미지(16:9 → 4:5 중앙 크롭) + 위→아래 검정 그라디언트(알파 0→100%).
우상단 슬로건 `MBTIJU: MBTI와 사주가 만나다.`(Black 26, 우측 x=1023, 중심 y=103), 브랜드 `MBTIJU`(Black 48, x=74, 중심 y=829),
헤드라인(SemiBold 68, x=60, top 850, 폭 996, 줄 높이 150, 최대 3줄, 넘으면 비례 축소). 자간은 모두 폰트 크기의 -5%(PIL은 글자 단위로 직접 그림).
폰트: `assets/fonts/Pretendard-{Black,SemiBold}.otf`. 본문 슬라이드(`render_content`)는 별개.
