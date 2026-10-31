import random
import unittest
from collections import Counter

from pipeline import topic_planner as tp


class SeedSpecTest(unittest.TestCase):
    def setUp(self):
        random.seed(1234)

    def test_all_pillars_have_guide_and_marker(self):
        for pillar in tp.PILLAR_WEIGHTS:
            self.assertIn(pillar, tp.PILLAR_GUIDE)
            self.assertIn(pillar, tp._PILLAR_MARKERS)

    def test_every_pillar_produces_a_filled_pattern(self):
        for pillar in tp.PILLAR_WEIGHTS:
            for _ in range(30):
                seed = tp._seed_spec("SAJU", [], pillar=pillar)
                self.assertTrue(seed["pattern"], pillar)
                self.assertNotRegex(seed["pattern"], r"[{}]", pillar)  # 미치환 플레이스홀더 없음
                self.assertNotRegex(seed["pattern"], r"[一-鿿]", pillar)

    def test_pillar_distribution_covers_new_pillars(self):
        counts = Counter(tp._seed_spec("SAJU", [])["pillar"] for _ in range(600))
        for pillar in ("relation", "habit", "sipsin", "identity"):
            self.assertGreater(counts[pillar], 0, pillar)

    def test_mbti_kind_keeps_mbti_series(self):
        seed = tp._seed_spec("MBTI", [], pillar="identity")
        self.assertEqual(seed["series"], "MBTI")
        self.assertRegex(seed["mbti"], r"^[IE][NS][TF][JP]$")

    def test_exclude_dm(self):
        for _ in range(30):
            self.assertNotEqual(tp._seed_spec("SAJU", [], exclude_dm="을목", pillar="identity")["dm"], "을목")


class FreshnessTest(unittest.TestCase):
    def test_pick_fresh_avoids_recent(self):
        recent = ["월급 들어온 날 어쩌고", "헤어진 다음 날 어쩌고"]
        pool = ["월급 들어온 날", "헤어진 다음 날", "택배 뜯는 순간"]
        for _ in range(20):
            self.assertEqual(tp._pick_fresh(pool, recent), "택배 뜯는 순간")

    def test_pick_fresh_falls_back_when_all_used(self):
        pool = ["봄", "여름"]
        self.assertIn(tp._pick_fresh(pool, ["봄 여름"]), pool)


class FitTitleTest(unittest.TestCase):
    def test_limit_and_hanja(self):
        t = tp._fit_title("을목(乙木) 여자가 퇴사 충동 오는 진짜 이유는 따로 있어요")
        self.assertLessEqual(len(t), 22)
        self.assertNotRegex(t, r"[一-鿿]")

    def test_short_title_untouched(self):
        self.assertEqual(tp._fit_title("을목 여자 특징?"), "을목 여자 특징?")

    def test_cuts_on_word_boundary(self):
        t = tp._fit_title("동업 파트너한테 병화 남자가 꼭 알아야 할 한 가지")
        self.assertFalse(t.endswith(" "))
        self.assertTrue("동업 파트너한테 병화 남자가 꼭 알아야 할 한 가지".startswith(t))


class FallbackAndClassifyTest(unittest.TestCase):
    def test_fallback_option_fields(self):
        seed = tp._seed_spec("SAJU", [], pillar="relation")
        opt = tp._fallback_option(seed)
        for k in ("series", "mbti", "topic", "title", "hook", "summary"):
            self.assertIn(k, opt)
        self.assertLessEqual(len(opt["title"]), 22)

    def test_classify_custom_topic(self):
        self.assertEqual(tp.classify_custom_topic("INFP 연애")["series"], "MBTI")
        self.assertEqual(tp.classify_custom_topic("INFP 연애")["mbti"], "INFP")
        self.assertEqual(tp.classify_custom_topic("타로 한 장")["series"], "TAROT")
        self.assertEqual(tp.classify_custom_topic("을목 여자")["series"], "SAJU")


if __name__ == "__main__":
    unittest.main()
