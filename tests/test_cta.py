import os
import unittest
from unittest import mock

from pipeline import cta
from pipeline.script_gen import Scene


def _scenes(*texts):
    return [Scene(scene_id=i + 1, narration=t, visual_prompt="a cafe", duration_estimate=3) for i, t in enumerate(texts)]


class InferKindTest(unittest.TestCase):
    def test_kinds(self):
        # 기존 kind 매핑 불변성 유지
        self.assertEqual(cta.infer_cta_kind("SAJU", "을목 여자 특징? 이거 모르면"), "report3y")
        self.assertEqual(cta.infer_cta_kind("SAJU", "남자 신금 x 여자 임수 궁합"), "couple")
        self.assertEqual(cta.infer_cta_kind("MBTI", "남자 INTJ x 여자 ENFP 궁합"), "mbti_saju")
        self.assertEqual(cta.infer_cta_kind("TAROT", ""), "tarot")
        self.assertEqual(cta.infer_cta_kind("JAMIDOSU", "명궁 풀이"), "jamidosu")
        self.assertEqual(cta.infer_cta_kind("SAJU", "앞으로 3년 흐름"), "report3y")
        self.assertEqual(cta.infer_cta_kind("SAJU", "직업과 적성"), "career")
        self.assertEqual(cta.infer_cta_kind("SAJU", "내 사주에 맞는 여행지"), "travel")

    def test_consult_kinds_for_concrete_concerns(self):
        # 구체적 고민형 주제는 consult kind로 매핑
        self.assertEqual(cta.infer_cta_kind("SAJU", "재회 연락 기다리는 사람이 이번 달 조심할 것"), "consult")
        self.assertEqual(cta.infer_cta_kind("SAJU", "썸 타는데 갑자기 연락 뜸해진 남자 속마음"), "consult")
        self.assertEqual(cta.infer_cta_kind("SAJU", "헤어지고 나서 미련 남았을 때 조심할 행동"), "consult")
        self.assertEqual(cta.infer_cta_kind("SAJU", "짝사랑 포기해야 할지 계속 가야 할지"), "consult")
        self.assertEqual(cta.infer_cta_kind("SAJU", "이직 고민이 터지는 일요일 밤"), "consult")
        self.assertEqual(cta.infer_cta_kind("SAJU", "퇴사 고민"), "consult")
        self.assertEqual(cta.infer_cta_kind("SAJU", "결혼 고민 앞두고 타이밍 엇갈리는 사람"), "consult")
        self.assertEqual(cta.infer_cta_kind("SAJU", "이럴 땐 어떡해"), "consult")
        self.assertEqual(cta.infer_cta_kind("CONSULT", "아무 주제"), "consult")

    def test_consult_cta_ratio_env(self):
        # CONSULT_CTA_RATIO=0 이면 고민형 주제라도 상담 kind로 가지 않고 기존 로직으로 폴백
        with mock.patch.dict(os.environ, {"CONSULT_CTA_RATIO": "0"}):
            self.assertEqual(cta.infer_cta_kind("SAJU", "재회 연락 기다리는 사람"), "report3y")
            self.assertEqual(cta.infer_cta_kind("SAJU", "이직 고민"), "career")

        # CONSULT_CTA_RATIO=1.0 이면 항상 consult
        with mock.patch.dict(os.environ, {"CONSULT_CTA_RATIO": "1.0"}):
            self.assertEqual(cta.infer_cta_kind("SAJU", "재회 연락"), "consult")

        # 잘못된 값이 들어오면 기본 1.0
        with mock.patch.dict(os.environ, {"CONSULT_CTA_RATIO": "invalid"}):
            self.assertEqual(cta._consult_ratio(), 1.0)

    def test_every_kind_has_plans_and_share_lines(self):
        for kind in cta.CTA_PLANS:
            self.assertTrue(cta.CTA_PLANS[kind])
            self.assertGreaterEqual(len(cta.CTA_PLANS[kind]), 1)
        self.assertGreaterEqual(len(cta.CTA_PLANS["consult"]), 3)  # 상담 문구 3종 이상
        self.assertTrue(cta.pick_share_line("no-such-kind"))  # 알 수 없는 kind는 기본 문구


