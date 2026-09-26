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
MZ 언어, 행동 유도(저장/팔로우/댓글) CTA로 마무리. 전체 분량 30~50초(씬 4~6개)."""


def build_series_prompt(series: str, context: dict) -> str:
    if series == "MBTI":
        mbti = context.get("mbti", "INFP")
        nick, t1, t2 = MBTI_KEYWORDS.get(mbti, ("","",""))
        return f"{REELS_PERSONA}\n\n[MBTI 시리즈: {mbti} ({nick})]\n핵심: {t1}, {t2}\n후킹으로 시작 → 사주 오행/십신 진단 → MBTI 심리 교차 분석 → 솔루션 → CTA\n해시태그: #{mbti} #사주 #운세 #MBTI궁합 #오늘의운세 #병오년 #릴스"
    elif series == "DAILY":
        el = context.get("element", "목(木)")
        info = FIVE_ELEMENTS.get(el, {})
        return f"{REELS_PERSONA}\n\n[오늘의 오행 운세 시리즈: {el}]\n색상: {info.get('color','')} | 기운: {info.get('booster','')}\n후킹 → 오행 본질 설명 → 실생활 팁 → CTA\n해시태그: #{el.split('(')[0]} #오늘의운세 #사주 #병오년 #릴스"
    else:
        return f"{REELS_PERSONA}\n\n주제: {context.get('topic','운세 릴스')}"


def generate_mbti_saju_script(series: str, context: Optional[dict] = None, model_name: Optional[str] = None) -> ReelsScript:
    from google.genai import types
    if context is None: context = {}
    if model_name is None: model_name = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
    system_prompt = build_series_prompt(series, context)
    user_prompt = f"""인스타그램 릴스 대본 JSON을 작성하세요.
시리즈: {series} | 컨텍스트: {json.dumps(context, ensure_ascii=False)}
JSON 스키마:
- title: 릴스 제목 (호기심 자극)
- hook: 초반 3초 후킹 대사
- scenes: 씬 리스트 4~6개 (scene_id, narration[한국어 구어체], visual_prompt[영문 9:16 cinematic no text], duration_estimate)
- instagram_caption: 이모지 포함 + 해시태그 10개 이상"""
    try:
        client = get_gemini_client()
        response = client.models.generate_content(
            model=model_name, contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                response_schema=ReelsScript, temperature=0.8,
            ),
        )
        if hasattr(response, "parsed") and response.parsed is not None:
            if isinstance(response.parsed, ReelsScript): return response.parsed
            return ReelsScript.model_validate(response.parsed)
        raw = response.text.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        return ReelsScript.model_validate(json.loads(raw))
    except Exception as e:
        print(f"[WARNING] Gemini API 실패 ({e}). 폴백 대본 사용.")
        return _fallback(series, context)


def _fallback(series: str, context: dict) -> ReelsScript:
    mbti = context.get("mbti", "ENFP")
    nick, t1, t2 = MBTI_KEYWORDS.get(mbti, ("활동가","열정","자유"))
    return ReelsScript(
        title=f"{mbti} {nick}의 사주×MBTI 완전 분석",
        hook=f"{mbti}라면 지금 이 영상 끝까지 보셔야 합니다.",
        scenes=[
            Scene(scene_id=1, narration=f"{mbti}라면 지금 이 영상 끝까지 보셔야 합니다.", duration_estimate=4,
                  visual_prompt=f"Vertical 9:16 ratio, mystical glowing {mbti} text on dark cosmic background, Korean fortune aesthetic, cinematic, no text"),
            Scene(scene_id=2, narration=f"{mbti}는 {t1} 성향이 강하죠. 사주로 보면 식상과 인성 기운이 교차하는 복잡한 구조를 가진 경우가 많습니다.", duration_estimate=6,
                  visual_prompt="Vertical 9:16 ratio, ancient Korean fortune book, candlelight, mystical symbols, cinematic, no text"),
            Scene(scene_id=3, narration=f"특히 {t2} 기질이 강한 시기에는 관성과의 충돌이 생길 수 있어요.", duration_estimate=6,
                  visual_prompt="Vertical 9:16 ratio, person silhouette at crossroads with glowing energy paths, Korean traditional aesthetic, no text"),
            Scene(scene_id=4, narration="지금 당장 이 행동 하나만 바꿔 보세요.", duration_estimate=5,
                  visual_prompt="Vertical 9:16 ratio, close-up hands writing in journal, glowing ink, warm bokeh, cinematic, no text"),
            Scene(scene_id=5, narration="도움이 됐다면 저장하고 팔로우해 두세요.", duration_estimate=4,
                  visual_prompt="Vertical 9:16 ratio, glowing bookmark icon above smartphone, clean modern aesthetic, no text"),
        ],
        instagram_caption=f"✨ {mbti} {nick} 사주×MBTI 분석\n\n#{mbti} #MBTI운세 #사주 #운세 #오늘의운세 #병오년운세 #MBTI분석 #사주궁합 #운명 #릴스"
    )