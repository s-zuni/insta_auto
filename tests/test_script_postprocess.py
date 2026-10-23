import unittest

from pipeline import carousel_gen as cg
from pipeline import mbti_saju_content as m
from pipeline.script_gen import ReelsScript, Scene


def _script(title="을목(乙木) 女 특징", scenes=None, caption="hi #a"):
    scenes = scenes or [Scene(scene_id=1, narration="반전이에요.", visual_prompt="a cafe", duration_estimate=3)]
    return ReelsScript(title=title, hook="h", scenes=scenes, instagram_caption=caption)


class ReelPostprocessTest(unittest.TestCase):
    def test_title_has_no_hanja_and_fits(self):
        s = m._enforce_shortform_cta(_script(title="을목(乙木) 여자 특징? 이거 모르면 진짜 후회합니다"), "SAJU", "을목 여자")
        self.assertNotRegex(s.title, r"[一-鿿]")
        self.assertLessEqual(len(s.title), 16)

    def test_cta_appended_after_conclusion_and_caption_has_cta(self):
        s = m._enforce_shortform_cta(_script(), "SAJU", "을목 여자 특징")
        self.assertEqual(s.scenes[0].narration, "반전이에요.")
        self.assertIn("프로필 링크", s.scenes[-1].narration)
        self.assertIn("프로필 링크", s.instagram_caption)
        self.assertTrue(s.instagram_caption.rstrip().endswith("#a"))  # 해시태그는 맨 뒤 유지

    def test_llm_default_cta_not_duplicated_in_caption(self):
        cap = f"본문\n\n{m.FIXED_CAPTION_CTA}\n\n#a"
        s = m._enforce_shortform_cta(_script(caption=cap), "SAJU", "을목 여자 특징")
        self.assertNotIn(m.FIXED_CAPTION_CTA, s.instagram_caption)


class CarouselPostprocessTest(unittest.TestCase):
    def test_normalize_strips_hanja_everywhere(self):
        script = cg.CarouselScript(
            title="을목(乙木) 특징",
            slides=[cg.CarouselSlide(headline="을목(乙木)은 덩굴", body="木 기운이 강해요"),
                    cg.CarouselSlide(headline="끝", body="")],
            instagram_caption="c", cover_visual_prompt="a",
        )
        out = cg._normalize(script)
        blob = out.title + "".join(s.headline + s.body for s in out.slides)
        self.assertNotRegex(blob, r"[一-鿿]")

    def test_caption_cta_added_before_hashtags(self):
        script = cg.CarouselScript(title="t", slides=[cg.CarouselSlide(headline="h", body="b")] * 2,
                                   instagram_caption="본문 #사주 #운세", cover_visual_prompt="a")
        out = cg._ensure_caption_cta(script, "SAJU", {"topic": "을목 여자"})
        self.assertIn("프로필 링크", out.instagram_caption)
        self.assertIn("📌", out.instagram_caption)
        self.assertTrue(out.instagram_caption.rstrip().endswith("#사주 #운세"))

    def test_caption_cta_not_duplicated(self):
        script = cg.CarouselScript(title="t", slides=[cg.CarouselSlide(headline="h", body="b")] * 2,
                                   instagram_caption="본문\n👉 프로필 링크에서 확인 #a", cover_visual_prompt="a")
        before = script.instagram_caption
        self.assertEqual(cg._ensure_caption_cta(script, "SAJU", {}).instagram_caption, before)


if __name__ == "__main__":
    unittest.main()