class ApplyReelCtaTest(unittest.TestCase):
    def test_adds_share_and_link_scenes_and_keeps_conclusion(self):
        sc = _scenes("씬 하나예요.", "반전은 이거예요.")
        narr, cap = cta.apply_reel_cta(sc, "", "SAJU", "을목 여자 특징", use_share=True)
        self.assertEqual(len(sc), 4)
        self.assertEqual(sc[1].narration, "반전은 이거예요.")  # LLM 결론 씬 보존
        self.assertIn("프로필 링크", sc[-1].narration)
        self.assertTrue(cta.has_share_line(sc))
        self.assertEqual([s.scene_id for s in sc], [1, 2, 3, 4])
        self.assertIn("different framing", sc[-1].visual_prompt)
        self.assertIn("📩", cap)
        self.assertIn("프로필 링크", cap)

    def test_without_share(self):
        sc = _scenes("씬 하나예요.")
        _, cap = cta.apply_reel_cta(sc, "", "SAJU", "을목 여자 특징", use_share=False)
        self.assertEqual(len(sc), 2)
        self.assertFalse(cta.has_share_line(sc))
        self.assertNotIn("📩", cap)

    def test_replaces_llm_profile_sentence_keeps_preceding_text(self):
        sc = _scenes("반전이에요. 프로필 링크에서 당신의 모든 운명을 확인하세요!")
        cta.apply_reel_cta(sc, "", "SAJU", "을목", use_share=False)
        self.assertEqual(sc[0].narration, "반전이에요.")
        self.assertIn("프로필 링크", sc[1].narration)

    def test_cta_only_last_scene_is_replaced(self):
        sc = _scenes("프로필 링크에서 확인하세요")
        cta.apply_reel_cta(sc, "", "SAJU", "을목", use_share=True)
        self.assertEqual(len(sc), 2)
        self.assertTrue(cta.has_share_line(sc))

    def test_empty_scenes_ok(self):
        narr, cap = cta.apply_reel_cta([], "", "SAJU", "을목", use_share=True)
        self.assertTrue(narr and cap)

    def test_ratio_env_zero_never_shares(self):
        with mock.patch.dict(os.environ, {"SHARE_CTA_RATIO": "0"}):
            for _ in range(20):
                sc = _scenes("씬이에요.")
                cta.apply_reel_cta(sc, "", "SAJU", "을목")
                self.assertFalse(cta.has_share_line(sc))

    def test_ratio_env_invalid_falls_back_to_always(self):
        with mock.patch.dict(os.environ, {"SHARE_CTA_RATIO": "abc"}):
            self.assertEqual(cta._share_ratio(), 1.0)

    def test_narration_has_no_hanja(self):
        for kind, plans in cta.CTA_PLANS.items():
            for narr, _, _ in plans:
                self.assertNotRegex(narr, r"[一-鿿]")
        for lines in cta.SHARE_LINES.values():
            for narr, _ in lines:
                self.assertNotRegex(narr, r"[一-鿿]")


class CtaTextRulesTest(unittest.TestCase):
    def test_instagram_captions_have_profile_link_and_no_direct_url_or_price(self):
        for kind, plans in cta.CTA_PLANS.items():
            for _, cap, _ in plans:
                self.assertIn("프로필 링크", cap, f"[{kind}] 캡션에 '프로필 링크'가 포함되어야 합니다.")
                # 인스타그램 캡션에는 직접 URL과 가격을 쓰지 않는다
                self.assertNotIn("http://", cap)
                self.assertNotIn("https://", cap)
                self.assertNotIn(".com", cap)
                self.assertNotIn("9,900", cap)
                self.assertNotIn("19,900", cap)
                self.assertNotIn("원", cap)
                # 봇 자동 전송/안내 약속 문구 금지
                self.assertNotIn("링크 전송", cap)
                self.assertNotIn("링크 안내", cap)
                self.assertNotIn("바로 안내", cap)

    def test_consult_cta_specific_rules(self):
        # 상담 문구 전수 검사
        for narr, cap, th_tpl in cta.CTA_PLANS["consult"]:
            # 나레이션 규칙: 순수 한글(한자 없음), 프로필 링크 포함, 상담 키워드 포함
            self.assertNotRegex(narr, r"[一-鿿]")
            self.assertIn("프로필 링크", narr)
            self.assertIn("상담", narr)
            self.assertNotIn("9,900", narr)
            self.assertNotIn("원", narr)

            # 인스타 캡션 규칙: [상담] 키워드, 카톡 1:1 상담 표기
            self.assertIn("[상담]", cap)
            self.assertIn("카톡 1:1", cap)

            # Threads 규칙: 카톡 채널 주소 슬롯, 9,900원 가격 표기, 전문가 직접 검수 문구 필수
            self.assertIn("{url}", th_tpl)
            self.assertIn("9,900원", th_tpl)
            self.assertIn("AI 분석을 바탕으로 운세 서비스 전문가가 직접 검수", th_tpl)
            self.assertIn("24시간", th_tpl)
            # 금지 표현
            self.assertNotIn("실시간", th_tpl)
            self.assertNotIn("즉시 답변", th_tpl)
            self.assertNotIn("예약", th_tpl)


class ThreadsCtaUrlTest(unittest.TestCase):
    def test_consult_uses_kakao_url_and_env_override(self):
        # 기본 카톡 채널 주소
        res = cta.pick_threads_cta("https://mbtiju.com/premium", topic="재회 연락 기다리는 사람")
        self.assertIn("https://pf.kakao.com/_xcdXJX/chat", res)
        self.assertIn("9,900원", res)

        # 환경변수로 덮어쓰기
        with mock.patch.dict(os.environ, {"KAKAO_CHAT_URL": "https://pf.kakao.com/_custom/chat"}):
            # cta.py의 KAKAO_CHAT_URL을 재참조하도록 테스트
            with mock.patch.object(cta, "KAKAO_CHAT_URL", "https://pf.kakao.com/_custom/chat"):
                res_custom = cta.pick_threads_cta("https://mbtiju.com/premium", topic="재회 고민")
                self.assertIn("https://pf.kakao.com/_custom/chat", res_custom)

    def test_existing_report_uses_premium_url(self):
        res = cta.pick_threads_cta("https://mbtiju.com/premium", topic="을목 여자 특징 앞으로 3년 흐름")
        self.assertIn("https://mbtiju.com/premium", res)
        self.assertNotIn("kakao", res)


