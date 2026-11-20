import asyncio
import json
import logging
import math
import sys
from contextlib import asynccontextmanager
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ML" / "Model"))
sys.path.insert(0, str(ROOT / "ML" / "Data" / "Processing"))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from Web.Backend.core.settings import settings
from Web.Backend.domain.asset_simulators import load_assets_config, simulate_assets
from Web.Backend.domain.grid_metrics import (
    TARGETS as GRID_TARGETS,
    build_ramp_metrics,
    calculate_reserve_dispatch,
    estimate_thermal_coal_burn,
    load_grid_norms,
)
from Web.Backend.integrations.abt_import import scan_abt_folder
from Web.Backend.integrations.sldc_source import fetch_sldc_snapshot
from Web.Backend.storage.actuals_store import ActualLoadStore, InferenceHistoryError
from predict_delhi_load import forecast_next_24h, load_prediction_bundle
from enrich_delhi_dataset import add_domain_features


ROOT = settings.project_root
MODEL_PATH = settings.model_path
DATASET_PATH = settings.dataset_path
ACTUALS_DB_PATH = settings.actuals_db_path
ABT_INBOX_PATH = settings.abt_inbox_path
logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))
TARGETS = (
    "brpl_mw",
    "tpddl_mw",
    "bypl_mw",
    "ndmc_mw",
    "mes_mw",
    "railways_mw",
    "delhi_total_mw",
)
WEATHER_VARS = [
    "temperature_2m",
    "relative_humidity_2m",
    "dew_point_2m",
    "apparent_temperature",
    "precipitation",
    "rain",
    "cloud_cover",
    "wind_speed_10m",
    "shortwave_radiation",
]


class ForecastRequest(BaseModel):
    contracted_ppa_mw: float | list[float] | None = None
    target: str = "delhi_total_mw"


class BessSimulationProfile(BaseModel):
    power_mw: float | None = None
    energy_mwh: float | None = None
    min_soc_pct: float | None = None
    max_soc_pct: float | None = None
    initial_soc_pct: float | None = None
    round_trip_efficiency: float | None = None


class EvSimulationProfile(BaseModel):
    bus_count: int | None = None
    charger_kw_per_bus: float | None = None
    target_energy_mwh: float | None = None


class DemandResponseSimulationProfile(BaseModel):
    threshold_mw: float | None = None
    enrolled_capacity_mw: float | None = None
    curtailable_fraction: float | None = None
    lead_time_hours: float | None = None
    event_duration_hours: float | None = None


class AssetSimulationRequest(BaseModel):
    target: str = "delhi_total_mw"
    corridor_capacity_mw: float | None = None
    bess: BessSimulationProfile | None = None
    ev_fleet: EvSimulationProfile | None = None
    demand_response: DemandResponseSimulationProfile | None = None


def _normalize_ppa_schedule(
    value: float | list[float] | str | None,
    horizon: int,
) -> list[float] | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        try:
            parsed = json.loads(text) if text.startswith("[") else [
                float(part.strip()) for part in text.split(",")
            ]
        except (json.JSONDecodeError, ValueError) as error:
            raise HTTPException(
                status_code=422,
                detail="contracted_ppa_mw must be a non-negative number or 96-number array",
            ) from error
        value = parsed
    values = value if isinstance(value, list) else [value]
    if len(values) not in (1, horizon):
        raise HTTPException(
            status_code=422,
            detail=f"contracted_ppa_mw must be a scalar or an array of exactly {horizon} values",
        )
    schedule = []
    try:
        for item in values:
            if item is None:
                raise TypeError("PPA values cannot be null")
            schedule.append(float(item))
    except (TypeError, ValueError) as error:
        raise HTTPException(
            status_code=422,
            detail="contracted_ppa_mw values must be numeric",
        ) from error
    if any(not math.isfinite(item) or item < 0 for item in schedule):
        raise HTTPException(
            status_code=422,
            detail="contracted_ppa_mw values must be finite and non-negative",
        )
    return schedule * horizon if len(schedule) == 1 else schedule


