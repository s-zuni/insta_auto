import os, sys, json, random
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

if sys.platform == "win32":
    try: sys.stdout.reconfigure(encoding="utf-8"); sys.stderr.reconfigure(encoding="utf-8")
    except: pass

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.script_gen import ReelsScript, Scene, get_gemini_client

MBTI_TYPES = ["INTJ","INTP","ENTJ","ENTP","INFJ","INFP","ENFJ","ENFP","ISTJ","ISFJ","ESTJ","ESFJ","ISTP","ISFP","ESTP","ESFP"]
MBTI_KEYWORDS = {
    "INTJ":("전략가","냉철한 비전","독립적 완벽주의"),"INTP":("논리학자","사색과 분석","내향적 천재성"),
    "ENTJ":("통솔자","리더십 본능","목표 달성 집착"),"ENTP":("토론가","아이디어 폭발","변화 추구"),
    "INFJ":("옹호자","깊은 공감","이상주의적 직관"),"INFP":("중재자","섬세한 감수성","내면의 가치"),
    "ENFJ":("선도자","인간관계 마스터","타인 성장 지원"),"ENFP":("활동가","열정적 창의성","연결과 자유"),
    "ISTJ":("현실주의자","책임감과 원칙","묵묵한 신뢰"),"ISFJ":("수호자","따뜻한 헌신","세심한 배려"),
    "ESTJ":("경영자","체계와 효율","강한 실행력"),"ESFJ":("집정관","사회적 조화","타인 중심 돌봄"),
    "ISTP":("장인","현장 문제 해결","말보다 행동"),"ISFP":("모험가","감각적 자유","조용한 예술혼"),
    "ESTP":("사업가","순간 포착 실행","현실 적응력"),"ESFP":("연예인","에너지와 재미","삶을 축제로"),
}
FIVE_ELEMENTS = {
    "목(木)":{"color":"초록","symbol":"🌿","booster":"성장·추진력"},
    "화(火)":{"color":"빨강","symbol":"🔥","booster":"열정·인기"},
    "토(土)":{"color":"황색","symbol":"🌍","booster":"안정·포용"},
    "금(金)":{"color":"흰색","symbol":"⚡","booster":"결단·원칙"},
    "수(水)":{"color":"파랑","symbol":"💧","booster":"지혜·유연성"},
}

REELS_PERSONA = """[릴스 대본 작가 페르소나]
당신은 대한민국 MZ세대 여성(20~30대)에게 최적화된 숏폼 릴스 대본 전문 작가입니다.
초반 3초 후킹, 팩트 중심 날카로운 어조, 사주 명리학 + MBTI 심리 역동 융합,
MZ 언어, 행동 유도(저장/팔로우/댓글) CTA로 마무리. 전체 분량 30~50초(씬 4~6개).

[주제/구성 규칙 - 필수]
- '오늘의 운세'식 일일 운세 주제는 금지. 순위(랭킹)와 특성을 적극 활용한 주제로 작성합니다.
  (예: "슬프면 무조건 눈물 흘리는 MBTI 1위", "올해 남은 3개월 잘되는 사주 특성",
   "잘 어울리는 MBTI 궁합", "잘 어울리는 사주&MBTI 조합 1위")
- 제목(title)은 공백 포함 16자 이내로 짧고 굵게(화면에 큰 글씨로 2줄까지만 표시됨, 줄바꿈 금지).
- 톤은 재밌고 능청스럽게, 친구에게 수다 떨듯 리듬감 있게 작성합니다.

[마지막 씬 CTA 고정 규칙 - 필수]
- 영상의 맨 마지막 씬(마지막 scene)의 narration은 반드시 다음 멘트로 고정합니다:
  "프로필 링크에서 당신의 모든 운명을 확인하세요!"
- 인스타그램 캡션(instagram_caption) 본문 끝에도 반드시 다음 문구를 포함하세요:
  "👉 프로필 링크에서 당신의 모든 운명을 확인하세요!"

[narration 작성 규칙 - 필수]
- narration 필드에는 한자(漢字)를 절대 포함하지 마세요. 오직 순수 한글(및 필요시 숫자)만 사용합니다.
  (예: "토(土)" 대신 "토"만 사용 — TTS가 한글과 한자를 중복 발음하는 것을 방지하기 위함입니다.)"""

