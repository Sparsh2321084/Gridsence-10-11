import unittest
from unittest.mock import patch

import pandas as pd

from Web.Backend.main import AssetSimulationRequest, post_simulate_assets
from Web.Backend.asset_simulators import (
    load_assets_config,
    simulate_bess_schedule,
    simulate_corridor_stress,
    simulate_demand_response,
    simulate_ev_valley_fill,
)


class AssetSimulatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_assets_config()
        self.index = pd.date_range("2026-11-20", periods=96, freq="15min")
        p50 = [7_000.0] * len(self.index)
        p95 = [7_200.0] * len(self.index)
        for position, timestamp in enumerate(self.index):
            if 18 <= timestamp.hour <= 22:
                p50[position] = 7_800.0
                p95[position] = 8_100.0
        self.forecast = pd.DataFrame(
            {
                "delhi_total_mw": p50,
                "delhi_total_mw_p95": p95,
                "temperature_2m": [50.0] * len(self.index),
            },
            index=self.index,
        )

    def test_ieee_738_derating_and_corridor_severity(self) -> None:
        result = simulate_corridor_stress(
            self.forecast,
            "delhi_total_mw",
            self.config,
            capacity_override_mw=1_000.0,
        )
        first_block = result["blocks"][0]

        self.assertAlmostEqual(first_block["derated_limit_mw"], 920.0)
        self.assertAlmostEqual(first_block["utilization_pct"], 7_200 / 920 * 100)
        self.assertEqual(first_block["status"], "N1_THERMAL_RISK")

    def test_corridor_severity_boundaries_and_safe_maintenance_window(self) -> None:
        forecast = pd.DataFrame(
            {
                "delhi_total_mw_p95": [849.0, 850.0, 950.0, 951.0, 1_000.0],
                "temperature_2m": [40.0] * 5,
            },
            index=pd.date_range("2026-11-20 00:00", periods=5, freq="15min"),
        )
        result = simulate_corridor_stress(
            forecast,
            "delhi_total_mw",
            self.config,
            capacity_override_mw=1_000.0,
        )

        self.assertEqual(
            [block["status"] for block in result["blocks"][:4]],
            ["NORMAL", "ELEVATED_SAG", "ELEVATED_SAG", "N1_THERMAL_RISK"],
        )
        self.assertFalse(result["blocks"][0]["safe_maintenance_window"])
        maintenance = simulate_corridor_stress(
            forecast.iloc[[-1]],
            "delhi_total_mw",
            self.config,
            capacity_override_mw=2_000.0,
        )
        self.assertTrue(maintenance["blocks"][0]["safe_maintenance_window"])

    def test_bess_schedule_respects_soc_and_power_limits(self) -> None:
        result = simulate_bess_schedule(
            self.forecast,
            "delhi_total_mw",
            self.config,
        )

        self.assertTrue(any(block["bess_mw"] < 0 for block in result["blocks"]))
        self.assertTrue(any(block["bess_mw"] > 0 for block in result["blocks"]))
        self.assertTrue(all(15.0 - 1e-8 <= block["soc_pct"] <= 95.0 + 1e-8 for block in result["blocks"]))
        self.assertTrue(all(abs(block["bess_mw"]) <= 20.0 + 1e-8 for block in result["blocks"]))

    def test_ev_water_filling_conserves_target_energy(self) -> None:
        result = simulate_ev_valley_fill(
            self.forecast,
            "delhi_total_mw",
            self.config,
        )
        active = [block for block in result["blocks"] if block["charging_mw"] > 0]

        self.assertAlmostEqual(result["scheduled_energy_mwh"], 65.0, places=7)
        self.assertAlmostEqual(
            sum(block["energy_mwh"] for block in result["blocks"]),
            65.0,
            places=7,
        )
        self.assertTrue(all(block["valley_window"] for block in active))
        self.assertTrue(all(block["charging_mw"] <= 90.0 for block in active))

    def test_demand_response_trigger_and_precooling_window(self) -> None:
        result = simulate_demand_response(
            self.forecast,
            "delhi_total_mw",
            self.config,
        )

        self.assertTrue(result["triggered"])
        self.assertEqual(result["mw_shaved"], 22.5)
        peak = pd.Timestamp(result["peak_timestamp"])
        precool_start = pd.Timestamp(result["precooling_window"]["start"])
        self.assertEqual(peak - precool_start, pd.Timedelta(hours=2))
        self.assertTrue(result["active_curtailment_blocks"])

    def test_demand_response_does_not_trigger_at_exact_threshold(self) -> None:
        flat = self.forecast.copy()
        flat["delhi_total_mw_p95"] = 7_800.0

        result = simulate_demand_response(
            flat,
            "delhi_total_mw",
            self.config,
        )

        self.assertFalse(result["triggered"])
        self.assertEqual(result["active_curtailment_blocks"], [])
        self.assertIsNone(result["precooling_window"])

    def test_simulation_endpoint_accepts_profile_overrides(self) -> None:
        rows = []
        for timestamp in self.index:
            row = {
                "timestamp": timestamp.isoformat() + "+05:30",
                "weather": {"temperature_2m": 50.0},
            }
            for target in (
                "brpl_mw",
                "tpddl_mw",
                "bypl_mw",
                "ndmc_mw",
                "mes_mw",
                "railways_mw",
                "delhi_total_mw",
            ):
                row[target] = float(self.forecast.iloc[0]["delhi_total_mw"])
                row[f"{target}_p95"] = float(self.forecast.iloc[0]["delhi_total_mw_p95"])
            rows.append(row)
        forecast_payload = {
            "generated_at": "2026-11-20T00:00:00+05:30",
            "data_freshness": {"forecast_mode": "REPLAYED"},
            "model_input_source": "HISTORICAL_BASELINE",
            "forecast": rows,
        }
        request = AssetSimulationRequest(
            target="delhi_total_mw",
            bess={"power_mw": 10.0},
            ev_fleet={"target_energy_mwh": 20.0},
            demand_response={"threshold_mw": 7_000.0},
        )

        with patch("Web.Backend.main._build_forecast", return_value=forecast_payload):
            response = post_simulate_assets(request)

        self.assertEqual(response["simulations"]["bess"]["profile"]["power_mw"], 10.0)
        self.assertAlmostEqual(
            response["simulations"]["ev_fleet"]["scheduled_energy_mwh"],
            20.0,
            places=7,
        )
        self.assertTrue(response["simulations"]["demand_response"]["triggered"])


if __name__ == "__main__":
    unittest.main()