def poll_sldc_snapshot() -> None:
    now = datetime.now(IST)
    store = load_actuals_store()
    try:
        dataset = load_dataset()
        seed_historical_actuals(store, dataset)
        scan_abt_folder(store, ABT_INBOX_PATH)
        snapshot = fetch_sldc_snapshot(now=now)
        snapshot_timestamp = pd.Timestamp(snapshot["timestamp"])
        if snapshot_timestamp.tzinfo is not None:
            snapshot_timestamp = snapshot_timestamp.tz_convert(IST).tz_localize(None)
        latest_actual = store.latest_complete_valid_timestamp()
        if (
            latest_actual is not None
            and snapshot_timestamp > latest_actual + pd.Timedelta(minutes=15)
        ):
            store.record_missing(
                latest_actual + pd.Timedelta(minutes=15),
                snapshot_timestamp - pd.Timedelta(minutes=15),
                source="sldc_live_snapshot",
            )
        store.ingest_frame(
            pd.DataFrame([snapshot]),
            source="sldc_live_snapshot",
            unit="MW",
        )
        logger.info("Stored Delhi SLDC snapshot at %s", snapshot["timestamp"])
    except (OSError, ValueError, KeyError) as error:
        missing_timestamp = pd.Timestamp(now).floor("15min")
        store.record_missing(
            missing_timestamp,
            missing_timestamp,
            source="sldc_live_snapshot",
        )
        logger.warning("Delhi SLDC snapshot unavailable: %s", error)


async def _sldc_ingestion_loop() -> None:
    while True:
        await asyncio.to_thread(poll_sldc_snapshot)
        now = pd.Timestamp(datetime.now(IST))
        next_poll = now.floor("15min") + pd.Timedelta(minutes=15)
        await asyncio.sleep(max(1.0, (next_poll - now).total_seconds()))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info("Starting %s", _app.title)
    if not settings.enable_sldc_polling:
        yield
        return
    task = asyncio.create_task(_sldc_ingestion_loop())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="GridSense Forecast API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@lru_cache(maxsize=1)
def load_bundle() -> dict[str, Any]:
    return load_prediction_bundle(MODEL_PATH)


@lru_cache(maxsize=1)
def load_dataset():
    return pd.read_parquet(DATASET_PATH).sort_values("timestamp").reset_index(drop=True)


@lru_cache(maxsize=1)
def load_actuals_store() -> ActualLoadStore:
    return ActualLoadStore(ACTUALS_DB_PATH)


@lru_cache(maxsize=1)
def load_asset_simulator_config() -> dict:
    return load_assets_config()


def seed_historical_actuals(store: ActualLoadStore, dataset: pd.DataFrame) -> None:
    stat = DATASET_PATH.stat()
    fingerprint = f"{stat.st_size}:{stat.st_mtime_ns}"
    store.seed_historical(dataset[["timestamp", *TARGETS]], fingerprint)


def fetch_open_meteo_weather() -> pd.DataFrame:
    params = {
        "latitude": 28.58,
        "longitude": 77.20,
        "past_days": 8,
        "forecast_days": 2,
        "hourly": ",".join(WEATHER_VARS),
        "timezone": "Asia/Kolkata",
    }
    url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": "GridSense-Delhi-API/1.0"})

    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    hourly = payload.get("hourly")
    if not isinstance(hourly, dict) or "time" not in hourly:
        raise ValueError("Open-Meteo response does not contain hourly weather data")
    missing_columns = [column for column in WEATHER_VARS if column not in hourly]
    if missing_columns:
        raise ValueError(
            f"Open-Meteo response is missing weather variables: {', '.join(missing_columns)}"
        )
    weather = pd.DataFrame(hourly)
    weather["timestamp"] = pd.to_datetime(weather["time"])
    return weather.drop(columns=["time"]).set_index("timestamp").sort_index()


def _align_hourly_weather(
    weather: pd.DataFrame,
    target_index: pd.DatetimeIndex,
) -> pd.DataFrame:
    weather = weather.sort_index()
    weather = weather[~weather.index.duplicated(keep="last")]
    continuous = [column for column in WEATHER_VARS if column not in ("precipitation", "rain")]
    union = weather.index.union(target_index)
    continuous_weather = (
        weather[continuous]
        .reindex(union)
        .interpolate(method="time")
        .ffill()
        .bfill()
        .reindex(target_index)
    )
    step_weather = (
        weather[["precipitation", "rain"]]
        .reindex(union)
        .ffill()
        .reindex(target_index)
        .fillna(0.0)
        / 4.0
    )
    aligned = pd.concat([continuous_weather, step_weather], axis=1)
    aligned.index.name = "timestamp"
    return aligned


