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
from pipeline.text_utils import sanitize_title

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

REELS_PERSONA = """[릴스 100만 바이럴 디렉터 페르소나]
당신은 대한민국 2030 여성 타겟 인스타그램 릴스 & 유튜브 숏츠 100만 뷰 바이럴 전문 디렉터입니다.
단순 정보 나열이나 지루한 설명은 시청자가 1초 만에 넘겨버리므로, 극단적 호기심과 '내 얘기다!' 하는 감정 몰입을 유발하는 구조로 기획합니다.
전체 분량 20~30초, 씬 8~10개. 전개는 초고속: 씬 1개 = 한 문장(공백 포함 22~38자, 길어도 48자 이내), 1.5~3초마다 새 정보/새 장면.
서론·부연·반복 금지, 접속사로 늘어지는 긴 문장 금지.

[1단계: 초반 1.5초 스크롤 정지 훅(Hook) - 씬 1 필수 규칙]
- 일반 대중 95%는 본인이 무슨 일간(을목·병화 등)인지 모른 채 피드를 넘깁니다.
- 따라서 주제가 [대중 확장형]일 때는 첫 문장(씬 1)에서 어려운 명리학 용어를 던지지 말고, 100% 누구나 즉시 대입할 수 있는 아래 5대 바이럴 포맷 중 하나로 시작하세요:
  1. 체크리스트형: "솔직히 여기서 세 개 이상 해당되면 사주에 도화살이 낀 사람입니다."
  2. 페이크아웃(통념 반박)형: "다 퍼주는 착한 사람일수록 손절할 때 제일 잔인한 진짜 이유."
  3. 카톡/일상 POV형: "썸 타는데 카톡 답장 일부러 늦게 하는 사람의 소름 돋는 속마음."
  4. 밸런스 게임(A vs B)형: "나만 바라보는 무토 남자 대 숨만 쉬어도 설레는 병화 남자."
  5. 대운 징조·미스터리형: "인생이 크게 풀리기 직전인 사람은 갑자기 이것부터 정리합니다."
- 주제가 [코어 핀셋형](예: "을목 여자 특징")일 때는 씬 1에서 대상을 직격 호명하고 결론을 숨겨("이거 모르면 평생 손해 봅니다") 시작하세요.
- 절대 금지: "오늘은 ~를 알아볼게요", "안녕하세요" 같은 설명형 인트로 절대 금지!

[2단계: 소름 돋는 일상 장면 3연타 & 사주 반전 해부 - 씬 2~6 규칙]
- 씬 2~4는 카톡 말투, 퇴근 후 침대, 월급날 소비, 연애 갈등 등 2030 한국인이 매일 겪는 하이퍼 리얼리즘 장면 3가지를 빠르게 던져 "헐 이거 완전 내 얘기잖아" 공감을 쌓습니다.
- 씬 5~6에서 반전을 줍니다: "사실 이게 성격 문제가 아니라 사주에 을목(또는 도화살/홍염살/식신/상관 등) 기운이 강해서 생기는 특징이거든요."
- 특징은 '좋은 점(매력/재능) 1 : 아픈 점(속앓이/상처) 2' 비율로 써서 위로와 저장 욕구를 동시에 폭발시킵니다.

[3단계: 클로징 반전 한 줄 & 알고리즘 3중 CTA - 필수]
- 본문 마지막 씬은 이 사주/MBTI가 운을 트이게 하는 구체적 행동 팁 한 줄로 끝냅니다.
- 그 뒤에 시스템(`cta.py`)이 자동으로 [친구 공유 유도 씬] + [댓글 '사주' 키워드 & 프로필 링크 안내 씬]을 붙입니다.

[narration & title 작성 규칙 - 절대 엄수]
- narration 필드에는 한자(漢字)를 절대 포함하지 마세요. 오직 순수 한글(및 필요시 숫자)만 사용합니다.
  (예: "토(土)" 대신 "토"만 사용 — TTS가 한글과 한자를 중복 발음하는 것을 방지하기 위함입니다.)
- 제목(title)도 한자 금지, 한글/영문/숫자만 사용 (화면 폰트에 한자 글리프가 없어 깨집니다).
- 제목(title)은 공백 포함 16자 이내로 짧고 강렬하게 (화면 상단 Y=265에 128px 큰 글씨로 2줄 표시)."""

FIXED_SHORTFORM_CTA = "댓글에 사주 남기거나 프로필 링크에서 내 사주와 엠비티아이 첫 분석을 무료로 확인해보세요!"
FIXED_CAPTION_CTA = "💬 댓글에 [사주] 남기거나\n👉 프로필 링크에서 내 사주 x MBTI 첫 분석을 무료로 확인하세요! (가입 필요)"


