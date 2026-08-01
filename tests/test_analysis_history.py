import os
import tempfile
import unittest

import analysis_history


class TestAnalysisHistory(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        analysis_history._db.initialize(analysis_history.SqliteDatabase(
            os.path.join(self._tmp, "test_history.db")))
        analysis_history.ensure_table()

    def tearDown(self):
        analysis_history._db.close()
        os.remove(os.path.join(self._tmp, "test_history.db"))

    def _record(self, **over):
        base = dict(
            ticker="ONDS", score=72.5, veredicto="Compra en retroceso a zona OB",
            action="BUY", precio=99.25, rr=2.1, direccion="bull",
            estado_onda="FORMING_WAVE_3", deviation=15.0, period="2 Y", bar_size="1 day",
        )
        base.update(over)
        return analysis_history.record_analysis(**base)

    def test_record_and_recent_desc_order(self):
        self._record(ticker="ONDS", score=60)
        self._record(ticker="AAA", score=90)
        recs = analysis_history.recent_analyses()
        self.assertEqual(len(recs), 2)
        self.assertEqual(recs[0]["ticker"], "AAA")
        self.assertIn("id", recs[0])
        self.assertIn("timestamp", recs[0])

    def test_load_analysis_roundtrip(self):
        rid = self._record(ticker="XYZ", score=55.5, rr=1.3)
        rec = analysis_history.load_analysis(rid)
        self.assertIsNotNone(rec)
        self.assertEqual(rec["ticker"], "XYZ")
        self.assertEqual(rec["score"], 55.5)
        self.assertEqual(rec["action"], "BUY")
        self.assertEqual(rec["deviation"], 15.0)
        self.assertEqual(rec["period"], "2 Y")

    def test_load_missing_returns_none(self):
        self.assertIsNone(analysis_history.load_analysis(999999))

    def test_recent_limit(self):
        for i in range(5):
            self._record(ticker=f"T{i}", score=i)
        recs = analysis_history.recent_analyses(limit=2)
        self.assertEqual(len(recs), 2)


if __name__ == "__main__":
    unittest.main()