def build_live_weather_exog(
    weather: pd.DataFrame,
    history_index: pd.DatetimeIndex,
    future: pd.DatetimeIndex,
    exog_columns: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if weather.empty or history_index.empty or future.empty:
        raise ValueError("Weather and forecast time indexes must not be empty")
    first_context = min(history_index[0], weather.index.min().floor("15min"))
    target_index = pd.date_range(first_context, future[-1], freq="15min")
    weather_15m = _align_hourly_weather(weather, target_index)
    features = add_domain_features(weather_15m.reset_index()).set_index("timestamp")
    missing = [column for column in exog_columns if column not in features.columns]
    if missing:
        raise ValueError(f"Live weather features are missing: {', '.join(missing)}")
    x_hist = features.loc[history_index, exog_columns]
    x_fut = features.loc[future, exog_columns]
    if x_hist.isna().any().any() or x_fut.isna().any().any():
        raise ValueError("Live weather feature assembly produced missing model inputs")
    return x_hist, x_fut


def build_baseline_future_exog(
    future: pd.DatetimeIndex,
    dataset: pd.DataFrame,
    exog_columns: list[str],
) -> pd.DataFrame:
    baseline_day = dataset.sort_values("timestamp").tail(96)[WEATHER_VARS].reset_index(drop=True)
    context_index = pd.date_range(
        future[0] - pd.Timedelta(hours=72),
        future[-1],
        freq="15min",
    )
    blocks = context_index.hour * 4 + context_index.minute // 15
    weather_15m = baseline_day.iloc[blocks.to_numpy()].copy()
    weather_15m.index = context_index
    weather_15m.index.name = "timestamp"
    features = add_domain_features(weather_15m.reset_index()).set_index("timestamp")
    missing = [column for column in exog_columns if column not in features.columns]
    if missing:
        raise ValueError(f"Historical weather features are missing: {', '.join(missing)}")
    result = features.loc[future, exog_columns]
    if result.isna().any().any():
        raise ValueError("Historical baseline feature assembly produced missing model inputs")
    return result


@app.get("/api/health")
def health():
    return {"status": "ok", "model": MODEL_PATH.name}


@app.get("/api/ready")
def readiness():
    missing_artifacts = [
        path.name
        for path in (MODEL_PATH, DATASET_PATH)
        if not path.is_file()
    ]
    if missing_artifacts:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "not_ready",
                "missing_artifacts": missing_artifacts,
            },
        )
    return {
        "status": "ready",
        "model": MODEL_PATH.name,
        "dataset": DATASET_PATH.name,
    }


