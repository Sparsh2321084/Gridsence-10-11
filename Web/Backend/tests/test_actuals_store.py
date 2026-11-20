import tempfile
import unittest
from pathlib import Path

import pandas as pd

from Web.Backend.actuals_store import ActualLoadStore, InferenceHistoryError


def reading(timestamp: str, **overrides: float) -> dict[str, object]:
    values: dict[str, object] = {
        "timestamp": timestamp,
        "brpl_mw": 1_800.0,
        "tpddl_mw": 1_000.0,
        "bypl_mw": 700.0,
        "ndmc_mw": 120.0,
        "mes_mw": 20.0,
        "railways_mw": 10.0,
        "delhi_total_mw": 3_650.0,
    }
    values.update(overrides)
    return values


class ActualLoadStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = ActualLoadStore(Path(self.temp_dir.name) / "actuals.sqlite3")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_duplicate_revision_keeps_valid_reading_over_spike(self) -> None:
        self.store.ingest_frame(
            pd.DataFrame(
                [
                    reading("2026-11-20 00:00:00"),
                    reading("2026-11-20 00:00:00", mes_mw=255.0),
                ]
            ),
            source="sldc_live_portal",
        )

        values = self.store.get_valid_values("2026-11-20 00:00:00")
        self.assertEqual(values["mes_mw"], 20.0)

    def test_mu_unit_conversion_and_spike_quality(self) -> None:
        mu_rows = [
            reading(
                f"2026-11-20 00:{minute:02d}:00",
                brpl_mw=0.45,
                tpddl_mw=0.25,
                bypl_mw=0.175,
                ndmc_mw=0.03,
                mes_mw=0.005,
                railways_mw=0.0025,
                delhi_total_mw=0.9125,
            )
            for minute in (0, 15, 30, 45)
        ]
        self.store.ingest_frame(pd.DataFrame(mu_rows), source="sldc_abt_weekly", unit="MU")
        converted = self.store.get_valid_values("2026-11-20 00:00:00")
        self.assertAlmostEqual(converted["delhi_total_mw"], 3_650.0)

        self.store.ingest_frame(
            pd.DataFrame([reading("2026-11-20 01:00:00", mes_mw=255.0)]),
            source="sldc_live_portal",
        )
        self.assertIsNone(self.store.get_valid_values("2026-11-20 01:00:00")["mes_mw"])
        with self.store._connect() as connection:
            row = connection.execute(
                "SELECT quality_flag FROM actual_load_15m WHERE timestamp = ? AND entity = 'mes_mw'",
                ("2026-11-20T01:00:00",),
            ).fetchone()
        self.assertEqual(row["quality_flag"], "SUSPECT_SPIKE")

    def test_three_hour_outage_is_stale_and_missing_actuals_stay_null(self) -> None:
        now = pd.Timestamp("2026-11-20 12:00:00", tz="Asia/Kolkata")
        latest = now.tz_localize(None) - pd.Timedelta(hours=3, minutes=15)
        timestamps = pd.date_range(end=latest, periods=672, freq="15min")
        self.store.ingest_frame(
            pd.DataFrame(
                [reading(timestamp.strftime("%Y-%m-%d %H:%M:%S")) for timestamp in timestamps]
            ),
            source="sldc_live_portal",
        )
        missing_start = latest + pd.Timedelta(minutes=15)
        missing_end = now.tz_localize(None) - pd.Timedelta(minutes=15)
        self.store.record_missing(missing_start, missing_end, source="sldc_live_portal")

        freshness = self.store.data_freshness(now=now)
        self.assertEqual(freshness["forecast_mode"], "STALE")
        missing = self.store.get_valid_values(missing_start)
        self.assertTrue(all(value is None for value in missing.values()))

    def test_september_baseline_is_replayed(self) -> None:
        self.store.ingest_frame(
            pd.DataFrame([reading("2026-09-27 23:45:00")]),
            source="historical_parquet",
        )

        freshness = self.store.data_freshness(
            now=pd.Timestamp("2026-11-20 03:00:00", tz="Asia/Kolkata")
        )
        self.assertEqual(freshness["forecast_mode"], "REPLAYED")
        self.assertEqual(freshness["latest_actual_timestamp"], "2026-09-27T23:45:00+05:30")

    def test_live_requires_recent_complete_data_and_sufficient_coverage(self) -> None:
        now = pd.Timestamp("2026-11-20 12:00:00", tz="Asia/Kolkata")
        latest = now.tz_localize(None) - pd.Timedelta(minutes=15)
        timestamps = pd.date_range(end=latest, periods=672, freq="15min")
        self.store.ingest_frame(
            pd.DataFrame(
                [reading(timestamp.strftime("%Y-%m-%d %H:%M:%S")) for timestamp in timestamps]
            ),
            source="sldc_live_portal",
        )

        freshness = self.store.data_freshness(now=now)
        self.assertEqual(freshness["forecast_mode"], "LIVE")
        self.assertGreaterEqual(freshness["valid_blocks_percent"], 95)

    def test_unreconciled_sum_is_not_treated_as_valid(self) -> None:
        self.store.ingest_frame(
            pd.DataFrame([reading("2026-11-20 00:00:00", delhi_total_mw=4_000.0)]),
            source="sldc_live_portal",
        )

        values = self.store.get_valid_values("2026-11-20 00:00:00")
        self.assertTrue(all(value is None for value in values.values()))
        with self.store._connect() as connection:
            row = connection.execute(
                "SELECT quality_flag FROM actual_load_15m WHERE timestamp = ? AND entity = 'delhi_total_mw'",
                ("2026-11-20T00:00:00",),
            ).fetchone()
        self.assertEqual(row["quality_flag"], "MISMATCH_SUM")

    def test_no_valid_fallback_reports_unavailable(self) -> None:
        freshness = self.store.data_freshness(
            now=pd.Timestamp("2026-11-20 03:00:00", tz="Asia/Kolkata")
        )
        self.assertEqual(freshness["forecast_mode"], "UNAVAILABLE")
        self.assertIsNone(freshness["latest_actual_timestamp"])

    def test_only_short_internal_gaps_are_interpolated_for_inference(self) -> None:
        start = pd.Timestamp("2026-11-20 00:00:00")
        rows = []
        for offset in range(8):
            if offset not in (3, 4):
                timestamp = start + pd.Timedelta(minutes=15 * offset)
                rows.append(reading(timestamp.strftime("%Y-%m-%d %H:%M:%S")))
        self.store.ingest_frame(pd.DataFrame(rows), source="sldc_live_portal")

        inference, filled_blocks = self.store.inference_input(start, periods=8)
        self.assertEqual(filled_blocks, 2)
        self.assertFalse(inference.isna().any().any())
        self.assertIsNone(self.store.get_valid_values(start + pd.Timedelta(minutes=45))["brpl_mw"])

        long_gap_store = ActualLoadStore(Path(self.temp_dir.name) / "long-gap.sqlite3")
        long_gap_store.ingest_frame(
            pd.DataFrame(
                [
                    reading((start + pd.Timedelta(minutes=15 * offset)).strftime("%Y-%m-%d %H:%M:%S"))
                    for offset in (0, 1, 7)
                ]
            ),
            source="sldc_live_portal",
        )
        with self.assertRaises(InferenceHistoryError):
            long_gap_store.inference_input(start, periods=8)

    def test_rejects_misaligned_timestamps(self) -> None:
        with self.assertRaisesRegex(ValueError, "not aligned"):
            self.store.ingest_frame(
                pd.DataFrame([reading("2026-11-20 00:01:00")]),
                source="sldc_live_portal",
            )

    def test_mu_auto_detection_requires_a_batch_of_low_values(self) -> None:
        rows = [
            reading(
                f"2026-11-20 02:{minute:02d}:00",
                brpl_mw=0.45,
                tpddl_mw=0.25,
                bypl_mw=0.175,
                ndmc_mw=0.03,
                mes_mw=0.005,
                railways_mw=0.0025,
                delhi_total_mw=0.9125,
            )
            for minute in (0, 15, 30, 45)
        ]
        self.store.ingest_frame(pd.DataFrame(rows), source="sldc_abt_weekly", unit="AUTO")
        values = self.store.get_valid_values("2026-11-20 02:00:00")
        self.assertAlmostEqual(values["delhi_total_mw"], 3_650.0)


if __name__ == "__main__":
    unittest.main()
