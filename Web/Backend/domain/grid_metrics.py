import json
import math
from pathlib import Path
from typing import Any, TypedDict

import pandas as pd

from Web.Backend.core.settings import settings

GRID_NORMS_PATH = settings.project_root / "config" / "grid_norms.json"
TARGETS = (
    "brpl_mw",
    "tpddl_mw",
    "bypl_mw",
    "ndmc_mw",
    "mes_mw",
    "railways_mw",
    "delhi_total_mw",
)


class ReserveDispatchResult(TypedDict):
    required_reserve_mw: float
    contracted_ppa_mw: float | None
    net_position_mw: float | None
    iex_dam_action: str | None
    rtm_reserve_buffer_mw: float | None


def load_grid_norms(path: Path | str = GRID_NORMS_PATH) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as file:
        norms = json.load(file)
    if not isinstance(norms, dict):
        raise ValueError("Grid norms configuration must be a JSON object")

    thresholds = norms.get("ramp_thresholds_mw", {}).get("entity_thresholds", {})
    missing = [target for target in TARGETS if target not in thresholds]
    if missing:
        raise ValueError(f"Grid norms are missing ramp thresholds for: {', '.join(missing)}")
    for target in TARGETS:
        p75 = float(thresholds[target]["p75"])
        p95 = float(thresholds[target]["p95"])
        if not math.isfinite(p75) or not math.isfinite(p95) or p75 < 0 or p95 < p75:
            raise ValueError(f"Invalid ramp thresholds configured for {target}")

    coal = norms.get("thermal_coal_burn", {})
    coal_rate = float(coal.get("specific_consumption_tonnes_per_mwh", float("nan")))
    default_share = float(coal.get("default_thermal_mix_share", float("nan")))
    seasonal = coal.get("seasonal_thermal_mix", {})
    seasonal_share = float(seasonal.get("share", float("nan")))
    if (
        not math.isfinite(coal_rate)
        or coal_rate <= 0
        or not math.isfinite(default_share)
        or not 0 <= default_share <= 1
        or not math.isfinite(seasonal_share)
        or not 0 <= seasonal_share <= 1
    ):
        raise ValueError("Invalid thermal coal-burn norms configuration")
    return norms


def classify_ramp(absolute_change_mw: float, p75_mw: float, p95_mw: float) -> str:
    if not all(math.isfinite(value) for value in (absolute_change_mw, p75_mw, p95_mw)):
        raise ValueError("Ramp values and thresholds must be finite")
    if absolute_change_mw < 0 or p75_mw < 0 or p95_mw < p75_mw:
        raise ValueError("Ramp values and thresholds must be non-negative and ordered")
    if absolute_change_mw < p75_mw:
        return "NORMAL"
    if absolute_change_mw < p95_mw:
        return "MODERATE"
    return "SEVERE"


def build_ramp_metrics(
    forecast: pd.DataFrame,
    previous_values: dict[str, float | None],
    previous_timestamp: pd.Timestamp,
    threshold_config: dict[str, dict[str, float]],
) -> tuple[list[dict[str, dict[str, float | str | None]]], dict[str, dict[str, Any]]]:
    if forecast.empty:
        raise ValueError("Ramp classification requires forecast rows")
    first_timestamp = pd.Timestamp(forecast.index[0])
    prior_timestamp = pd.Timestamp(previous_timestamp)
    if first_timestamp.tzinfo is not None:
        first_timestamp = first_timestamp.tz_convert("Asia/Kolkata").tz_localize(None)
    if prior_timestamp.tzinfo is not None:
        prior_timestamp = prior_timestamp.tz_convert("Asia/Kolkata").tz_localize(None)
    first_has_adjacent_history = (
        first_timestamp - prior_timestamp == pd.Timedelta(minutes=15)
    )

    per_block: list[dict[str, dict[str, float | str | None]]] = [
        {} for _ in range(len(forecast))
    ]
    summary: dict[str, dict[str, Any]] = {}
    for target in TARGETS:
        if target not in forecast.columns or target not in threshold_config:
            raise ValueError(f"Missing forecast or ramp threshold for {target}")
        values = pd.to_numeric(forecast[target], errors="raise").to_numpy(dtype="float64")
        previous = previous_values.get(target)
        changes: list[float | None] = [None] * len(values)
        if first_has_adjacent_history and previous is not None and math.isfinite(float(previous)):
            changes[0] = abs(float(values[0]) - float(previous))
        for position in range(1, len(values)):
            changes[position] = abs(float(values[position]) - float(values[position - 1]))

        p75 = float(threshold_config[target]["p75"])
        p95 = float(threshold_config[target]["p95"])
        for position, change in enumerate(changes):
            per_block[position][target] = {
                "absolute_change_mw": change,
                "severity": classify_ramp(change, p75, p95) if change is not None else None,
                "p75_mw": p75,
                "p95_mw": p95,
            }

        available = [
            (position, change)
            for position, change in enumerate(changes)
            if change is not None
        ]
        if available:
            max_position, max_change = max(available, key=lambda item: item[1])
            summary[target] = {
                "absolute_change_mw": float(max_change),
                "timestamp": pd.Timestamp(forecast.index[max_position]),
                "severity": classify_ramp(float(max_change), p75, p95),
                "p75_mw": p75,
                "p95_mw": p95,
            }
        else:
            summary[target] = {
                "absolute_change_mw": None,
                "timestamp": None,
                "severity": None,
                "p75_mw": p75,
                "p95_mw": p95,
            }
    return per_block, summary


