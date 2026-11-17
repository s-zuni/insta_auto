import os
import random
import unittest
from unittest import mock

from pipeline import hook_guard, topic_planner as tp
from pipeline.mbti_saju_content import _enforce_plain_hook
from pipeline.script_gen import ReelsScript, Scene


def _script(title, hook, scene1):
    scenes = [Scene(scene_id=1, narration=scene1, duration_estimate=3, visual_prompt="v", media_type="video")]
    return ReelsScript(title=title, hook=hook, scenes=scenes, instagram_caption="c")


class FindJargonTest(unittest.TestCase):
    def test_detects_day_master_sinsal_and_abbreviation(self):
        self.assertIn("임수", hook_guard.find_jargon("98년생 임수 INFP, 올해 결혼운"))
        self.assertIn("도화살", hook_guard.find_jargon("3개 맞으면 도화살"))
        self.assertIn("겉착속칼", hook_guard.find_jargon("겉착속칼 사주 특징"))
        self.assertIn("대운", hook_guard.find_jargon("대운 터지기 직전"))

    def test_plain_hooks_pass(self):
        for h in ("착한 사람의 소름돋는 이중성", "다 퍼주는 사람이 제일 먼저 연락 끊는 이유",
                  "사주에 이런 사람 많아요", "상관없다고 말하는 사람"):
            self.assertEqual(hook_guard.find_jargon(h), [], h)

    def test_mbti_allowed_by_default_and_bannable(self):
        self.assertEqual(hook_guard.find_jargon("INFP가 연애할 때"), [])
        with mock.patch.dict(os.environ, {"HOOK_BAN_MBTI": "true"}):
            self.assertEqual(hook_guard.find_jargon("INFP가 연애할 때"), ["INFP"])

    def test_allow_switch(self):
        with mock.patch.dict(os.environ, {"ALLOW_JARGON_HOOKS": "true"}):
            self.assertEqual(hook_guard.find_jargon("을목 여자 특징"), [])

    def test_fallbacks_are_clean(self):
        for title, hook in hook_guard.PLAIN_FALLBACKS:
            self.assertEqual(hook_guard.find_jargon(title + hook), [])
            self.assertLessEqual(len(title), 22)


class EnforcePlainTest(unittest.TestCase):
    def test_noop_when_clean(self):
        llm = mock.Mock()
        out, rem = hook_guard.enforce_plain({"title": "연락 끊는 이유"}, llm=llm)
        llm.assert_not_called()
        self.assertEqual((out, rem), ({"title": "연락 끊는 이유"}, []))

    def test_rewrites_only_bad_fields(self):
        llm = mock.Mock(return_value={"title": "참다가 한 번에 터지는 사람"})
        out, rem = hook_guard.enforce_plain({"title": "을목 여자 특징", "hook": "깨끗한 훅"}, llm=llm)
        self.assertEqual(out["title"], "참다가 한 번에 터지는 사람")
        self.assertEqual(out["hook"], "깨끗한 훅")
        self.assertEqual(rem, [])

    def test_rewrite_still_jargon_is_reported(self):
        llm = mock.Mock(return_value={"title": "병화 남자 특징"})
        out, rem = hook_guard.enforce_plain({"title": "을목 여자 특징"}, llm=llm)
        self.assertEqual(rem, ["title"])

    def test_llm_failure_does_not_raise(self):
        llm = mock.Mock(side_effect=RuntimeError("quota"))
        out, rem = hook_guard.enforce_plain({"title": "을목 여자 특징"}, llm=llm)
        self.assertEqual(rem, ["title"])


class PlannerGuardTest(unittest.TestCase):
    def test_viral_seed_patterns_are_jargon_free(self):
        random.seed(7)
        for pillar in ("viral_checklist", "viral_fakeout", "viral_pov", "viral_mystery", "viral_balance"):
            for _ in range(60):
                pat = tp._seed_spec("SAJU", [], pillar=pillar)["pattern"]
                self.assertEqual(hook_guard.find_jargon(pat), [], f"{pillar}: {pat}")

    def test_apply_plain_without_llm_falls_back_and_aligns_topic(self):
        opt = {"title": "을목 여자 특징? 이거 모르면", "hook": "을목 여자라면 끝까지 보세요", "topic": "을목 여자 특징"}
        out = tp._apply_plain(opt, use_llm=False)
        self.assertEqual(hook_guard.find_jargon(out["title"] + out["hook"]), [])
        self.assertNotIn("을목", out["topic"].split("(")[0])  # 제목과 어긋나지 않게 주제도 교체

    def test_apply_plain_uses_llm_rewrite_and_keeps_topic(self):
        opt = {"title": "을목 여자 특징", "hook": "깨끗한 훅", "topic": "을목 여자 특징 (근거: 을목)"}
        with mock.patch.object(hook_guard, "_default_llm", return_value={"title": "참다가 한 번에 터지는 사람"}):
            out = tp._apply_plain(opt)
        self.assertEqual(out["title"], "참다가 한 번에 터지는 사람")
        self.assertIn("을목", out["topic"])  # 사주 근거는 본문용으로 유지

    def test_clean_option_untouched(self):
        opt = {"title": "착한 사람의 이중성", "hook": "훅", "topic": "t"}
        self.assertEqual(tp._apply_plain(dict(opt)), opt)

    def test_fallback_option_is_always_clean(self):
        random.seed(3)
        for pillar in tp.PILLAR_WEIGHTS:
            opt = tp._fallback_option(tp._seed_spec("SAJU", [], pillar=pillar))
            self.assertEqual(hook_guard.find_jargon(opt["title"] + opt["hook"]), [], pillar)


class ScriptGuardTest(unittest.TestCase):
    def test_script_title_hook_scene1_rewritten(self):
        s = _script("을목 여자 특징", "을목이라면 보세요", "을목 여자는 카톡 답장이 늦어요.")
        llm_out = {"title": "카톡 답장이 늦는 사람", "hook": "답장 늦는 사람 속마음", "scene1": "카톡 답장이 늦는 사람, 이유 있어요."}
        with mock.patch.object(hook_guard, "_default_llm", return_value=llm_out):
            _enforce_plain_hook(s, "을목 카톡")
        self.assertEqual(s.title, "카톡 답장이 늦는 사람")
        self.assertEqual(s.scenes[0].narration, "카톡 답장이 늦는 사람, 이유 있어요.")

    def test_script_fallback_when_llm_fails(self):
        s = _script("도화살 특징", "도화살이면 보세요", "도화살 있으면 이래요.")
        with mock.patch.object(hook_guard, "_default_llm", side_effect=RuntimeError("x")):
            _enforce_plain_hook(s)
        self.assertEqual(hook_guard.find_jargon(s.title + s.hook), [])
        self.assertIn("도화살", s.scenes[0].narration)  # 씬 1은 흐름 보존(경고만)

    def test_clean_script_untouched_no_llm_call(self):
        s = _script("착한 사람의 이중성", "훅", "착한 사람이 연락 끊는 이유.")
        with mock.patch.object(hook_guard, "_default_llm") as m:
            _enforce_plain_hook(s)
        m.assert_not_called()


if __name__ == "__main__":
    unittest.main()
