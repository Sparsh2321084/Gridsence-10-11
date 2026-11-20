import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

import pandas as pd

from Web.Backend.abt_import import ingest_abt_week, read_abt_week, scan_abt_folder
from Web.Backend.actuals_store import ActualLoadStore
from Web.Backend.main import (
    WEATHER_VARS,
    build_baseline_future_exog,
    build_live_weather_exog,
    fetch_open_meteo_weather,
)
from Web.Backend import main as forecast_api


EXOG_COLUMNS = [
    "temperature_2m",
    "relative_humidity_2m",
    "dew_point_2m",
    "apparent_temperature",
    "precipitation",
    "rain",
    "cloud_cover",
    "wind_speed_10m",
    "shortwave_radiation",
    "cdd_24",
    "hdd_18",
    "temp_roll_3h",
    "temp_roll_24h",
    "temp_roll_72h",
    "temp_max_24h",
    "temp_min_24h",
    "apparent_temp_roll_24h",
    "block_of_day",
    "day_of_week",
    "is_weekend",
    "sin_block",
    "cos_block",
    "sin_dow",
    "cos_dow",
    "sin_doy",
    "cos_doy",
    "is_holiday",
    "is_non_working_day",
    "is_lockdown",
]


def workbook_rows(timestamps: pd.DatetimeIndex) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Date": timestamps.date,
            "Block": timestamps.hour * 4 + timestamps.minute // 15 + 1,
            "BILL BRPL": 0.45,
            "BILL TPDDL/NDPL": 0.25,
            "BILL BYPL": 0.175,
            "BILL NDMC": 0.03,
            "MES": 0.005,
            "NORTHERN RAILWAY": 0.0025,
        }
    )


class AbtImporterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = ActualLoadStore(Path(self.temp_dir.name) / "actuals.sqlite3")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_weekly_workbook_backfills_stale_store_to_live(self) -> None:
        now = pd.Timestamp("2026-11-20 00:00:00", tz="Asia/Kolkata")
        previous = pd.Timestamp("2026-11-17 00:00:00")
        self.store.ingest_frame(
            pd.DataFrame(
                [
                    {
                        "timestamp": previous,
                        "brpl_mw": 1_800.0,
                        "tpddl_mw": 1_000.0,
                        "bypl_mw": 700.0,
                        "ndmc_mw": 120.0,
                        "mes_mw": 20.0,
                        "railways_mw": 10.0,
                        "delhi_total_mw": 3_650.0,
                    }
                ]
            ),
            source="sldc_live_snapshot",
        )
        self.assertEqual(self.store.data_freshness(now)["forecast_mode"], "STALE")

        timestamps = pd.date_range("2026-11-13", periods=672, freq="15min")
        workbook = Path(self.temp_dir.name) / "abt_week.xlsx"
        workbook_rows(timestamps).drop(index=8).to_excel(
            workbook,
            index=False,
            sheet_name="ABT",
        )

        self.assertEqual(read_abt_week(workbook).shape[0], 672)
        self.assertEqual(ingest_abt_week(self.store, workbook), 672)
        self.assertEqual(self.store.data_freshness(now)["forecast_mode"], "LIVE")
        values = self.store.get_valid_values("2026-11-13 00:00:00")
        self.assertAlmostEqual(values["brpl_mw"], 1_800.0)
        self.assertAlmostEqual(values["delhi_total_mw"], 3_650.0)
        missing = self.store.get_valid_values("2026-11-13 02:00:00")
        self.assertTrue(all(value is None for value in missing.values()))

    def test_inbox_scanner_imports_new_workbooks_once(self) -> None:
        inbox = Path(self.temp_dir.name) / "inbox"
        inbox.mkdir()
        workbook = inbox / "week.xlsx"
        timestamps = pd.date_range("2026-11-13", periods=672, freq="15min")
        workbook_rows(timestamps).to_excel(workbook, index=False)

        imported, failures = scan_abt_folder(self.store, inbox)
        self.assertEqual(imported, [workbook])
        self.assertEqual(failures, [])
        imported_again, failures_again = scan_abt_folder(self.store, inbox)
        self.assertEqual(imported_again, [])
        self.assertEqual(failures_again, [])

    def test_import_materializes_gap_after_historical_baseline(self) -> None:
        self.store.ingest_frame(
            pd.DataFrame(
                [
                    {
                        "timestamp": "2026-09-27 23:45:00",
                        "brpl_mw": 1_800.0,
                        "tpddl_mw": 1_000.0,
                        "bypl_mw": 700.0,
                        "ndmc_mw": 120.0,
                        "mes_mw": 20.0,
                        "railways_mw": 10.0,
                        "delhi_total_mw": 3_650.0,
                    }
                ]
            ),
            source="historical_parquet",
        )
        workbook = Path(self.temp_dir.name) / "week.xlsx"
        timestamps = pd.date_range("2026-11-13", periods=672, freq="15min")
        workbook_rows(timestamps).to_excel(workbook, index=False)

        ingest_abt_week(self.store, workbook)

        with self.store._connect() as connection:
            row = connection.execute(
                "SELECT mw, quality_flag FROM actual_load_15m WHERE timestamp = ? AND entity = ?",
                ("2026-09-28T00:00:00", "brpl_mw"),
            ).fetchone()
        self.assertIsNone(row["mw"])
        self.assertEqual(row["quality_flag"], "MISSING")


