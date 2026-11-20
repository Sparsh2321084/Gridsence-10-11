import unittest

import pandas as pd
from fastapi import HTTPException

from Web.Backend.grid_metrics import (
    TARGETS,
    build_ramp_metrics,
    calculate_reserve_dispatch,
    classify_ramp,
    estimate_thermal_coal_burn,
    load_grid_norms,
)
from Web.Backend.main import _normalize_ppa_schedule


class GridMetricTests(unittest.TestCase):
    def test_coal_estimate_uses_seasonal_share_and_block_energy(self) -> None:
        norms = load_grid_norms()["thermal_coal_burn"]
        timestamps = pd.DatetimeIndex(["2026-07-01 12:00", "2026-08-01 12:00"])

        blocks, total = estimate_thermal_coal_burn(
            [100.0, 100.0],
            timestamps,
            interval_minutes=15,
            coal_norms=norms,
        )

        self.assertAlmostEqual(blocks[0]["energy_mwh"], 25.0)
        self.assertAlmostEqual(blocks[0]["estimated_coal_burn_tonnes"], 11.05)
        self.assertAlmostEqual(blocks[1]["estimated_coal_burn_tonnes"], 13.0)
        self.assertAlmostEqual(total["estimated_coal_burn_tonnes"], 24.05)
        self.assertAlmostEqual(total["thermal_mix_share"], 0.74)

    def test_ramp_severity_threshold_boundaries(self) -> None:
        self.assertEqual(classify_ramp(74.99, 75.0, 100.0), "NORMAL")
        self.assertEqual(classify_ramp(75.0, 75.0, 100.0), "MODERATE")
        self.assertEqual(classify_ramp(99.99, 75.0, 100.0), "MODERATE")
        self.assertEqual(classify_ramp(100.0, 75.0, 100.0), "SEVERE")

    def test_first_ramp_is_unavailable_without_adjacent_predecessor(self) -> None:
        forecast = pd.DataFrame(
            {target: [110.0, 125.0] for target in TARGETS},
            index=pd.date_range("2026-11-20 00:00", periods=2, freq="15min"),
        )
        thresholds = {target: {"p75": 10.0, "p95": 20.0} for target in TARGETS}
        previous_values = {target: 100.0 for target in TARGETS}

        blocks, summary = build_ramp_metrics(
            forecast,
            previous_values,
            pd.Timestamp("2026-11-19 23:30"),
            thresholds,
        )

        self.assertIsNone(blocks[0]["delhi_total_mw"]["absolute_change_mw"])
        self.assertIsNone(blocks[0]["delhi_total_mw"]["severity"])
        self.assertEqual(blocks[1]["delhi_total_mw"]["absolute_change_mw"], 15.0)
        self.assertEqual(summary["delhi_total_mw"]["severity"], "MODERATE")

    def test_reserve_and_ppa_dispatch_math(self) -> None:
        result = calculate_reserve_dispatch(100.0, 120.0, 90.0, 0.05)

        self.assertEqual(result["required_reserve_mw"], 20.0)
        self.assertEqual(result["net_position_mw"], 10.0)
        self.assertEqual(result["iex_dam_action"], "BUY")
        self.assertEqual(result["rtm_reserve_buffer_mw"], 20.0)

    def test_ppa_schedule_accepts_scalar_or_exact_horizon(self) -> None:
        self.assertEqual(_normalize_ppa_schedule("50", 3), [50.0, 50.0, 50.0])
        self.assertEqual(_normalize_ppa_schedule("[1,2,3]", 3), [1.0, 2.0, 3.0])

    def test_ppa_schedule_rejects_wrong_length_and_negative_values(self) -> None:
        with self.assertRaises(HTTPException):
            _normalize_ppa_schedule("[1,2]", 3)
        with self.assertRaises(HTTPException):
            _normalize_ppa_schedule(-1.0, 3)


if __name__ == "__main__":
    unittest.main()