def calculate_reserve_dispatch(
    p50_mw: float,
    p95_mw: float,
    contracted_ppa_mw: float | None,
    minimum_p50_fraction: float,
) -> ReserveDispatchResult:
    if not all(math.isfinite(value) for value in (p50_mw, p95_mw, minimum_p50_fraction)):
        raise ValueError("Forecast and reserve policy values must be finite")
    if minimum_p50_fraction < 0:
        raise ValueError("Minimum reserve fraction cannot be negative")
    if contracted_ppa_mw is not None and (
        not math.isfinite(contracted_ppa_mw) or contracted_ppa_mw < 0
    ):
        raise ValueError("Contracted PPA must be a finite non-negative value")

    required_reserve = max(p95_mw - p50_mw, minimum_p50_fraction * p50_mw)
    if contracted_ppa_mw is None:
        net_position = None
        reserve_buffer = None
        action = None
    else:
        net_position = p50_mw - contracted_ppa_mw
        reserve_buffer = max(0.0, p95_mw - max(p50_mw, contracted_ppa_mw))
        action = "BUY" if net_position > 0 else "SELL" if net_position < 0 else "BALANCED"
    return {
        "required_reserve_mw": required_reserve,
        "contracted_ppa_mw": contracted_ppa_mw,
        "net_position_mw": net_position,
        "iex_dam_action": action,
        "rtm_reserve_buffer_mw": reserve_buffer,
    }


def estimate_thermal_coal_burn(
    p50_mw: list[float],
    timestamps: list[pd.Timestamp] | pd.DatetimeIndex,
    interval_minutes: int,
    coal_norms: dict[str, Any],
) -> tuple[list[dict[str, float]], dict[str, float]]:
    if interval_minutes <= 0 or len(p50_mw) != len(timestamps):
        raise ValueError("Coal estimate requires matching forecast blocks and timestamps")
    if any(not math.isfinite(float(value)) for value in p50_mw):
        raise ValueError("Coal estimate requires finite P50 load values")

    seasonal = coal_norms["seasonal_thermal_mix"]
    seasonal_months = set(int(month) for month in seasonal["months"])
    default_share = float(coal_norms["default_thermal_mix_share"])
    seasonal_share = float(seasonal["share"])
    specific_consumption = float(coal_norms["specific_consumption_tonnes_per_mwh"])
    interval_hours = interval_minutes / 60.0
    blocks: list[dict[str, float]] = []
    total_energy_mwh = 0.0
    total_coal_tonnes = 0.0
    share_weighted_energy = 0.0
    for load_mw, timestamp in zip(p50_mw, timestamps):
        share = seasonal_share if pd.Timestamp(timestamp).month in seasonal_months else default_share
        energy_mwh = max(0.0, float(load_mw)) * interval_hours
        coal_tonnes = energy_mwh * specific_consumption * share
        blocks.append(
            {
                "thermal_mix_share": share,
                "energy_mwh": energy_mwh,
                "estimated_coal_burn_tonnes": coal_tonnes,
            }
        )
        total_energy_mwh += energy_mwh
        total_coal_tonnes += coal_tonnes
        share_weighted_energy += energy_mwh * share
    effective_share = (
        share_weighted_energy / total_energy_mwh if total_energy_mwh > 0 else default_share
    )
    return blocks, {
        "energy_mwh": total_energy_mwh,
        "estimated_coal_burn_tonnes": total_coal_tonnes,
        "thermal_mix_share": effective_share,
        "specific_consumption_tonnes_per_mwh": specific_consumption,
    }