class LiveWeatherTests(unittest.TestCase):
    def test_open_meteo_request_uses_eight_past_and_two_forecast_days(self) -> None:
        hourly = {"time": ["2026-11-20T00:00"]}
        hourly.update({column: [1.0] for column in WEATHER_VARS})
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(
            {"hourly": hourly}
        ).encode("utf-8")
        with patch("Web.Backend.main.urllib.request.urlopen", return_value=response) as urlopen:
            result = fetch_open_meteo_weather()

        query = parse_qs(urlparse(urlopen.call_args.args[0].full_url).query)
        self.assertEqual(query["past_days"], ["8"])
        self.assertEqual(query["forecast_days"], ["2"])
        self.assertEqual(result.shape, (1, len(WEATHER_VARS)))

    def test_live_weather_assembles_model_history_and_forecast_features(self) -> None:
        hourly_index = pd.date_range("2026-11-11", "2026-11-22 23:00", freq="h")
        hourly = pd.DataFrame(index=hourly_index)
        for column in WEATHER_VARS:
            hourly[column] = 0.0
        hourly["temperature_2m"] = range(len(hourly))
        hourly["apparent_temperature"] = hourly["temperature_2m"] + 1.0
        history_index = pd.date_range("2026-11-13", periods=672, freq="15min")
        future = pd.date_range(history_index[-1] + pd.Timedelta(minutes=15), periods=96, freq="15min")

        x_hist, x_fut = build_live_weather_exog(
            hourly,
            history_index,
            future,
            EXOG_COLUMNS,
        )

        self.assertEqual(x_hist.shape, (672, 29))
        self.assertEqual(x_fut.shape, (96, 29))
        self.assertEqual(x_hist.columns.tolist(), EXOG_COLUMNS)
        self.assertFalse(x_hist.isna().any().any())
        self.assertFalse(x_fut.isna().any().any())
        self.assertGreater(
            float(x_fut["temperature_2m"].iloc[0]),
            float(x_hist["temperature_2m"].iloc[-1]),
        )

    def test_historical_fallback_builds_future_calendar_and_weather_features(self) -> None:
        timestamps = pd.date_range("2026-09-27 00:00", periods=96, freq="15min")
        dataset = pd.DataFrame({"timestamp": timestamps})
        for column in WEATHER_VARS:
            dataset[column] = 0.0
        dataset["temperature_2m"] = 24.0
        dataset["apparent_temperature"] = 25.0
        future = pd.date_range("2026-11-20 03:45", periods=96, freq="15min")

        x_future = build_baseline_future_exog(future, dataset, EXOG_COLUMNS)

        self.assertEqual(x_future.shape, (96, 29))
        self.assertEqual(x_future.index.tolist(), future.tolist())
        self.assertEqual(int(x_future.iloc[0]["block_of_day"]), 15)
        self.assertFalse(x_future.isna().any().any())


class CausalDriftTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = ActualLoadStore(Path(self.temp_dir.name) / "actuals.sqlite3")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_block_bias_uses_prior_days_and_excludes_current_day(self) -> None:
        actual_rows = []
        for day in pd.date_range("2026-11-13", periods=5, freq="D"):
            timestamps = pd.date_range(day, periods=96, freq="15min")
            for timestamp in timestamps:
                actual_rows.append(
                    {
                        "timestamp": timestamp,
                        "brpl_mw": 1_810.0,
                        "tpddl_mw": 1_000.0,
                        "bypl_mw": 700.0,
                        "ndmc_mw": 120.0,
                        "mes_mw": 20.0,
                        "railways_mw": 10.0,
                        "delhi_total_mw": 3_660.0,
                    }
                )
            predictions = pd.DataFrame(
                {
                    "brpl_mw": 1_800.0,
                    "tpddl_mw": 1_000.0,
                    "bypl_mw": 700.0,
                    "ndmc_mw": 120.0,
                    "mes_mw": 20.0,
                    "railways_mw": 10.0,
                    "delhi_total_mw": 3_650.0,
                },
                index=timestamps,
            )
            self.store.record_predictions(
                predictions,
                issued_at=day - pd.Timedelta(days=1),
            )
        current_timestamp = pd.Timestamp("2026-11-20 00:00:00")
        actual_rows.append(
            {
                "timestamp": current_timestamp,
                "brpl_mw": 2_500.0,
                "tpddl_mw": 1_000.0,
                "bypl_mw": 700.0,
                "ndmc_mw": 120.0,
                "mes_mw": 20.0,
                "railways_mw": 10.0,
                "delhi_total_mw": 4_350.0,
            }
        )
        self.store.record_predictions(
            pd.DataFrame(
                [
                    {
                        "brpl_mw": 1_800.0,
                        "tpddl_mw": 1_000.0,
                        "bypl_mw": 700.0,
                        "ndmc_mw": 120.0,
                        "mes_mw": 20.0,
                        "railways_mw": 10.0,
                        "delhi_total_mw": 3_650.0,
                    }
                ],
                index=[current_timestamp],
            ),
            issued_at=current_timestamp - pd.Timedelta(days=1),
        )
        self.store.ingest_frame(pd.DataFrame(actual_rows), source="sldc_abt_weekly")

        now = pd.Timestamp("2026-11-20 12:00:00", tz="Asia/Kolkata")
        future = pd.date_range("2026-11-20 00:00", periods=2, freq="15min")
        bias = self.store.recent_14d_block_bias(future, now=now)

        self.assertIsNotNone(bias)
        self.assertAlmostEqual(float(bias.iloc[0]["brpl_mw"]), 10.0)
        self.assertAlmostEqual(float(bias.iloc[0]["delhi_total_mw"]), 10.0)
        self.assertAlmostEqual(float(bias.iloc[1]["brpl_mw"]), 10.0)

    def test_bias_requires_five_matched_days(self) -> None:
        day = pd.Timestamp("2026-11-13")
        timestamps = pd.date_range(day, periods=96, freq="15min")
        actuals = [
            {
                "timestamp": timestamp,
                "brpl_mw": 1_810.0,
                "tpddl_mw": 1_000.0,
                "bypl_mw": 700.0,
                "ndmc_mw": 120.0,
                "mes_mw": 20.0,
                "railways_mw": 10.0,
                "delhi_total_mw": 3_660.0,
            }
            for timestamp in timestamps
        ]
        predictions = pd.DataFrame(
            {
                "brpl_mw": 1_800.0,
                "tpddl_mw": 1_000.0,
                "bypl_mw": 700.0,
                "ndmc_mw": 120.0,
                "mes_mw": 20.0,
                "railways_mw": 10.0,
                "delhi_total_mw": 3_650.0,
            },
            index=timestamps,
        )
        self.store.ingest_frame(pd.DataFrame(actuals), source="sldc_abt_weekly")
        self.store.record_predictions(predictions, issued_at=day - pd.Timedelta(days=1))

        bias = self.store.recent_14d_block_bias(
            pd.date_range("2026-11-20", periods=1, freq="15min"),
            now=pd.Timestamp("2026-11-20 12:00:00", tz="Asia/Kolkata"),
        )
        self.assertIsNone(bias)


