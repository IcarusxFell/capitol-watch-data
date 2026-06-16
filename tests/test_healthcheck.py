import datetime as dt
import unittest

from scraper.healthcheck import evaluate

NOW = dt.datetime(2026, 6, 16, 18, 0, tzinfo=dt.timezone.utc)
HEALTHY = {"updated_utc": "2026-06-16T16:55:47+00:00", "counts": {"house": 9605, "senate": 1472}}


class TestHealthCheck(unittest.TestCase):
    def test_healthy(self):
        self.assertEqual(evaluate(HEALTHY, NOW), [])

    def test_stale(self):
        later = dt.datetime(2026, 6, 20, 0, 0, tzinfo=dt.timezone.utc)
        problems = evaluate(HEALTHY, later)
        self.assertTrue(any("stale" in p for p in problems))

    def test_low_counts(self):
        meta = {"updated_utc": "2026-06-16T16:55:47+00:00", "counts": {"house": 5, "senate": 1}}
        self.assertEqual(len(evaluate(meta, NOW)), 2)

    def test_missing_timestamp(self):
        self.assertEqual(len(evaluate({"counts": {"house": 9605, "senate": 1472}}, NOW)), 1)


if __name__ == "__main__":
    unittest.main()