DOMAIN_LABELS = {
    "SAJU": "사주", "SHINJEOM": "신점", "JAMIDOSU": "자미두수", "TAROT": "타로",
}


def build_series_prompt(series: str, context: dict) -> str:
    if series == "MBTI":
        mbti = context.get("mbti", "INFP")
        nick, t1, t2 = MBTI_KEYWORDS.get(mbti, ("","",""))
        base = f"{REELS_PERSONA}\n\n[MBTI 시리즈: {mbti} ({nick})]\n핵심: {t1}, {t2}\n일상 공감 후킹으로 시작 → {mbti}의 연애·인간관계 속마음 해부 → 사주 오행/십성 교차 반전 → 현실 팁\n해시태그: #{mbti} #사주 #운세 #MBTI궁합 #병오년 #릴스"
    elif series == "DAILY":
        el = context.get("element", "목(木)")
        el_display = el.split("(")[0]  # 한자 표기는 모델 프롬프트에서 제외해 narration에 새어들어가는 것을 방지
        info = FIVE_ELEMENTS.get(el, {})
        base = f"{REELS_PERSONA}\n\n[오행 랭킹/특성 시리즈: {el_display}]\n색상: {info.get('color','')} | 기운: {info.get('booster','')}\n후킹 → 오행별 순위·특성 설명 → 실생활 팁\n해시태그: #{el_display} #사주 #병오년 #릴스"
    elif series in DOMAIN_LABELS:
        label = DOMAIN_LABELS[series]
        topic = context.get("topic", f"{label} 특성 TOP 랭킹")
        base = f"{REELS_PERSONA}\n\n[{label} 바이럴 시리즈]\n주제 및 기획 설계: {topic}\n초반 1.5초 후킹 → 일상 공감 장면 3연타 → {label} 명리학 핵심 반전 해석(장점 1 : 아픈 점 2) → 현실 솔루션\n해시태그: #{label} #운세 #병오년 #사주풀이 #릴스"
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


# pipeline.cta 임포트 실패 시에만 쓰는 폴백 (서비스에서 확인된 문구만 사용)
DYNAMIC_SHORTFORM_CTAS = [
    ("내 일간이 궁금하면 댓글에 사주 남기거나 프로필 링크에서 가입 없이 삼십 초 만에 무료로 확인해보세요!", "💬 댓글에 [사주] 남기거나\n👉 프로필 링크에서 가입 없이 30초 무료 체험, 내 일간부터 확인하세요!"),
]


def _enforce_shortform_cta(script: ReelsScript, series: str = "", topic: str = "") -> ReelsScript:
    """숏폼(릴스, 숏츠)의 초반 씬 media_type 지정 및 마지막 씬 내레이션·캡션에 고전환 3중 CTA를 적용합니다."""
    for idx, sc in enumerate(script.scenes):
        sc.media_type = "video" if idx < 2 else "image"

    # 영상마다 자연스럽게 순환하는 고전환 CTA 멘트 적용
    try:
        from pipeline.cta import apply_reel_cta
        # LLM이 쓴 마지막 씬(결론/반전)은 보존하고 그 뒤에 주제별 CTA를 붙인다
        chosen_short_cta, chosen_caption_cta = apply_reel_cta(script.scenes, script.instagram_caption, series, topic or script.title)
    except Exception:
        chosen_short_cta, chosen_caption_cta = random.choice(DYNAMIC_SHORTFORM_CTAS)
        if script.scenes:
            script.scenes[-1].narration = chosen_short_cta
            if script.scenes[-1].duration_estimate < 3:
                script.scenes[-1].duration_estimate = 4

    # 기존 일반 멘트가 있다면 고전환 멘트로 교체
    script.instagram_caption = script.instagram_caption.replace(FIXED_CAPTION_CTA, "").strip()
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
    script.title = sanitize_title(script.title.replace("\n", " "))
    if len(script.title) > 16:
        script.title = script.title[:16].strip()
    return script


