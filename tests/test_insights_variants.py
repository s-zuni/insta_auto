import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from pipeline import insights


class VariantRecordingTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig = insights.DB_PATH
        insights.DB_PATH = Path(self._tmp.name) / "state.db"

    def tearDown(self):
        insights.DB_PATH = self._orig
        self._tmp.cleanup()

    def _score(self, media_id, score, window=72):
        conn = insights._conn()
        with conn:
            conn.execute("INSERT INTO post_insights VALUES (?,?,?,?,?)",
                         (media_id, window, "2026-01-01", json.dumps({"reach": 100}), score))
        conn.close()

    def test_record_and_read_variant(self):
        insights.record_post("m1", "reel", series="SAJU", title="t", variant={"scenes": 9, "share_cta": True})
        conn = insights._conn()
        row = conn.execute("SELECT variant_json FROM published_posts WHERE media_id='m1'").fetchone()
        conn.close()
        self.assertEqual(json.loads(row["variant_json"]), {"scenes": 9, "share_cta": True})

    def test_variant_defaults_to_empty(self):
        insights.record_post("m2", "reel")
        conn = insights._conn()
        row = conn.execute("SELECT variant_json FROM published_posts WHERE media_id='m2'").fetchone()
        conn.close()
        self.assertEqual(json.loads(row["variant_json"]), {})

    def test_empty_media_id_ignored(self):
        insights.record_post("", "reel")
        conn = insights._conn()
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM published_posts").fetchone()[0], 0)
        conn.close()

    def test_migrates_old_db_without_column(self):
        old = Path(self._tmp.name) / "old.db"
        c = sqlite3.connect(old)
        c.execute("""CREATE TABLE published_posts (media_id TEXT PRIMARY KEY, format TEXT, series TEXT, mbti TEXT,
                     topic TEXT, title TEXT, hook TEXT, trend_hint TEXT, permalink TEXT, published_at TEXT)""")
        c.execute("INSERT INTO published_posts VALUES ('old','reel','SAJU','','','t','h','','','2026-01-01')")
        c.commit()
        c.close()
        insights.DB_PATH = old
        insights.record_post("new", "reel", variant={"x": 1})
        conn = insights._conn()
        cols = {r[1] for r in conn.execute("PRAGMA table_info(published_posts)")}
        self.assertIn("variant_json", cols)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM published_posts").fetchone()[0], 2)
        conn.close()

    def test_variant_summary_groups_and_skips_missing(self):
        for mid, share, score in (("a", True, 10.0), ("b", True, 6.0), ("c", False, 4.0)):
            insights.record_post(mid, "reel", variant={"share_cta": share})
            self._score(mid, score)
        insights.record_post("legacy", "reel")  # 구버전 게시물: 변형 정보 없음 -> 제외
        self._score("legacy", 99.0)
        summ = insights.variant_summary("share_cta")
        self.assertEqual(summ["True"], {"avg_score": 8.0, "n": 2})
        self.assertEqual(summ["False"], {"avg_score": 4.0, "n": 1})
        self.assertNotIn("legacy", json.dumps(summ))

    def test_weekly_report_includes_ab_block_only_with_two_variants(self):
        for mid, share, score in (("a", True, 10.0), ("b", False, 4.0)):
            insights.record_post(mid, "reel", series="SAJU", title="제목", variant={"share_cta": share})
            self._score(mid, score)
        self.assertIn("A/B", insights.weekly_report())

        for_one = Path(self._tmp.name) / "one.db"
        insights.DB_PATH = for_one
        insights.record_post("z", "reel", series="SAJU", title="제목", variant={"share_cta": True})
        self._score("z", 3.0)
        self.assertNotIn("A/B", insights.weekly_report())


if __name__ == "__main__":
    unittest.main()
