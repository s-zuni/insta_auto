import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import ImageDraw, ImageFont

from pipeline import cover, flow_automation as fa, hook_guard
from pipeline.mbti_saju_content import _enforce_plain_hook
from pipeline.script_gen import ReelsScript, Scene
from pipeline.text_utils import wrap_natural_title
from pipeline.visual_gen import infer_curiosity_badge

TITLE = "착한 당신이 먼저 연락 끊는 진짜 이유"


def _font(size):
    p = Path("assets/fonts/Pretendard-Bold.otf")
    return ImageFont.truetype(str(p), size) if p.is_file() else ImageFont.load_default()


class WrapNeverDropsTextTest(unittest.TestCase):
    def test_overflow_is_returned_not_truncated(self):
        # 126px, 940px 폭에서는 2줄로 안 들어간다 -> 예전엔 '진짜 이유'가 잘려 나갔다
        lines = wrap_natural_title(TITLE, _font(126), 940, max_lines=2)
        self.assertEqual("".join(lines).replace(" ", ""), TITLE.replace(" ", ""))


class CoverTest(unittest.TestCase):
    def test_cover_draws_full_title(self):
        drawn = []
        real_text = ImageDraw.ImageDraw.text

        def spy(self_, xy, text, *a, **kw):
            if kw.get("anchor") == "mt":
                drawn.append(text)
            return real_text(self_, xy, text, *a, **kw)

        with tempfile.TemporaryDirectory() as d, mock.patch.object(ImageDraw.ImageDraw, "text", spy):
            cover.build_reel_cover(None, TITLE, Path(d) / "c.jpg")
        unique = list(dict.fromkeys(drawn))  # 그림자+본문으로 같은 줄이 두 번 그려진다
        self.assertEqual("".join(unique).replace(" ", ""), TITLE.replace(" ", ""))

    def test_badge_has_no_tofu_glyph_brackets_or_fake_stats(self):
        for title in ("착한 당신이 먼저 연락 끊는 진짜 이유", "여기서 3개 이상 맞으면 소름", "98년생 INFP 결혼운",
                      "인생 풀리기 직전 신호", "연락 안 하는 사람 속마음"):
            badge = cover.infer_mbtiju_badge(title)
            self.assertNotIn("✦", badge, title)
            self.assertNotIn("]", badge, title)
            self.assertNotIn("[", badge, title)
            self.assertNotRegex(badge, r"\d+%", title)

    def test_curiosity_badge_has_no_fake_stats_or_jargon(self):
        for title in ("착한 당신이 먼저 연락 끊는 진짜 이유", "3개 맞으면 체크", "인생 풀리기 직전 신호", "돈 새는 이유"):
            b = infer_curiosity_badge(title)
            self.assertNotRegex(b, r"\d+%", title)
            self.assertEqual(hook_guard.find_jargon(b), [], title)

    def test_plain_badge_formats_bracket_label(self):
        self.assertEqual(cover._plain_badge("[ 반전 주의 ] 겉과 속이 다른 사람들"), "반전 주의 · 겉과 속이 다른 사람들")
        self.assertEqual(cover._plain_badge("[ 태그 ]"), "태그")


class VideoReuseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        env = mock.patch.dict(os.environ, {"FLOW_REUSE_EXISTING": "true"})
        env.start()
        self.addCleanup(env.stop)
        self.video = self.dir / "scene_01_raw.mp4"
        self.video.write_bytes(b"x" * 40_000)

    def test_untagged_old_clip_is_not_reused(self):
        with mock.patch.object(fa, "_fetch_scene_video", return_value=None) as fetch:
            self.assertIsNone(fa.acquire_scene_video(1, "new prompt", self.dir))
        fetch.assert_called_once()

    def test_clip_from_different_prompt_is_not_reused(self):
        fa._write_source_tag(self.video, "old prompt")
        with mock.patch.object(fa, "_fetch_scene_video", return_value=None) as fetch:
            self.assertIsNone(fa.acquire_scene_video(1, "new prompt", self.dir))
        fetch.assert_called_once()

    def test_clip_from_same_prompt_is_reused(self):
        fa._write_source_tag(self.video, "same prompt")
        with mock.patch.object(fa, "_fetch_scene_video") as fetch:
            self.assertEqual(fa.acquire_scene_video(1, "same prompt", self.dir), self.video)
        fetch.assert_not_called()

    def test_fresh_clip_gets_tagged(self):
        with mock.patch.object(fa, "_fetch_scene_video", return_value=self.video):
            fa.acquire_scene_video(1, "fresh", self.dir)
        self.assertTrue(fa._source_matches(self.video, "fresh"))


class ComposerVideoResolveTest(unittest.TestCase):
    def test_does_not_autodetect_stale_clip_by_default(self):
        from pipeline.composer import _resolve_scene_video
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "images").mkdir()
            (root / "videos").mkdir()
            (root / "videos" / "scene_01_raw.mp4").write_bytes(b"x" * 40_000)
            img = str(root / "images" / "scene_01.jpg")
            self.assertIsNone(_resolve_scene_video({}, 1, img))
            self.assertEqual(_resolve_scene_video({1: "given.mp4"}, 1, img), "given.mp4")
            with mock.patch.dict(os.environ, {"COMPOSER_AUTODETECT_VIDEOS": "true"}):
                self.assertTrue(_resolve_scene_video({}, 1, img).endswith("scene_01_raw.mp4"))


class GuardContextAndBirthYearTest(unittest.TestCase):
    def test_rewrite_context_is_script_narration_not_ordered_topic(self):
        scenes = [Scene(scene_id=i + 1, narration=n, duration_estimate=3, visual_prompt="v")
                  for i, n in enumerate(["힘들 때마다 연락하기 주저해요.", "혼자 정리하곤 합니다."])]
        s = ReelsScript(title="을목 여자 특징", hook="훅", scenes=scenes, instagram_caption="c")
        seen = {}

        def fake(fields, context="", llm=None):
            seen["context"] = context
            return fields, []

        with mock.patch.object(hook_guard, "enforce_plain", side_effect=fake):
            _enforce_plain_hook(s, "주문한 전혀 다른 주제")
        self.assertIn("힘들 때마다", seen["context"])
        self.assertNotIn("주문한", seen["context"])

    def test_birth_year_allowed_by_default_bannable_by_env(self):
        self.assertEqual(hook_guard.find_jargon("99년생 토끼띠가 지치는 이유"), [])
        with mock.patch.dict(os.environ, {"HOOK_BAN_BIRTHYEAR": "true"}):
            found = hook_guard.find_jargon("99년생 토끼띠가 지치는 이유")
            self.assertIn("99년생", found)
            self.assertIn("토끼띠", found)
            self.assertEqual(hook_guard.find_jargon("허리띠 말고 연락 끊는 이유"), [])


if __name__ == "__main__":
    unittest.main()