class ForecastApiIntegrationTests(unittest.TestCase):
    @staticmethod
    def fixed_datetime_class() -> type[datetime]:
        class FixedDateTime(datetime):
            @classmethod
            def now(cls, tz: timezone | None = None) -> datetime:
                current = cls(
                    2026,
                    11,
                    20,
                    3,
                    39,
                    tzinfo=timezone(timedelta(hours=5, minutes=30)),
                )
                return current if tz is None else current.astimezone(tz)

        return FixedDateTime

    def test_sldc_poller_normalizes_timestamp_before_comparing_with_sqlite(self) -> None:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        dataset_path = root / "dataset.parquet"
        dataset_path.touch()
        store = ActualLoadStore(root / "poller.sqlite3")
        dataset = pd.DataFrame(
            [
                {
                    "timestamp": "2026-11-20 03:00:00",
                    "brpl_mw": 1_800.0,
                    "tpddl_mw": 1_000.0,
                    "bypl_mw": 700.0,
                    "ndmc_mw": 120.0,
                    "mes_mw": 20.0,
                    "railways_mw": 10.0,
                    "delhi_total_mw": 3_650.0,
                }
            ]
        )
        snapshot = {
            "timestamp": pd.Timestamp("2026-11-20 03:30:00", tz="Asia/Kolkata"),
            "brpl_mw": 1_800.0,
            "tpddl_mw": 1_000.0,
            "bypl_mw": 700.0,
            "ndmc_mw": 120.0,
            "mes_mw": 20.0,
            "railways_mw": 10.0,
            "delhi_total_mw": 3_650.0,
        }
        with (
            patch.object(forecast_api, "DATASET_PATH", dataset_path),
            patch.object(forecast_api, "datetime", self.fixed_datetime_class()),
            patch.object(forecast_api, "load_dataset", return_value=dataset),
            patch.object(forecast_api, "load_actuals_store", return_value=store),
            patch.object(forecast_api, "scan_abt_folder", return_value=([], [])),
            patch.object(forecast_api, "fetch_sldc_snapshot", return_value=snapshot),
        ):
            forecast_api.poll_sldc_snapshot()

        self.assertEqual(
            store.latest_complete_valid_timestamp(),
            pd.Timestamp("2026-11-20 03:30:00"),
        )
        self.assertTrue(
            all(
                value is None
                for value in store.get_valid_values("2026-11-20 03:15:00").values()
            )
        )

    def test_live_actuals_weather_and_causal_bias_reach_forecast_call(self) -> None:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        model_path = root / "model.joblib"
        dataset_path = root / "dataset.parquet"
        model_path.touch()
        dataset_path.touch()

        dataset_timestamps = pd.date_range("2026-09-21", periods=672, freq="15min")
        dataset = pd.DataFrame({"timestamp": dataset_timestamps})
        for column in EXOG_COLUMNS:
            dataset[column] = 0.0
        dataset["temperature_2m"] = 20.0
        dataset["apparent_temperature"] = 20.0
        for column, value in {
            "brpl_mw": 1_800.0,
            "tpddl_mw": 1_000.0,
            "bypl_mw": 700.0,
            "ndmc_mw": 120.0,
            "mes_mw": 20.0,
            "railways_mw": 10.0,
            "delhi_total_mw": 3_650.0,
        }.items():
            dataset[column] = value

        store = ActualLoadStore(root / "live.sqlite3")
        fixed_now = pd.Timestamp("2026-11-20 03:39:00", tz="Asia/Kolkata")
        latest = fixed_now.tz_localize(None).floor("15min") - pd.Timedelta(minutes=15)
        live_timestamps = pd.date_range(end=latest, periods=672, freq="15min")
        store.ingest_frame(
            pd.DataFrame(
                [
                    {
                        "timestamp": timestamp,
                        "brpl_mw": 1_800.0,
                        "tpddl_mw": 1_000.0,
                        "bypl_mw": 700.0,
                        "ndmc_mw": 120.0,
                        "mes_mw": 20.0,
                        "railways_mw": 10.0,
                        "delhi_total_mw": 3_650.0,
                    }
                    for timestamp in live_timestamps
                ]
            ),
            source="sldc_abt_weekly",
        )

        hourly_index = pd.date_range("2026-11-11", "2026-11-22 23:00", freq="h")
        hourly_weather = pd.DataFrame(index=hourly_index)
        for column in WEATHER_VARS:
            hourly_weather[column] = 0.0
        hourly_weather["temperature_2m"] = 25.0
        hourly_weather["apparent_temperature"] = 26.0
        captured: dict[str, object] = {}

        def fake_forecast(
            _model_path: Path,
            y_hist: object,
            x_hist: object,
            x_fut: object,
            future: pd.DatetimeIndex,
            recent_14d_block_bias: pd.DataFrame | None = None,
        ) -> pd.DataFrame:
            captured["shapes"] = (y_hist.shape, x_hist.shape, x_fut.shape)
            captured["bias"] = recent_14d_block_bias
            result = pd.DataFrame(index=future)
            for target, value in {
                "brpl_mw": 1_800.0,
                "tpddl_mw": 1_000.0,
                "bypl_mw": 700.0,
                "ndmc_mw": 120.0,
                "mes_mw": 20.0,
                "railways_mw": 10.0,
                "delhi_total_mw": 3_650.0,
            }.items():
                result[target] = value
                result[f"{target}_p05"] = value - 50.0
                result[f"{target}_p95"] = value + 50.0
            return result

        bundle = {
            "lookback": 672,
            "horizon": 96,
            "all_targets": [
                "brpl_mw",
                "tpddl_mw",
                "bypl_mw",
                "ndmc_mw",
                "mes_mw",
                "railways_mw",
                "delhi_total_mw",
            ],
            "exog_cols": EXOG_COLUMNS,
        }
        with (
            patch.object(forecast_api, "MODEL_PATH", model_path),
            patch.object(forecast_api, "DATASET_PATH", dataset_path),
            patch.object(forecast_api, "datetime", self.fixed_datetime_class()),
            patch.object(forecast_api, "load_bundle", return_value=bundle),
            patch.object(forecast_api, "load_dataset", return_value=dataset),
            patch.object(forecast_api, "load_actuals_store", return_value=store),
            patch.object(forecast_api, "fetch_open_meteo_weather", return_value=hourly_weather),
            patch.object(
                store,
                "recent_14d_block_bias",
                side_effect=lambda future, now: pd.DataFrame(
                    1.0,
                    index=pd.DatetimeIndex(future),
                    columns=bundle["all_targets"],
                ),
            ),
            patch.object(forecast_api, "forecast_next_24h", side_effect=fake_forecast),
        ):
            response = forecast_api.get_forecast()

        self.assertEqual(response["model_input_source"], "LIVE_ACTUALS")
        self.assertEqual(response["data_freshness"]["forecast_mode"], "LIVE")
        self.assertEqual(response["weather_source"], "Open-Meteo live lookback and forecast")
        self.assertEqual(
            captured["shapes"],
            ((672, 7), (672, 29), (96, 29)),
        )
        self.assertIsNotNone(captured["bias"])
        self.assertEqual(len(response["forecast"]), 96)

    def test_replayed_forecast_stays_on_historical_baseline(self) -> None:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        model_path = root / "model.joblib"
        dataset_path = root / "dataset.parquet"
        model_path.touch()
        dataset_path.touch()

        timestamps = pd.date_range("2026-09-21", periods=672, freq="15min")
        dataset = pd.DataFrame({"timestamp": timestamps})
        for column in EXOG_COLUMNS:
            dataset[column] = 0.0
        dataset["temperature_2m"] = 20.0
        dataset["apparent_temperature"] = 21.0
        for column, value in {
            "brpl_mw": 1_800.0,
            "tpddl_mw": 1_000.0,
            "bypl_mw": 700.0,
            "ndmc_mw": 120.0,
            "mes_mw": 20.0,
            "railways_mw": 10.0,
            "delhi_total_mw": 3_650.0,
        }.items():
            dataset[column] = value
        store = ActualLoadStore(root / "replay.sqlite3")
        bundle = {
            "lookback": 672,
            "horizon": 96,
            "all_targets": [
                "brpl_mw",
                "tpddl_mw",
                "bypl_mw",
                "ndmc_mw",
                "mes_mw",
                "railways_mw",
                "delhi_total_mw",
            ],
            "exog_cols": EXOG_COLUMNS,
        }

        def fake_forecast(
            _model_path: Path,
            _y_hist: object,
            _x_hist: object,
            _x_fut: object,
            future: pd.DatetimeIndex,
            recent_14d_block_bias: pd.DataFrame | None = None,
        ) -> pd.DataFrame:
            self.assertIsNone(recent_14d_block_bias)
            result = pd.DataFrame(index=future)
            for target, value in {
                "brpl_mw": 1_800.0,
                "tpddl_mw": 1_000.0,
                "bypl_mw": 700.0,
                "ndmc_mw": 120.0,
                "mes_mw": 20.0,
                "railways_mw": 10.0,
                "delhi_total_mw": 3_650.0,
            }.items():
                result[target] = value
                result[f"{target}_p05"] = value - 50.0
                result[f"{target}_p95"] = value + 50.0
            return result

        with (
            patch.object(forecast_api, "MODEL_PATH", model_path),
            patch.object(forecast_api, "DATASET_PATH", dataset_path),
            patch.object(forecast_api, "datetime", self.fixed_datetime_class()),
            patch.object(forecast_api, "load_bundle", return_value=bundle),
            patch.object(forecast_api, "load_dataset", return_value=dataset),
            patch.object(forecast_api, "load_actuals_store", return_value=store),
            patch.object(
                forecast_api,
                "fetch_open_meteo_weather",
                side_effect=AssertionError("Replay mode must not request live weather"),
            ),
            patch.object(forecast_api, "forecast_next_24h", side_effect=fake_forecast),
        ):
            response = forecast_api.get_forecast()

        self.assertEqual(response["model_input_source"], "HISTORICAL_BASELINE")
        self.assertEqual(response["data_freshness"]["forecast_mode"], "REPLAYED")
        self.assertEqual(response["weather_source"], "Historical baseline profile")


if __name__ == "__main__":
    unittest.main()