def _build_forecast(
    contracted_ppa_mw: float | list[float] | str | None,
    target: str,
):
    if not MODEL_PATH.exists() or not DATASET_PATH.exists():
        raise HTTPException(status_code=500, detail="Production model or dataset is missing")

    bundle = load_bundle()
    dataset = load_dataset()
    actuals_store = load_actuals_store()
    seed_historical_actuals(actuals_store, dataset)
    lookback = int(bundle["lookback"])
    horizon = int(bundle["horizon"])
    if target not in bundle["all_targets"]:
        raise HTTPException(
            status_code=422,
            detail=f"target must be one of: {', '.join(bundle['all_targets'])}",
        )
    ppa_schedule = _normalize_ppa_schedule(contracted_ppa_mw, horizon)

    if len(dataset) < lookback:
        raise HTTPException(status_code=500, detail="Dataset is too short for model lookback")

    now = datetime.now(IST).replace(second=0, microsecond=0)
    first_slot = pd.Timestamp(now).tz_localize(None).floor("15min") + pd.Timedelta(minutes=15)
    future = pd.date_range(first_slot, periods=horizon, freq="15min")

    history = dataset.tail(lookback)
    freshness = actuals_store.data_freshness(now)
    history_source = "HISTORICAL_BASELINE"
    weather_source = "Historical baseline profile"
    filled_blocks = 0
    try:
        if freshness["forecast_mode"] == "LIVE":
            latest_actual = actuals_store.latest_complete_valid_timestamp()
            if latest_actual is None:
                raise InferenceHistoryError("No complete live actual-load window is available")
            history_index = pd.date_range(
                end=latest_actual,
                periods=lookback,
                freq="15min",
            )
            y_history, filled_blocks = actuals_store.inference_input(
                history_index[0],
                lookback,
            )
            hourly_weather = fetch_open_meteo_weather()
            x_history, x_future = build_live_weather_exog(
                hourly_weather,
                history_index,
                future,
                bundle["exog_cols"],
            )
            history_source = "LIVE_ACTUALS"
            weather_source = "Open-Meteo live lookback and forecast"
        else:
            history_index = pd.DatetimeIndex(pd.to_datetime(history["timestamp"]))
            y_history, filled_blocks = actuals_store.inference_input(
                history_index[0],
                lookback,
            )
            x_history = history[bundle["exog_cols"]].set_axis(history_index)
            x_future = build_baseline_future_exog(
                future,
                dataset,
                bundle["exog_cols"],
            )
    except (InferenceHistoryError, OSError, json.JSONDecodeError, KeyError, ValueError) as error:
        if freshness["forecast_mode"] != "LIVE":
            raise HTTPException(
                status_code=503,
                detail={
                    "message": str(error),
                    "data_freshness": actuals_store.data_freshness(
                        now,
                        filled_blocks=filled_blocks,
                        inference_available=False,
                    ),
                },
            ) from error
        logger.warning("Live model inputs unavailable; using historical baseline: %s", error)
        filled_blocks = 0
        history = dataset.tail(lookback)
        history_index = pd.DatetimeIndex(pd.to_datetime(history["timestamp"]))
        try:
            y_history, filled_blocks = actuals_store.inference_input(
                history_index[0],
                lookback,
            )
        except InferenceHistoryError as fallback_error:
            raise HTTPException(
                status_code=503,
                detail={
                    "message": str(fallback_error),
                    "data_freshness": actuals_store.data_freshness(
                        now,
                        inference_available=False,
                    ),
                },
            ) from fallback_error
        x_history = history[bundle["exog_cols"]].set_axis(history_index)
        x_future = build_baseline_future_exog(
            future,
            dataset,
            bundle["exog_cols"],
        )
        history_source = "HISTORICAL_BASELINE"
        weather_source = "Historical baseline profile"

    y_hist = y_history[bundle["all_targets"]].to_numpy(dtype="float32")
    x_hist = x_history[bundle["exog_cols"]].to_numpy(dtype="float32")
    x_fut = x_future[bundle["exog_cols"]].to_numpy(dtype="float32")
    yesterday_values = actuals_store.get_valid_values_for_timestamps(
        future - pd.Timedelta(days=1)
    )

    recent_bias = actuals_store.recent_14d_block_bias(future, now=now)
    forecast = forecast_next_24h(
        bundle,
        y_hist,
        x_hist,
        x_fut,
        future,
        recent_14d_block_bias=recent_bias,
    )
    actuals_store.record_predictions(forecast, issued_at=now)

    norms = load_grid_norms()
    threshold_config = norms["ramp_thresholds_mw"]["entity_thresholds"]
    previous_values: dict[str, float | None] = {
        column: float(y_hist[-1, position])
        for position, column in enumerate(bundle["all_targets"])
    }
    ramp_blocks, ramp_summary = build_ramp_metrics(
        forecast,
        previous_values,
        history_index[-1],
        threshold_config,
    )
    coal_blocks, coal_summary = estimate_thermal_coal_burn(
        forecast["delhi_total_mw"].astype(float).tolist(),
        future,
        15,
        norms["thermal_coal_burn"],
    )
    reserve_fraction = float(norms["reserve_policy"]["minimum_p50_fraction"])

    rows = []
    for position, timestamp in enumerate(future):
        values = forecast.iloc[position]
        row: dict[str, Any] = {"timestamp": timestamp.isoformat() + "+05:30"}
        for column in bundle["all_targets"]:
            row[column] = round(float(values[column]), 2)
            row[column + "_p05"] = round(float(values[column + "_p05"]), 2)
            row[column + "_p95"] = round(float(values[column + "_p95"]), 2)
        row["ramp_assessments"] = ramp_blocks[position]
        row["required_reserve_mw"] = {
            column: round(
                float(
                    calculate_reserve_dispatch(
                        float(values[column]),
                        float(values[column + "_p95"]),
                        None,
                        reserve_fraction,
                    )["required_reserve_mw"]
                ),
                2,
            )
            for column in GRID_TARGETS
        }
        row["ppa_dispatch"] = (
            calculate_reserve_dispatch(
                float(values[target]),
                float(values[target + "_p95"]),
                ppa_schedule[position],
                reserve_fraction,
            )
            if ppa_schedule is not None
            else None
        )
        row["thermal_coal_burn"] = {
            "energy_mwh": round(coal_blocks[position]["energy_mwh"], 2),
            "estimated_coal_burn_tonnes": round(
                coal_blocks[position]["estimated_coal_burn_tonnes"], 2
            ),
            "thermal_mix_share": coal_blocks[position]["thermal_mix_share"],
        }
        row["yesterday_actuals"] = {}
        for column in bundle["all_targets"]:
            actual_value = yesterday_values[position][column]
            row["yesterday_actuals"][column] = (
                round(actual_value, 2) if actual_value is not None else None
            )
        row["weather"] = {
            column: (
                round(float(x_future.iloc[position][column]), 2)
                if pd.notna(x_future.iloc[position][column])
                else None
            )
            for column in (
                "temperature_2m",
                "apparent_temperature",
                "shortwave_radiation",
            )
        }
        rows.append(row)

    asset_forecast = forecast.copy()
    asset_forecast["temperature_2m"] = x_future["temperature_2m"].to_numpy(dtype="float64")
    asset_simulations = simulate_assets(
        asset_forecast,
        target,
        load_asset_simulator_config(),
    )
    totals = forecast["delhi_total_mw"]
    freshness = actuals_store.data_freshness(now, filled_blocks=filled_blocks)
    data_as_of = (
        history_index[-1]
        if history_source == "LIVE_ACTUALS"
        else pd.Timestamp(dataset["timestamp"].max())
    )
    return {
        "generated_at": datetime.now(IST).isoformat(),
        "data_as_of": data_as_of.isoformat() + "+05:30",
        "model_input_source": history_source,
        "data_freshness": freshness,
        "weather_source": weather_source,
        "location": "Delhi",
        "interval_minutes": 15,
        "horizon_hours": 24,
        "forecast": rows,
        "asset_simulations": asset_simulations,
        "dispatch_target": target,
        "contracted_ppa_mw": ppa_schedule,
        "ramp_thresholds_mw": threshold_config,
        "ramp_summary": {
            column: {
                **metrics,
                "timestamp": (
                    metrics["timestamp"].isoformat() + "+05:30"
                    if metrics["timestamp"] is not None
                    else None
                ),
            }
            for column, metrics in ramp_summary.items()
        },
        "thermal_coal_burn": {
            "label": "Estimated Thermal Coal Burn (CEA Normative 0.65 t/MWh)",
            **coal_summary,
            "basis_note": norms["thermal_coal_burn"]["basis_note"],
        },
        "reserve_policy": norms["reserve_policy"],
        "summary": {
            "current_mw": round(float(totals.iloc[0]), 2),
            "peak_mw": round(float(totals.max()), 2),
            "average_mw": round(float(totals.mean()), 2),
            "estimated_thermal_coal_burn_tonnes": round(
                coal_summary["estimated_coal_burn_tonnes"], 2
            ),
        },
    }


