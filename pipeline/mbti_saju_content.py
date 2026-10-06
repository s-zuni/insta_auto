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

from pipeline.script_gen import ReelsScript, Scene, generate_json

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

REELS_PERSONA = """[릴스 바이럴 디렉터 페르소나]
당신은 대한민국 2030 여성 타겟 인스타그램 릴스 & 유튜브 숏츠 100만 뷰 바이럴 전문 디렉터입니다.
단순 정보 나열은 시청자가 1초 만에 넘겨버리므로, 극단적 호기심과 감정 몰입을 유발하는 구조로 기획합니다.
전체 분량 30~45초 (씬 4~6개).

[1단계: 초반 1.5초 훅(Hook) 작성 공식 - 씬 1 필수 규칙]
- 첫 문장(씬 1 narration)은 무조건 아래 3대 바이럴 공식 중 하나를 적용해 즉각적인 스와이프를 차단하세요:
  1. 결핍·손실 회피형: "이거 모르면 2026년 하반기 땅을 치고 후회합니다", "절대 돈 빌려주면 안 되는 MBTI 사주 조합 1위"
  2. 극단적 반전·공감형: "겉은 천사인데 속은 멘탈 박살난 MBTI 특징", "남들은 완벽해 보이지만 속은 곪아 터진 이유"
  3. 경고·타겟 특정형: "주변에 이 MBTI 있으면 무조건 조심하세요", "올해 대운 들어오기 직전 나타나는 소름 돋는 징조"
- 절대 금지: "오늘은 ~를 알아볼게요", "안녕하세요" 같은 지루한 설명형 인트로 절대 금지!

[2단계: 본문 구성 및 인터랙션 트리거 - 씬 2~4 규칙]
- 팩트 폭격 + 사주 명리학/MBTI 심리 분석을 빠르게 교차 전달 (~해요, ~거든요, ~랍니다 식의 리듬감 있는 말투).
- 댓글·공유 유도 떡밥을 본문 중간에 자연스럽게 삽입 (예: "주변에 이런 친구 꼭 있죠?", "공감된다면 댓글로 남겨주세요").

[3단계: 클로징 고전환 CTA 규칙 - 필수]
- 영상의 맨 마지막 씬(마지막 scene)의 narration은 단순히 "운명을 확인하세요" 대신, 구체적인 혜택과 결핍을 자극하는 고전환 멘트를 작성합니다:
  (기본 템플릿: "내 사주 오행과 MBTI 상세 분석표는 프로필 링크에서 바로 확인해보세요!" 또는 "나머지 순위와 내 대운 확인은 프로필 링크에 남겨뒀어요!")
- 인스타그램 캡션(instagram_caption) 본문 끝에도 반드시 다음 문구를 포함하세요:
  "👉 프로필 링크에서 내 사주와 MBTI 상세 분석표를 확인하세요!"

[narration 작성 규칙 - 절대 엄수]
- narration 필드에는 한자(漢字)를 절대 포함하지 마세요. 오직 순수 한글(및 필요시 숫자)만 사용합니다.
  (예: "토(土)" 대신 "토"만 사용 — TTS가 한글과 한자를 중복 발음하는 것을 방지하기 위함입니다.)
- 제목(title)은 공백 포함 16자 이내로 짧고 강렬하게 (화면에 큰 글씨로 2줄 표시)."""

FIXED_SHORTFORM_CTA = "내 사주와 MBTI 상세 분석표는 프로필 링크에서 바로 확인해보세요!"
FIXED_CAPTION_CTA = "👉 프로필 링크에서 내 사주와 MBTI 상세 분석표를 확인하세요!"



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


DYNAMIC_SHORTFORM_CTAS = [
    ("내 사주와 MBTI 상세 분석표는 프로필 링크에서 바로 확인해보세요!", "👉 프로필 링크에서 내 사주와 MBTI 상세 분석표를 확인하세요!"),
    ("나머지 순위와 내 대운 확인은 프로필 링크에 남겨뒀어요!", "👉 프로필 링크에서 나머지 순위와 내 대운을 무료로 확인하세요!"),
    ("더 자세한 내 사주 오행 진단은 프로필 링크에서 1초 만에 확인하세요!", "👉 프로필 링크에서 내 사주 오행 무료 진단표를 확인하세요!"),
]


def _enforce_shortform_cta(script: ReelsScript) -> ReelsScript:
    """숏폼(릴스, 숏츠)의 마지막 씬 내레이션과 캡션에 고전환 CTA를 적용합니다."""
    # 영상마다 자연스럽게 순환하는 고전환 CTA 멘트 적용
    chosen_short_cta, chosen_caption_cta = random.choice(DYNAMIC_SHORTFORM_CTAS)

    if script.scenes:
        script.scenes[-1].narration = chosen_short_cta
        if script.scenes[-1].duration_estimate < 3:
            script.scenes[-1].duration_estimate = 4

    # 기존 일반 멘트가 있다면 고전환 멘트로 교체
    old_cta_pattern = "프로필 링크에서 당신의 모든 운명을 확인하세요!"
    if old_cta_pattern in script.instagram_caption:
        script.instagram_caption = script.instagram_caption.replace(
            f"👉 {old_cta_pattern}", chosen_caption_cta
        ).replace(old_cta_pattern, chosen_caption_cta)
    elif chosen_caption_cta not in script.instagram_caption:
        if "#" in script.instagram_caption:
            parts = script.instagram_caption.split("#", 1)
            script.instagram_caption = f"{parts[0].strip()}\n\n{chosen_caption_cta}\n\n#{parts[1]}"
        else:
            script.instagram_caption = f"{script.instagram_caption.strip()}\n\n{chosen_caption_cta}"


    # 오늘의 운세 관련 해시태그 정리
    script.instagram_caption = script.instagram_caption.replace("#오늘의운세", "#운세").replace("#오늘운세", "#운세")

    # 제목 줄바꿈 제거 및 길이 제한
    script.title = script.title.replace("\n", " ").strip()
    if len(script.title) > 16:
        script.title = script.title[:16].strip()
    return script


def generate_mbti_saju_script(series: str, context: Optional[dict] = None, model_name: Optional[str] = None) -> ReelsScript:
    if context is None: context = {}
    system_prompt = build_series_prompt(series, context)
    user_prompt = f"""인스타그램 릴스 대본 JSON을 작성하세요.
시리즈: {series} | 컨텍스트: {json.dumps(context, ensure_ascii=False)}
JSON 스키마:
- title: 릴스 제목 (16자 이내, 호기심 자극)
- hook: 초반 3초 후킹 대사
- scenes: 씬 리스트 4~6개 (scene_id, narration[한국어 구어체], visual_prompt[영문 가로 16:9 landscape cinematic no text], duration_estimate)
  * 마지막 씬 narration은 반드시 "{FIXED_SHORTFORM_CTA}" 로 작성
- instagram_caption: 이모지 포함 + "{FIXED_CAPTION_CTA}" 포함 + 해시태그 10개 이상"""
    try:
        script = generate_json(system_prompt, user_prompt, ReelsScript, temperature=0.8, model_name=model_name)
        return _enforce_shortform_cta(script)
    except Exception as e:
        print(f"[WARNING] OpenAI API 실패 ({e}). 폴백 대본 사용.")
        return _enforce_shortform_cta(_fallback(series, context))


def _fallback(series: str, context: dict) -> ReelsScript:
    mbti = context.get("mbti", "ENFP")
    nick, t1, t2 = MBTI_KEYWORDS.get(mbti, ("활동가","열정","자유"))
    return ReelsScript(
        title=f"{mbti} {nick}의 사주 심층분석"[:16],
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