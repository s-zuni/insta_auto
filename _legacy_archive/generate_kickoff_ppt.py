import sys
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE

def create_deck(output_path="team_project_kickoff.pptx"):
    prs = Presentation()
    # 16:9 Widescreen
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]

    # Color Palette
    COLOR_PRIMARY = RGBColor(30, 41, 59)     # Slate 800 (Deep Navy)
    COLOR_ACCENT = RGBColor(99, 102, 241)    # Indigo 500 (Vibrant Accent)
    COLOR_SECONDARY = RGBColor(79, 70, 229)  # Indigo 600
    COLOR_HIGHLIGHT = RGBColor(236, 72, 153) # Pink/Rose
    COLOR_BG_LIGHT = RGBColor(248, 250, 252) # Slate 50
    COLOR_CARD = RGBColor(255, 255, 255)     # White
    COLOR_TEXT_DARK = RGBColor(15, 23, 42)   # Slate 900
    COLOR_TEXT_MUTED = RGBColor(100, 116, 139) # Slate 500
    COLOR_BORDER = RGBColor(226, 232, 240)   # Slate 200

    def add_header(slide, title_text, category_text="AI SERVICE TEAM PROJECT"):
        # Category Tracker
        cat_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.4), Inches(10), Inches(0.4))
        tf_cat = cat_box.text_frame
        tf_cat.word_wrap = True
        p_cat = tf_cat.paragraphs[0]
        p_cat.text = category_text.upper()
        p_cat.font.size = Pt(11)
        p_cat.font.bold = True
        p_cat.font.color.rgb = COLOR_ACCENT

        # Slide Title
        t_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.7), Inches(11), Inches(0.8))
        tf_t = t_box.text_frame
        tf_t.word_wrap = True
        p_t = tf_t.paragraphs[0]
        p_t.text = title_text
        p_t.font.size = Pt(24)
        p_t.font.bold = True
        p_t.font.color.rgb = COLOR_TEXT_DARK

    def add_card(slide, left, top, width, height, bg_color=COLOR_CARD, border_color=COLOR_BORDER):
        card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
        card.fill.solid()
        card.fill.fore_color.rgb = bg_color
        card.line.color.rgb = border_color
        card.line.width = Pt(1.5)
        return card

    # ==========================================
    # SLIDE 1: Cover Slide
    # ==========================================
    s1 = prs.slides.add_slide(blank_layout)
    bg1 = s1.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
    bg1.fill.solid()
    bg1.fill.fore_color.rgb = COLOR_PRIMARY
    bg1.line.fill.background()

    # Title & Subtitle box
    tbox = s1.shapes.add_textbox(Inches(1.2), Inches(2.0), Inches(11), Inches(3.2))
    tf = tbox.text_frame
    tf.word_wrap = True

    p0 = tf.paragraphs[0]
    p0.text = "AI SERVICE TEAM PROJECT KICK-OFF"
    p0.font.size = Pt(14)
    p0.font.bold = True
    p0.font.color.rgb = RGBColor(165, 180, 252) # Indigo 200
    p0.space_after = Pt(14)

    p1 = tf.add_paragraph()
    p1.text = "AI 크로스 플랫폼 마케팅 자동화 파이프라인"
    p1.font.size = Pt(36)
    p1.font.bold = True
    p1.font.color.rgb = RGBColor(255, 255, 255)
    p1.space_after = Pt(10)

    p2 = tf.add_paragraph()
    p2.text = "인스타그램 릴스 & 유튜브 숏츠부터 네이버 블로그까지, 하나의 기획으로 동시 확장하기"
    p2.font.size = Pt(18)
    p2.font.color.rgb = RGBColor(203, 213, 225) # Slate 300
    p2.space_after = Pt(30)

    p3 = tf.add_paragraph()
    p3.text = "팀 구성: 총 4명 (릴스/숏츠 그로스 2명 + 네이버 블로그 자동화 2명) | 4주 스프린트"
    p3.font.size = Pt(13)
    p3.font.color.rgb = RGBColor(148, 163, 184)

    # ==========================================
    # SLIDE 2: Background & Vision
    # ==========================================
    s2 = prs.slides.add_slide(blank_layout)
    add_header(s2, "프로젝트 배경 및 목표: 왜 이 프로젝트인가?", "PROJECT BACKGROUND & VISION")

    col_w = Inches(3.6)
    top_pos = Inches(1.8)
    card_h = Inches(4.8)

    cards_data = [
        ("01. 백지에서 시작하지 않는 프로젝트", 
         "이미 핵심 파이프라인(LLM 기획 ➔ TTS 음성 ➔ 비주얼 생성 ➔ 영상 합성 ➔ 자동 배포)이 완성되어 있습니다.\n\n개발 환경 세팅에 진 빠지지 않고, 실전 기능 개선과 확장에 즉시 몰입할 수 있습니다.",
         COLOR_ACCENT),
        ("02. 확실한 AI 포트폴리오 확보", 
         "단순한 튜토리얼 실습이 아닌, 실제 운영되는 인스타그램 계정과 네이버 블로그에 매일 콘텐츠가 발행됩니다.\n\n'AI 파이프라인 구축 + 실제 사용자 지표(조회수, 저장수, 검색 유입)'를 증명하는 포트폴리오를 완성합니다.",
         COLOR_SECONDARY),
        ("03. 원소스 멀티유즈 (One-Source)", 
         "숏폼 영상(릴스/숏츠)과 롱폼 검색형 콘텐츠(네이버 블로그)를 한 번의 기획으로 동시 발행합니다.\n\nSNS 알고리즘 유입과 검색 포털 유입을 동시에 잡는 강력한 크로스 마케팅 구조를 구현합니다.",
         COLOR_HIGHLIGHT),
    ]

    for idx, (title, desc, accent) in enumerate(cards_data):
        left_pos = Inches(0.8 + idx * 4.0)
        add_card(s2, left_pos, top_pos, col_w, card_h)

        # Header tag
        tag = s2.shapes.add_shape(MSO_SHAPE.RECTANGLE, left_pos, top_pos, col_w, Inches(0.7))
        tag.fill.solid()
        tag.fill.fore_color.rgb = accent
        tag.line.fill.background()
        tf_tag = tag.text_frame
        p_tag = tf_tag.paragraphs[0]
        p_tag.text = title
        p_tag.font.size = Pt(13)
        p_tag.font.bold = True
        p_tag.font.color.rgb = RGBColor(255, 255, 255)
        p_tag.alignment = PP_ALIGN.CENTER

        # Body
        body = s2.shapes.add_textbox(left_pos + Inches(0.3), top_pos + Inches(0.9), col_w - Inches(0.6), card_h - Inches(1.1))
        tf_body = body.text_frame
        tf_body.word_wrap = True
        p_b = tf_body.paragraphs[0]
        p_b.text = desc
        p_b.font.size = Pt(14)
        p_b.font.color.rgb = COLOR_TEXT_DARK

    # ==========================================
    # SLIDE 3: Architecture (One-Source Multi-Use)
    # ==========================================
    s3 = prs.slides.add_slide(blank_layout)
    add_header(s3, "시스템 아키텍처: 하나의 기획으로 두 채널을 장악하는 구조", "SYSTEM ARCHITECTURE")

    # Core Source Card (Left)
    add_card(s3, Inches(0.8), Inches(1.8), Inches(4.5), Inches(4.8), bg_color=RGBColor(241, 245, 249))
    t1 = s3.shapes.add_textbox(Inches(1.1), Inches(2.0), Inches(4.0), Inches(4.3))
    tf1 = t1.text_frame
    tf1.word_wrap = True
    p1 = tf1.paragraphs[0]
    p1.text = "🎯 CORE PIPELINE (공통 소스)"
    p1.font.size = Pt(16)
    p1.font.bold = True
    p1.font.color.rgb = COLOR_PRIMARY
    p1.space_after = Pt(14)

    steps = [
        "1. 주제 기획 (topic_planner.py)\n   • 타겟 페르소나 및 후킹 키워드 선정",
        "2. 대본 기획 (script_gen.py)\n   • Gemini 무료 티어 우선 (JSON 포맷 출력)",
        "3. 비주얼 생성 (visual_gen.py)\n   • 고화질 씬별 이미지 생성 (9:16 / 16:9)",
        "4. 음성/싱크 추출 (tts_engine.py)\n   • Edge-TTS 및 단어 단위 타이밍 추출"
    ]
    for s in steps:
        p = tf1.add_paragraph()
        p.text = s
        p.font.size = Pt(13)
        p.font.color.rgb = COLOR_TEXT_DARK
        p.space_after = Pt(10)

    # Branch 1: Reels/Shorts (Top Right)
    add_card(s3, Inches(6.0), Inches(1.8), Inches(6.5), Inches(2.2))
    tb_reels = s3.shapes.add_textbox(Inches(6.2), Inches(1.9), Inches(6.1), Inches(2.0))
    tf_reels = tb_reels.text_frame
    tf_reels.word_wrap = True
    pr = tf_reels.paragraphs[0]
    pr.text = "🎬 채널 1: 인스타그램 릴스 & 유튜브 숏츠 (영상 파이프라인)"
    pr.font.size = Pt(15)
    pr.font.bold = True
    pr.font.color.rgb = COLOR_ACCENT
    pr.space_after = Pt(6)

    pr_desc = tf_reels.add_paragraph()
    pr_desc.text = "• FFmpeg 영상 합성 (composer.py): Ken Burns 모션 + ASS 자막 번인\n• 인스타/유튜브 자동 업로드 + 성과 인사이트(도달/저장수) 수집\n• 빠른 소비 & 바이럴 중심의 폭발적 알고리즘 트래픽 유입"
    pr_desc.font.size = Pt(13)
    pr_desc.font.color.rgb = COLOR_TEXT_DARK

    # Branch 2: Naver Blog (Bottom Right)
    add_card(s3, Inches(6.0), Inches(4.3), Inches(6.5), Inches(2.3))
    tb_blog = s3.shapes.add_textbox(Inches(6.2), Inches(4.4), Inches(6.1), Inches(2.1))
    tf_blog = tb_blog.text_frame
    tf_blog.word_wrap = True
    pb = tf_blog.paragraphs[0]
    pb.text = "✍️ 채널 2: 네이버 블로그 (신규 확장 파이프라인)"
    pb.font.size = Pt(15)
    pb.font.bold = True
    pb.font.color.rgb = RGBColor(16, 185, 129) # Emerald Green
    pb.space_after = Pt(6)

    pb_desc = tf_blog.add_paragraph()
    pb_desc.text = "• 롱폼 글 확장 (blog_gen.py): 대본을 1,500~2,000자 포스팅으로 변환\n• 이미지 자동 배치: 릴스 생성 이미지를 본문 중간에 자연스럽게 삽입\n• 네이버 스마트블록 SEO: 키워드 검색 유입 & 인스타 프로필 연계"
    pb_desc.font.size = Pt(13)
    pb_desc.font.color.rgb = COLOR_TEXT_DARK

    # ==========================================
    # SLIDE 4: Roles & Responsibilities
    # ==========================================
    s4 = prs.slides.add_slide(blank_layout)
    add_header(s4, "팀 구성 및 역할 분담 (R&R): 총 4명의 시너지", "ROLES & RESPONSIBILITIES")

    # Team Left (Reels 2 members)
    add_card(s4, Inches(0.8), Inches(1.8), Inches(5.6), Inches(4.8))
    tag_l = s4.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(1.8), Inches(5.6), Inches(0.7))
    tag_l.fill.solid()
    tag_l.fill.fore_color.rgb = COLOR_ACCENT
    tag_l.line.fill.background()
    p_tl = tag_l.text_frame.paragraphs[0]
    p_tl.text = "파트 A: 릴스/숏츠 퀄리티 개선 & 채널 육성 (2명)"
    p_tl.font.size = Pt(14)
    p_tl.font.bold = True
    p_tl.font.color.rgb = RGBColor(255, 255, 255)
    p_tl.alignment = PP_ALIGN.CENTER

    tb_l = s4.shapes.add_textbox(Inches(1.1), Inches(2.7), Inches(5.0), Inches(3.7))
    tf_l = tb_l.text_frame
    tf_l.word_wrap = True
    p_l1 = tf_l.paragraphs[0]
    p_l1.text = "👤 팀원 1: 기획 & 대본 프롬프트 고도화"
    p_l1.font.size = Pt(15)
    p_l1.font.bold = True
    p_l1.font.color.rgb = COLOR_TEXT_DARK
    p_l1_sub = tf_l.add_paragraph()
    p_l1_sub.text = "• 3초 후킹 공식 및 스토리텔링 프롬프트 튜닝\n• 타겟 페르소나별 주제 기획 템플릿 개선\n• 인스타그램 캡션 & 해시태그 생성 최적화"
    p_l1_sub.font.size = Pt(12)
    p_l1_sub.font.color.rgb = COLOR_TEXT_MUTED
    p_l1_sub.space_after = Pt(12)

    p_l2 = tf_l.add_paragraph()
    p_l2.text = "👤 팀원 2: 비주얼 퀄리티 & 영상 연출 튜닝"
    p_l2.font.size = Pt(15)
    p_l2.font.bold = True
    p_l2.font.color.rgb = COLOR_TEXT_DARK
    p_l2_sub = tf_l.add_paragraph()
    p_l2_sub.text = "• 이미지 생성 프롬프트(실사감/조명/구도) 스타일 개선\n• 자막 가독성(폰트, 여백, 애니메이션) 및 BGM 매칭\n• 주 4~5회 정기 발행 및 시청 지속 시간 분석"
    p_l2_sub.font.size = Pt(12)
    p_l2_sub.font.color.rgb = COLOR_TEXT_MUTED

    # Team Right (Blog 2 members)
    add_card(s4, Inches(6.9), Inches(1.8), Inches(5.6), Inches(4.8))
    tag_r = s4.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(6.9), Inches(1.8), Inches(5.6), Inches(0.7))
    tag_r.fill.solid()
    tag_r.fill.fore_color.rgb = RGBColor(16, 185, 129)
    tag_r.line.fill.background()
    p_tr = tag_r.text_frame.paragraphs[0]
    p_tr.text = "파트 B: 네이버 블로그 자동화 & 크로스 연계 (2명: 본인+팀원3)"
    p_tr.font.size = Pt(14)
    p_tr.font.bold = True
    p_tr.font.color.rgb = RGBColor(255, 255, 255)
    p_tr.alignment = PP_ALIGN.CENTER

    tb_r = s4.shapes.add_textbox(Inches(7.2), Inches(2.7), Inches(5.0), Inches(3.7))
    tf_r = tb_r.text_frame
    tf_r.word_wrap = True
    p_r1 = tf_r.paragraphs[0]
    p_r1.text = "👤 본인 (프로젝트 리더): 아키텍처 & 엔진 개발"
    p_r1.font.size = Pt(15)
    p_r1.font.bold = True
    p_r1.font.color.rgb = COLOR_TEXT_DARK
    p_r1_sub = tf_r.add_paragraph()
    p_r1_sub.text = "• 블로그 자동 생성 모듈 (blog_gen.py) 코어 개발\n• 숏폼 대본 ➔ 1,500자 롱폼 구조화 프롬프트 설계\n• 이미지 자동 배치 및 전체 파이프라인 통합"
    p_r1_sub.font.size = Pt(12)
    p_r1_sub.font.color.rgb = COLOR_TEXT_MUTED
    p_r1_sub.space_after = Pt(12)

    p_r2 = tf_r.add_paragraph()
    p_r2.text = "👤 팀원 3: 네이버 SEO & 퍼블리셔 구축"
    p_r2.font.size = Pt(15)
    p_r2.font.bold = True
    p_r2.font.color.rgb = COLOR_TEXT_DARK
    p_r2_sub = tf_r.add_paragraph()
    p_r2_sub.text = "• 네이버 스마트블록/D.I.A.+ 검색 키워드 분석 로직\n• 네이버 블로그 등록기 (naver_publisher.py) 구축\n• 블로그 본문 내 인스타 릴스 링크 연계 및 유입 추적"
    p_r2_sub.font.size = Pt(12)
    p_r2_sub.font.color.rgb = COLOR_TEXT_MUTED

    # ==========================================
    # SLIDE 5: Git & Folder Structure
    # ==========================================
    s5 = prs.slides.add_slide(blank_layout)
    add_header(s5, "협업 환경 및 파일 분장: Git 충돌 방지 설계", "GIT COLLABORATION & REPO STRUCTURE")

    # File mapping card
    add_card(s5, Inches(0.8), Inches(1.8), Inches(7.5), Inches(4.8))
    tb_map = s5.shapes.add_textbox(Inches(1.1), Inches(2.0), Inches(7.0), Inches(4.4))
    tf_map = tb_map.text_frame
    tf_map.word_wrap = True
    pm = tf_map.paragraphs[0]
    pm.text = "📂 작업 영역 분리를 통한 코드 충돌 제로화"
    pm.font.size = Pt(16)
    pm.font.bold = True
    pm.font.color.rgb = COLOR_PRIMARY
    pm.space_after = Pt(12)

    code_lines = [
        ("pipeline/topic_planner.py", "팀원 1 담당 (주제/타겟 기획)"),
        ("pipeline/script_gen.py", "팀원 1 담당 (대본 프롬프트 고도화)"),
        ("pipeline/visual_gen.py", "팀원 2 담당 (이미지 스타일 프롬프트)"),
        ("pipeline/composer.py", "팀원 2 담당 (자막/영상 레이아웃)"),
        ("pipeline/blog_gen.py", "본인+팀원 3 [신규 파일] (블로그 본문 생성)"),
        ("pipeline/naver_publisher.py", "본인+팀원 3 [신규 파일] (네이버 발행 자동화)"),
        ("main.py", "파이프라인 통합 실행 (옵션 플래그 추가)")
    ]
    for fn, role in code_lines:
        p = tf_map.add_paragraph()
        p.text = f"• {fn:28} ➔ {role}"
        p.font.size = Pt(13)
        p.font.name = "Consolas"
        p.font.color.rgb = COLOR_TEXT_DARK
        p.space_after = Pt(6)

    # Git rules card
    add_card(s5, Inches(8.6), Inches(1.8), Inches(3.9), Inches(4.8), bg_color=COLOR_BG_LIGHT)
    tb_rules = s5.shapes.add_textbox(Inches(8.8), Inches(2.0), Inches(3.5), Inches(4.4))
    tf_rules = tb_rules.text_frame
    tf_rules.word_wrap = True
    pr = tf_rules.paragraphs[0]
    pr.text = "🛡️ 비전공 팀원을 위한 Git 규칙"
    pr.font.size = Pt(15)
    pr.font.bold = True
    pr.font.color.rgb = COLOR_ACCENT
    pr.space_after = Pt(14)

    git_steps = [
        "1. .env 파일 절대 푸시 금지\n   (.gitignore에 이미 차단 완료)",
        "2. 기능별 브랜치 작업\n   (feature/script, feature/blog 등)",
        "3. 무료 모드로 로컬 테스트\n   --mock-images 플래그로 API 비용 없이 합성 검증",
        "4. 주 1회 메인 브랜치 병합\n   PR(Pull Request) 리뷰 후 합치기"
    ]
    for gs in git_steps:
        p = tf_rules.add_paragraph()
        p.text = gs
        p.font.size = Pt(12)
        p.font.color.rgb = COLOR_TEXT_DARK
        p.space_after = Pt(10)

    # ==========================================
    # SLIDE 6: 4-Week Roadmap
    # ==========================================
    s6 = prs.slides.add_slide(blank_layout)
    add_header(s6, "4주 스프린트 로드맵: 실행 중심의 검증 일정", "4-WEEK SPRINT ROADMAP")

    step_w = Inches(2.8)
    top_pos6 = Inches(1.8)
    h6 = Inches(4.8)

    weeks = [
        ("1주차", "온보딩 & Hello World", COLOR_ACCENT,
         "• 전원 로컬 환경 세팅 (Python, venv, ffmpeg)\n• mock 모드로 첫 영상 1편 생성 성공 경험\n• 팀원별 API 키 발급 및 계정 개설"),
        ("2주차", "프롬프트 튜닝 & 신규 모듈", COLOR_SECONDARY,
         "• 릴스 팀: 후킹 대본 & 실사 이미지 프롬프트 개선\n• 블로그 팀: blog_gen.py 롱폼 글 생성 모듈 완성\n• 고화질 샘플 콘텐츠 2~3편 도출"),
        ("3주차", "통합 & 실전 발행 개시", COLOR_HIGHLIGHT,
         "• main.py --blog 플래그 통합\n• 인스타그램 & 네이버 블로그에 주 4회 정기 발행\n• 파이프라인 에러 모니터링 및 자동화 안정화"),
        ("4주차", "지표 분석 & 포트폴리오", RGBColor(16, 185, 129),
         "• 인스타 도달/저장수 & 블로그 검색 유입 집계\n• A/B 테스트 결과 분석 및 회고\n• AI 교육 과정 최종 발표 PPT 및 포트폴리오 완성"),
    ]

    for idx, (w_title, w_sub, w_color, w_desc) in enumerate(weeks):
        l_pos = Inches(0.8 + idx * 3.0)
        add_card(s6, l_pos, top_pos6, step_w, h6)

        # Header
        h_box = s6.shapes.add_shape(MSO_SHAPE.RECTANGLE, l_pos, top_pos6, step_w, Inches(0.9))
        h_box.fill.solid()
        h_box.fill.fore_color.rgb = w_color
        h_box.line.fill.background()
        tf_h = h_box.text_frame
        p_wh = tf_h.paragraphs[0]
        p_wh.text = w_title
        p_wh.font.size = Pt(13)
        p_wh.font.bold = True
        p_wh.font.color.rgb = RGBColor(255, 255, 255)
        p_wh.alignment = PP_ALIGN.CENTER
        p_sub = tf_h.add_paragraph()
        p_sub.text = w_sub
        p_sub.font.size = Pt(11)
        p_sub.font.color.rgb = RGBColor(241, 245, 249)
        p_sub.alignment = PP_ALIGN.CENTER

        # Content
        c_box = s6.shapes.add_textbox(l_pos + Inches(0.2), top_pos6 + Inches(1.1), step_w - Inches(0.4), h6 - Inches(1.3))
        tf_c = c_box.text_frame
        tf_c.word_wrap = True
        p_c = tf_c.paragraphs[0]
        p_c.text = w_desc
        p_c.font.size = Pt(13)
        p_c.font.color.rgb = COLOR_TEXT_DARK

    # ==========================================
    # SLIDE 7: Onboarding Guide
    # ==========================================
    s7 = prs.slides.add_slide(blank_layout)
    add_header(s7, "팀원 온보딩 퀵스타트: 5분 안에 첫 영상 뽑기", "QUICKSTART ONBOARDING GUIDE")

    # Command card
    add_card(s7, Inches(0.8), Inches(1.8), Inches(11.7), Inches(4.8), bg_color=COLOR_PRIMARY)
    tb_cmd = s7.shapes.add_textbox(Inches(1.2), Inches(2.1), Inches(11.0), Inches(4.2))
    tf_cmd = tb_cmd.text_frame
    tf_cmd.word_wrap = True

    p_ct = tf_cmd.paragraphs[0]
    p_ct.text = "⚡ 로컬 터미널 1회성 세팅 & 첫 실행 명령어"
    p_ct.font.size = Pt(16)
    p_ct.font.bold = True
    p_ct.font.color.rgb = RGBColor(255, 255, 255)
    p_ct.space_after = Pt(14)

    cmd_lines = [
        "# 1. 저장소 클론 및 가상환경 생성",
        "git clone <우리-팀-저장소-URL>",
        "cd insta_auto",
        "python -m venv .venv",
        ".\\.venv\\Scripts\\Activate.ps1",
        "",
        "# 2. 패키지 설치 & 환경변수 설정",
        "pip install -r requirements.txt",
        "cp .env.example .env   # .env 파일에 본인 GEMINI_API_KEY 입력",
        "",
        "# 3. 비용 0원 목업 모드로 첫 릴스 영상 생성 확인!",
        "python main.py --topic \"AI 개발 교육생의 하루\" --mock-script --mock-images",
        "➔ assets/output/final_reel.mp4 생성 확인 완료 🎉"
    ]

    for cl in cmd_lines:
        p = tf_cmd.add_paragraph()
        p.text = cl
        p.font.size = Pt(12)
        p.font.name = "Consolas"
        if cl.startswith("#"):
            p.font.color.rgb = RGBColor(148, 163, 184) # Slate 400
        elif cl.startswith("➔"):
            p.font.color.rgb = RGBColor(52, 211, 153) # Emerald 400
            p.font.bold = True
        else:
            p.font.color.rgb = RGBColor(248, 250, 252) # Light White
        p.space_after = Pt(2)

    prs.save(output_path)
    print(f"Presentation successfully saved to: {output_path}")

if __name__ == "__main__":
    create_deck("team_project_kickoff.pptx")

