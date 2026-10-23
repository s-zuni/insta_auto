import unittest

from PIL import ImageFont

from pipeline.text_utils import (
    build_karaoke_blocks,
    sanitize_narration,
    sanitize_title,
    split_into_clauses,
    wrap_by_pixel_width,
)


class SanitizeTitleTest(unittest.TestCase):
    def test_removes_parenthesized_hanja(self):
        self.assertEqual(sanitize_title("을목(乙木) 여자 특징"), "을목 여자 특징")

    def test_removes_bare_hanja(self):
        self.assertNotRegex(sanitize_title("乙木 여자 특징"), r"[一-鿿]")

    def test_keeps_hangul_english_digits(self):
        self.assertEqual(sanitize_title("ENFP 3가지 vs 신금?"), "ENFP 3가지 vs 신금?")

    def test_empty_values(self):
        self.assertEqual(sanitize_title(""), "")
        self.assertIsNone(sanitize_title(None))

    def test_matches_narration_rule(self):
        self.assertEqual(sanitize_narration("토(土)사주"), "토사주")


class ClauseAndWrapTest(unittest.TestCase):
    def test_split_merges_short_fragments(self):
        parts = split_into_clauses("네, 그래요. 오늘은 정말 좋은 하루예요")
        self.assertTrue(all(len(p) >= 6 for p in parts[:-1]) or len(parts) == 1)

    def test_wrap_respects_width(self):
        font = ImageFont.load_default()
        lines = wrap_by_pixel_width("가나다 라마바 사아자 차카타 파하", font, 40)
        self.assertGreater(len(lines), 1)
        self.assertEqual(" ".join(lines), "가나다 라마바 사아자 차카타 파하")


class KaraokeBlocksTest(unittest.TestCase):
    def test_returns_blocks_not_none(self):
        # 회귀: HIGHLIGHT_KEYWORDS가 함수 본문 중간에 끼어 None을 반환하던 버그
        font = ImageFont.load_default()
        blocks = build_karaoke_blocks("을목 여자 특징이에요. 이거 모르면 후회해요", [], 0.0, 3.0, font, 900)
        self.assertIsNotNone(blocks)
        self.assertGreaterEqual(len(blocks), 1)
        start, end, text = blocks[0]
        self.assertLessEqual(start, end)
        self.assertIn("\\kf", text)

    def test_time_shift_never_negative(self):
        font = ImageFont.load_default()
        blocks = build_karaoke_blocks("안녕하세요 반갑습니다", [], 0.0, 2.0, font, 900, time_shift=0.5)
        self.assertTrue(all(s >= 0 and e >= 0 for s, e, _ in blocks))


if __name__ == "__main__":
    unittest.main()