FIXED_SHORTFORM_CTA = "프로필 링크에서 당신의 모든 운명을 확인하세요!"
FIXED_CAPTION_CTA = "👉 프로필 링크에서 당신의 모든 운명을 확인하세요!"


DOMAIN_LABELS = {
    "SAJU": "사주", "SHINJEOM": "신점", "JAMIDOSU": "자미두수", "TAROT": "타로",
}


def build_series_prompt(series: str, context: dict) -> str:
    if series == "MBTI":
        mbti = context.get("mbti", "INFP")
        nick, t1, t2 = MBTI_KEYWORDS.get(mbti, ("","",""))
        base = f"{REELS_PERSONA}\n\n[MBTI 시리즈: {mbti} ({nick})]\n핵심: {t1}, {t2}\n후킹으로 시작 → 사주 오행/십신 진단 → MBTI 심리 교차 분석 → 솔루션 → CTA\n해시태그: #{mbti} #사주 #운세 #MBTI궁합 #병오년 #릴스"
    elif series == "DAILY":
        el = context.get("element", "목(木)")
        el_display = el.split("(")[0]  # 한자 표기는 모델 프롬프트에서 제외해 narration에 새어들어가는 것을 방지
        info = FIVE_ELEMENTS.get(el, {})
        base = f"{REELS_PERSONA}\n\n[오행 랭킹/특성 시리즈: {el_display}]\n색상: {info.get('color','')} | 기운: {info.get('booster','')}\n후킹 → 오행별 순위·특성 설명 → 실생활 팁 → CTA\n해시태그: #{el_display} #사주 #병오년 #릴스"
    elif series in DOMAIN_LABELS:
        label = DOMAIN_LABELS[series]
        topic = context.get("topic", f"{label} 특성 TOP 랭킹")
        base = f"{REELS_PERSONA}\n\n[{label} 시리즈]\n주제: {topic}\n후킹 → {label} 핵심 포인트 해석 → 현실 조언 → CTA\n해시태그: #{label} #운세 #병오년 #릴스"
    else:
        base = f"{REELS_PERSONA}\n\n주제: {context.get('topic','운세 릴스')}"

    # MBTI/DAILY 시리즈는 기본 틀만 있으므로, 구체적 주제(기획안/사용자 지정)가 있으면 반드시 반영
    custom_topic = str(context.get("topic", "")).strip()
    if custom_topic and series in ("MBTI", "DAILY", "ELEMENT"):
        base += f"\n\n[이번 영상의 구체적 주제 - 반드시 이 주제를 중심으로 작성]\n{custom_topic}"

    trend_hint = str(context.get("trend_hint", "")).strip()
    if trend_hint:
        base += f"\n\n[참고할 실시간 트렌드 헤드라인]\n\"{trend_hint}\"\n(이 트렌드를 자연스러운 후킹이나 사례로 녹여내되, 억지로 끼워 맞추지는 마세요.)"
    return base


def _enforce_shortform_cta(script: ReelsScript) -> ReelsScript:
    """숏폼(릴스, 숏츠)의 마지막 씬 내레이션과 캡션에 고정 CTA를 적용합니다."""
    if script.scenes:
        script.scenes[-1].narration = FIXED_SHORTFORM_CTA
        if script.scenes[-1].duration_estimate < 3:
            script.scenes[-1].duration_estimate = 4

    if FIXED_CAPTION_CTA not in script.instagram_caption:
        if "#" in script.instagram_caption:
            parts = script.instagram_caption.split("#", 1)
            script.instagram_caption = f"{parts[0].strip()}\n\n{FIXED_CAPTION_CTA}\n\n#{parts[1]}"
        else:
            script.instagram_caption = f"{script.instagram_caption.strip()}\n\n{FIXED_CAPTION_CTA}"

    # 오늘의 운세 관련 해시태그 정리
    script.instagram_caption = script.instagram_caption.replace("#오늘의운세", "#운세").replace("#오늘운세", "#운세")

    # 제목 줄바꿈 제거 및 길이 제한
    script.title = script.title.replace("\n", " ").strip()
    if len(script.title) > 16:
        script.title = script.title[:16].strip()
    return script


