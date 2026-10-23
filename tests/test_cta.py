import os
import unittest
from unittest import mock

from pipeline import cta
from pipeline.script_gen import Scene


def _scenes(*texts):
    return [Scene(scene_id=i + 1, narration=t, visual_prompt="a cafe", duration_estimate=3) for i, t in enumerate(texts)]


class InferKindTest(unittest.TestCase):
    def test_kinds(self):
        self.assertEqual(cta.infer_cta_kind("SAJU", "을목 여자 특징? 이거 모르면"), "report3y")
        self.assertEqual(cta.infer_cta_kind("SAJU", "남자 신금 x 여자 임수 궁합"), "couple")
        self.assertEqual(cta.infer_cta_kind("MBTI", "남자 INTJ x 여자 ENFP 궁합"), "mbti_saju")
        self.assertEqual(cta.infer_cta_kind("TAROT", ""), "tarot")
        self.assertEqual(cta.infer_cta_kind("SAJU", "앞으로 3년 흐름"), "report3y")

    def test_every_kind_has_plans_and_share_lines(self):
        for kind in cta.CTA_PLANS:
            self.assertTrue(cta.CTA_PLANS[kind])
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


if __name__ == "__main__":
    unittest.main()
