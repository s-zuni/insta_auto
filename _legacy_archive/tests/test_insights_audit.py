import unittest
from unittest import mock

from pipeline import insights


class ClassifyHookTest(unittest.TestCase):
    def test_jargon_hook_flagged(self):
        r = insights.classify_hook("ESFP 병화 여자, 요즘 데이트 신청 폭주하는 이유?")
        self.assertTrue(r["hook_jargon"])
        self.assertTrue(r["hook_has_mbti"])
        self.assertEqual(r["hook_formula"], "identity")

    def test_plain_hook_not_jargon(self):
        r = insights.classify_hook("다 퍼주는 사람이 제일 먼저 연락 끊는 이유")
        self.assertFalse(r["hook_jargon"])

    def test_checklist(self):
        self.assertEqual(insights.classify_hook("여기서 3개 이상 맞으면 소름")["hook_formula"], "checklist")

    def test_empty(self):
        r = insights.classify_hook("")
        self.assertEqual((r["hook_formula"], r["hook_chars"]), ("other", 0))


class AuditRowsTest(unittest.TestCase):
    def test_outlier_multiple_uses_median(self):
        media = [{"id": str(i), "caption": f"h{i}", "media_product_type": "REELS"} for i in range(4)]
        views = {"0": 1510, "1": 189, "2": 130, "3": 119}

        def fake_metrics(mid, access_token=None):
            return {"views": views[mid], "reach": views[mid] - 10, "shares": 1, "follows": 0,
                    "ig_reels_avg_watch_time": 4000}

        with mock.patch.object(insights, "fetch_account_media", return_value=media), \
                mock.patch.object(insights, "fetch_media_insights", side_effect=fake_metrics):
            rows = insights.audit_rows()
        self.assertEqual(rows[0]["id"], "0")
        self.assertAlmostEqual(rows[0]["outlier"], 9.5, places=1)  # 1510 / median(159.5)
        self.assertEqual(rows[0]["avg_watch_s"], 4.0)


if __name__ == "__main__":
    unittest.main()