def generate_mbti_saju_script(series: str, context: Optional[dict] = None, model_name: Optional[str] = None) -> ReelsScript:
    from google.genai import types
    if context is None: context = {}
    if model_name is None: model_name = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
    system_prompt = build_series_prompt(series, context)
    user_prompt = f"""인스타그램 릴스 대본 JSON을 작성하세요.
시리즈: {series} | 컨텍스트: {json.dumps(context, ensure_ascii=False)}
JSON 스키마:
- title: 릴스 제목 (16자 이내, 줄바꿈 금지, 호기심 자극)
- hook: 초반 3초 후킹 대사
- scenes: 씬 리스트 4~6개 (scene_id, narration[한국어 구어체], visual_prompt[영문 가로 16:9 landscape cinematic no text], duration_estimate)
  * 마지막 씬 narration은 반드시 "{FIXED_SHORTFORM_CTA}" 로 작성
- instagram_caption: 이모지 포함 + "{FIXED_CAPTION_CTA}" 포함 + 해시태그 10개 이상"""
    try:
        client = get_gemini_client()
        response = client.models.generate_content(
            model=model_name, contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                response_schema=ReelsScript, temperature=0.7,
            ),
        )
        if hasattr(response, "parsed") and response.parsed is not None:
            script = response.parsed if isinstance(response.parsed, ReelsScript) else ReelsScript.model_validate(response.parsed)
            return _enforce_shortform_cta(script)
        raw = response.text.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        script = ReelsScript.model_validate(json.loads(raw))
        return _enforce_shortform_cta(script)
    except Exception as e:
        print(f"[WARNING] Gemini API 실패 ({e}). 폴백 대본 사용.")
        return _enforce_shortform_cta(_fallback(series, context))


def _fallback(series: str, context: dict) -> ReelsScript:
    mbti = context.get("mbti", "ENFP")
    nick, t1, t2 = MBTI_KEYWORDS.get(mbti, ("활동가","열정","자유"))
    return ReelsScript(
        title=f"{mbti} {nick} 사주 심층분석"[:16],
        hook=f"{mbti}라면 지금 이 영상 끝까지 보셔야 합니다.",
        scenes=[
            Scene(scene_id=1, narration=f"{mbti}라면 지금 이 영상 끝까지 보셔야 합니다.", duration_estimate=4,
                  visual_prompt=f"Horizontal 16:9 landscape ratio, mystical glowing {mbti} text on dark cosmic background, Korean fortune aesthetic, cinematic, no text"),
            Scene(scene_id=2, narration=f"{mbti}는 {t1} 성향이 강하죠. 사주로 보면 식상과 인성 기운이 교차하는 복잡한 구조를 가진 경우가 많습니다.", duration_estimate=6,
                  visual_prompt="Horizontal 16:9 landscape ratio, ancient Korean fortune book, candlelight, mystical symbols, cinematic, no text"),
            Scene(scene_id=3, narration=f"특히 {t2} 기질이 강한 시기에는 관성과의 충돌이 생길 수 있어요.", duration_estimate=6,
                  visual_prompt="Horizontal 16:9 landscape ratio, person silhouette at crossroads with glowing energy paths, Korean traditional aesthetic, no text"),
            Scene(scene_id=4, narration="지금 당장 이 행동 하나만 바꿔 보세요.", duration_estimate=5,
                  visual_prompt="Horizontal 16:9 landscape ratio, close-up hands writing in journal, glowing ink, warm bokeh, cinematic, no text"),
            Scene(scene_id=5, narration=FIXED_SHORTFORM_CTA, duration_estimate=4,
                  visual_prompt="Horizontal 16:9 landscape ratio, smartphone screen displaying profile link with mystical glow, clean modern aesthetic, no text"),
        ],
        instagram_caption=f"✨ {mbti} {nick} 사주×MBTI 분석\n\n{FIXED_CAPTION_CTA}\n\n#{mbti} #MBTI운세 #사주 #운세 #병오년운세 #MBTI분석 #사주궁합 #운명 #릴스"
    )