def generate_mbti_saju_script(series: str, context: Optional[dict] = None, model_name: Optional[str] = None) -> ReelsScript:
    if context is None: context = {}
    system_prompt = build_series_prompt(series, context)
    user_prompt = f"""인스타그램 100만 바이럴 릴스 대본 JSON을 작성하세요.
시리즈: {series} | 컨텍스트: {json.dumps(context, ensure_ascii=False)}
JSON 스키마:
- title: 릴스 화면 상단 제목 (16자 이내, 호기심·결핍 자극, 한자 절대 금지)
- hook: 초반 2초 후킹 대사
- scenes: 씬 리스트 7~9개 (뒤에 시스템이 CTA 씬 2개를 자동 추가하여 총 9~11씬이 됨)
  * scene_id: 1부터 순차 증가
  * narration: 한국어 구어체, 한 씬 = 한 문장(공백 포함 22~38자, 한자 절대 금지)
  * visual_prompt: 영문, Vertical 9:16 세로 풀스크린 구도. 실제 한국인 2030 남녀가 일상(성수동 카페, 지하철 퇴근길, 자취방 침대, 사무실 데스크, 한강 야경 등)에서 스마트폰 세로 모드로 찍은 듯한 몰입감 있는 장면 묘사. 씬 1~2는 영상(video) 클립용으로 미세한 움직임(subtle movement, looking at phone, turning head, pouring coffee 등)과 표정/시선 디테일을 묘사하고, 매 씬 구도(인물 클로즈업, 옆모습, 감성 소품 컷, 뒷모습)를 다채롭게 작성. glowing/mystical/neon/cosmic/fantasy/일러스트/3D 금지. no text, no watermark.
  * duration_estimate: 2~4초
  * media_type: 씬 1~2는 "video", 씬 3 이후는 "image"
  * 마지막 씬 narration은 반전/핵심 조언 한 줄로 마무리 (프로필 링크/댓글 CTA 문장은 시스템이 뒤에 자동으로 붙이므로 직접 쓰지 말 것)
- instagram_caption: 공감 요약 + 이모지 + 인기 해시태그 10개 이상 (CTA 문구는 시스템이 자동 삽입)"""
    try:
        script = generate_json(system_prompt, user_prompt, ReelsScript, temperature=0.8, model_name=model_name)
        return _enforce_shortform_cta(script, series, str(context.get("topic", "")))
    except Exception as e:
        print(f"[WARNING] LLM 대본 생성 실패 ({e}). 폴백 대본 사용.")
        return _enforce_shortform_cta(_fallback(series, context), series, str(context.get("topic", "")))


def _fallback(series: str, context: dict) -> ReelsScript:
    mbti = context.get("mbti", "ENFP")
    nick, t1, t2 = MBTI_KEYWORDS.get(mbti, ("활동가","열정","자유"))
    return ReelsScript(
        title=f"겉은 밝은 {mbti} 진짜 속마음"[:16],
        hook=f"주변에 {mbti} 있는데 이것까지 알면 진짜 소름 돋습니다.",
        scenes=[
            Scene(scene_id=1, narration=f"솔직히 주변에 {mbti} 있는데 이 세 가지 모르면 평생 오해합니다.", duration_estimate=3, media_type="video",
                  visual_prompt="Horizontal 16:9 landscape ratio, candid smartphone video of a Korean woman in her late 20s sitting at a cafe window seat looking up from her phone with subtle movement, natural daylight, no text"),
            Scene(scene_id=2, narration=f"밖에서는 분위기 메이커인데 집 현관문 닫자마자 말 한마디 안 하고 기절해요.", duration_estimate=4, media_type="video",
                  visual_prompt="Horizontal 16:9 landscape ratio, candid shot of a Korean woman coming home at night and dropping her bag by the sofa, warm room lamp light, no text"),
            Scene(scene_id=3, narration=f"서운한 게 생겨도 웃으면서 넘기다가 혼자 새벽에 카톡창 보며 속앓이를 합니다.", duration_estimate=4, media_type="image",
                  visual_prompt="Horizontal 16:9 landscape ratio, close-up candid photo of hands holding a glowing smartphone in bed at late night, natural dim lighting, no text"),
            Scene(scene_id=4, narration=f"사실 이게 단순한 {mbti} 성향이 아니라 사주에 식신이나 을목 기운이 겹칠 때 나타나는 특징이거든요.", duration_estimate=4, media_type="image",
                  visual_prompt="Horizontal 16:9 landscape ratio, candid photo of a Korean woman looking out a subway window at dusk, natural light, no text"),
            Scene(scene_id=5, narration="이런 사람한테는 해결책보다 내 편이라는 확신 한마디가 운을 확 열어줍니다.", duration_estimate=4, media_type="image",
                  visual_prompt="Horizontal 16:9 landscape ratio, candid close-up of two cups of coffee on a wooden cafe table with warm sunlight, no text"),
        ],
        instagram_caption=f"✨ 겉은 밝은 {mbti} ({nick}), 사주로 본 진짜 속마음\n\n{FIXED_CAPTION_CTA}\n\n#{mbti} #MBTI운세 #사주 #운세 #병오년운세 #MBTI분석 #사주궁합 #도화살 #릴스"
    )