@app.get("/api/forecast")
def get_forecast(
    contracted_ppa_mw: str | None = None,
    target: str = "delhi_total_mw",
):
    return _build_forecast(contracted_ppa_mw, target)


@app.post("/api/forecast")
def post_forecast(request: ForecastRequest):
    return _build_forecast(request.contracted_ppa_mw, request.target)


def _asset_forecast_from_response(rows: list[dict]) -> pd.DataFrame:
    timestamps = pd.DatetimeIndex(
        pd.to_datetime([row["timestamp"] for row in rows], utc=True).tz_convert("Asia/Kolkata")
    )
    columns = {
        target: [row[target] for row in rows]
        for target in GRID_TARGETS
    }
    columns.update(
        {
            f"{target}_p95": [row[f"{target}_p95"] for row in rows]
            for target in GRID_TARGETS
        }
    )
    columns["temperature_2m"] = [
        row["weather"]["temperature_2m"] for row in rows
    ]
    return pd.DataFrame(columns, index=timestamps)


@app.post("/api/v1/simulate-assets")
def post_simulate_assets(request: AssetSimulationRequest):
    forecast_payload = _build_forecast(None, request.target)
    profile_overrides = request.model_dump(exclude_none=True)
    profile_overrides.pop("target", None)
    try:
        simulations = simulate_assets(
            _asset_forecast_from_response(forecast_payload["forecast"]),
            request.target,
            load_asset_simulator_config(),
            profile_overrides,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {
        "generated_at": forecast_payload["generated_at"],
        "data_freshness": forecast_payload["data_freshness"],
        "model_input_source": forecast_payload["model_input_source"],
        "simulations": simulations,
    }