class YoutubeAdaptationTest(unittest.TestCase):
    def test_consult_caption_replaces_profile_link_with_kakao_url(self):
        cap = "💬 댓글에 [상담] 남겨주세요!\n👉 프로필 링크에서 카톡 1:1 상담으로 내 고민을 바로 물어보세요!"
        adapted = cta.adapt_caption_for_youtube(cap)
        self.assertNotIn("프로필 링크", adapted)
        self.assertIn("https://pf.kakao.com/_xcdXJX/chat", adapted)

    def test_report_caption_replaces_profile_link_with_site_url(self):
        cap = "💬 댓글에 [사주] 남겨주세요!\n👉 프로필 링크에서 가입 없이 30초 무료 체험으로 내 일간부터 확인하세요!"
        adapted = cta.adapt_caption_for_youtube(cap)
        self.assertNotIn("프로필 링크", adapted)
        self.assertIn("https://mbtiju.com", adapted)


class DetectCtaKindTest(unittest.TestCase):
    def test_detects_consult_and_report_scenes(self):
        sc_consult = _scenes("앞 내용이에요.", cta.CTA_PLANS["consult"][0][0])
        self.assertEqual(cta.detect_cta_kind(sc_consult), "consult")

        sc_report = _scenes("앞 내용이에요.", cta.CTA_PLANS["report3y"][0][0])
        self.assertEqual(cta.detect_cta_kind(sc_report), "report3y")

        sc_unknown = _scenes("일반 씬")
        self.assertEqual(cta.detect_cta_kind(sc_unknown, default="fallback"), "fallback")


class ThreadsBanmalAndZeroEmojiTest(unittest.TestCase):
    def test_all_threads_cta_templates_are_banmal_and_emoji_free(self):
        from pipeline import threads_content as tc

        for kind, plans in cta.CTA_PLANS.items():
            for _, _, th_tpl in plans:
                self.assertEqual(tc._strip_emojis(th_tpl), th_tpl, f"[{kind}] Threads CTA에 이모지가 없어야 합니다.")
                self.assertFalse(tc._has_polite_ending([th_tpl]), f"[{kind}] Threads CTA는 반말이어야 합니다: {th_tpl}")

        for v in tc.CTA_VARIANTS:
            self.assertEqual(tc._strip_emojis(v), v)
            self.assertFalse(tc._has_polite_ending([v]))

    def test_strip_emojis_and_convert_polite_to_banmal(self):
        from pipeline import threads_content as tc

        raw = "🔥 **겉으론 다정한데** 속으론 칼같은 사람 특징 ✨\n1. 연락 귀찮아해요 😭\n2. 근데 내 사람은 챙기거든요\n솔직히 맞는지 확인해보세요! 👉"
        cleaned = tc._clean_post(raw)
        self.assertNotIn("🔥", cleaned)
        self.assertNotIn("✨", cleaned)
        self.assertNotIn("😭", cleaned)
        self.assertNotIn("👉", cleaned)
        self.assertNotIn("**", cleaned)
        self.assertFalse(tc._has_polite_ending([cleaned]))
        self.assertIn("귀찮아함", cleaned)
        self.assertIn("챙기거든", cleaned)
        self.assertIn("확인해봐!", cleaned)

    def test_generate_threads_retries_on_polite_and_strips_emojis(self):
        from pipeline import threads_content as tc

        polite_cand = tc.ThreadsThread(
            topic_tag="사주🔥",
            posts=["겉으론 순한데 속은 칼같은 사람이에요 ✨\n첫째로 손절이 빨라요\n둘째로 뒤끝이 없어요\n솔직히 맞나요?"],
        )
        banmal_cand = tc.ThreadsThread(
            topic_tag="사주",
            posts=["겉으론 다 맞춰주는데 속으론 이미 손절 끝낸 사람 특징\n\n1. 싸울 때 화 안 내고 입 닫음\n2. 카톡 미리보기로만 읽고 안 봄\n\n솔직히 본인 몇 개 해당됨?"],
        )
        with mock.patch.object(tc, "generate_json", side_effect=[polite_cand, banmal_cand]) as m_gen:
            res = tc.generate_threads_thread(category="사주", slot="evening", with_cta=True)
            self.assertEqual(m_gen.call_count, 2)  # 1차 존댓말 감지 후 2차 재시도
            for p in res.posts:
                self.assertEqual(tc._strip_emojis(p), p)
                self.assertFalse(tc._has_polite_ending([p]))


if __name__ == "__main__":
    unittest.main()
