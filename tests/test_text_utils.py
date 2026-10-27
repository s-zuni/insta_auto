import unittest
from pathlib import Path
from PIL import ImageFont

from pipeline.text_utils import (
    build_karaoke_blocks,
    normalize_mbti_to_english,
    sanitize_narration,
    sanitize_title,
    split_into_clauses,
    wrap_by_pixel_width,
    wrap_natural_title,
)


class NormalizeMbtiTest(unittest.TestCase):
    def test_korean_mbti_transliterations(self):
        self.assertEqual(
            normalize_mbti_to_english("인프피는 엠비티아이 중에서 제일 여려요"),
            "INFP는 MBTI 중에서 제일 여려요"
        )
        self.assertEqual(
            normalize_mbti_to_english("엔티제와 인팁의 궁합 소름"),
            "ENTJ와 INTP의 궁합 소름"
        )
        self.assertEqual(
            normalize_mbti_to_english("엣프제 잇티제 엣팁 잇프피"),
            "ESFJ ISTJ ESTP ISFP"
        )

    def test_lowercase_english_mbti(self):
        self.assertEqual(
            normalize_mbti_to_english("infp와 enfp의 mbti 분석"),
            "INFP와 ENFP의 MBTI 분석"
        )

    def test_sanitize_narration_normalizes_mbti(self):
        self.assertEqual(
            sanitize_narration("을목(乙木) 인프피의 올해 운세"),
            "을목 INFP의 올해 운세"
        )


class SanitizeTitleTest(unittest.TestCase):
    def test_removes_parenthesized_hanja(self):
        self.assertEqual(sanitize_title("을목(乙木) 여자 특징"), "을목 여자 특징")

    def test_removes_bare_hanja(self):
        self.assertNotRegex(sanitize_title("乙木 여자 특징"), r"[一-鿿]")

    def test_keeps_hangul_english_digits(self):
        self.assertEqual(sanitize_title("ENFP 3가지 vs 신금?"), "ENFP 3가지 vs 신금?")

    def test_normalizes_korean_mbti(self):
        self.assertEqual(sanitize_title("인프피 사주 궁합"), "INFP 사주 궁합")

    def test_empty_values(self):
        self.assertEqual(sanitize_title(""), "")
        self.assertIsNone(sanitize_title(None))

    def test_matches_narration_rule(self):
        self.assertEqual(sanitize_narration("토(土)사주"), "토사주")


class ClauseAndWrapTest(unittest.TestCase):
    def test_split_merges_short_fragments(self):
        parts = split_into_clauses("네, 그래요. 오늘은 정말 좋은 하루예요")
        self.assertTrue(all(len(p) >= 6 for p in parts[:-1]) or len(parts) == 1)

    def test_split_recognizes_korean_connective_endings(self):
        parts = split_into_clauses("겉으로는 다정해 보이는데 한 번 마음 식으면 손절해요")
        self.assertEqual(len(parts), 2)
        self.assertEqual(parts[0], "겉으로는 다정해 보이는데")
        self.assertEqual(parts[1], "한 번 마음 식으면 손절해요")

    def test_wrap_respects_width(self):
        font = ImageFont.load_default()
        lines = wrap_by_pixel_width("가나다 라마바 사아자 차카타 파하", font, 40)
        self.assertGreater(len(lines), 1)
        self.assertEqual(" ".join(lines), "가나다 라마바 사아자 차카타 파하")

    def test_wrap_natural_title_with_delimiter(self):
        font_path = Path("assets/fonts/Pretendard-Bold.otf")
        font = ImageFont.truetype(str(font_path), 86) if font_path.is_file() else ImageFont.load_default()
        lines = wrap_natural_title("98년생 임수 INFP, 결혼운 언제 터질까?", font, 970)
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0], "98년생 임수 INFP,")
        self.assertEqual(lines[1], "결혼운 언제 터질까?")

    def test_wrap_natural_title_balanced(self):
        font_path = Path("assets/fonts/Pretendard-Bold.otf")
        font = ImageFont.truetype(str(font_path), 86) if font_path.is_file() else ImageFont.load_default()
        lines = wrap_natural_title("00년생 용띠 ESFJ 특징 3가지", font, 970)
        self.assertEqual(len(lines), 2)
        self.assertGreater(len(lines[1].split()), 1)  # 외톨이 단어 방지


class KaraokeBlocksTest(unittest.TestCase):
    def test_returns_blocks_not_none(self):
        font = ImageFont.load_default()
        blocks = build_karaoke_blocks("을목 여자 특징이에요. 이거 모르면 후회해요", [], 0.0, 3.0, font, 900)
        self.assertIsNotNone(blocks)
        self.assertGreaterEqual(len(blocks), 1)
        start, end, text = blocks[0]
        self.assertLessEqual(start, end)
        self.assertIn("\\kf", text)

    def test_colorize_token_with_particles(self):
        from pipeline.text_utils import _colorize_token
        self.assertIn(r"\c&H002BF7FF&", _colorize_token("INFP는"))
        self.assertIn(r"\c&H002BF7FF&", _colorize_token("ENTJ가"))
        self.assertIn(r"\c&H002BF7FF&", _colorize_token("MBTI의"))
        self.assertNotIn(r"\c&H002BF7FF&", _colorize_token("안녕하세요"))

    def test_time_shift_never_negative(self):
        font = ImageFont.load_default()
        blocks = build_karaoke_blocks("안녕하세요 반갑습니다", [], 0.0, 2.0, font, 900, time_shift=0.5)
        self.assertTrue(all(s >= 0 and e >= 0 for s, e, _ in blocks))


if __name__ == "__main__":
    unittest.main()
