import json
import math
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from Web.Backend.domain.grid_metrics import TARGETS

ASSETS_CONFIG_PATH = (
    Path(__file__).resolve().parents[1] / "config" / "assets_config.json"
)
INTERVAL_HOURS = 0.25
LOCAL_TIMEZONE = "Asia/Kolkata"


def load_assets_config(path: Path | str = ASSETS_CONFIG_PATH) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as file:
        config = json.load(file)
    if not isinstance(config, dict):
        raise ValueError("Asset simulator configuration must be a JSON object")

    capacities = config.get("corridor_limits_mw", {})
    missing = [target for target in TARGETS if target not in capacities]
    if missing:
        raise ValueError(f"Missing corridor limits for: {', '.join(missing)}")
    for target in TARGETS:
        _positive_number(capacities[target], f"corridor_limits_mw.{target}")

    derating = config.get("thermal_derating", {})
    for key in (
        "base_temperature_c",
        "derating_fraction_per_c",
        "normal_utilization_limit",
        "elevated_utilization_limit",
        "maintenance_utilization_limit",
    ):
        _finite_number(derating.get(key), f"thermal_derating.{key}")
    if not (
        0 < float(derating["normal_utilization_limit"])
        < float(derating["elevated_utilization_limit"])
        <= 1
    ):
        raise ValueError("Thermal utilization thresholds must be ordered in (0, 1]")
    if (
        float(derating["derating_fraction_per_c"]) < 0
        or not 0 < float(derating["maintenance_utilization_limit"]) <= 1
    ):
        raise ValueError("Thermal derating and maintenance limits are invalid")
    return config


def simulate_corridor_stress(
    forecast: pd.DataFrame,
    target: str,
    config: dict[str, Any],
    capacity_override_mw: float | None = None,
) -> dict[str, Any]:
    if target not in TARGETS:
        raise ValueError(f"Unknown forecast target: {target}")
    _require_forecast_columns(forecast, (f"{target}_p95", "temperature_2m"))
    nominal_limit = (
        _positive_number(capacity_override_mw, "corridor capacity")
        if capacity_override_mw is not None
        else _positive_number(config["corridor_limits_mw"][target], "corridor capacity")
    )
    rules = config["thermal_derating"]
    blocks = []
    safe_maintenance_blocks = []
    peak_utilization = -1.0
    peak_status = "NORMAL"

    for timestamp, row in forecast.iterrows():
        temperature = _finite_number(row["temperature_2m"], "temperature_2m")
        p95 = _finite_number(row[f"{target}_p95"], f"{target}_p95")
        excess_temperature = max(0.0, temperature - float(rules["base_temperature_c"]))
        derating_factor = max(
            0.0,
            1.0 - float(rules["derating_fraction_per_c"]) * excess_temperature,
        )
        derated_limit = nominal_limit * derating_factor
        utilization = (
            max(0.0, p95) / derated_limit if derated_limit > 0 else 1_000_000.0
        )
        if utilization < float(rules["normal_utilization_limit"]):
            status = "NORMAL"
        elif utilization <= float(rules["elevated_utilization_limit"]):
            status = "ELEVATED_SAG"
        else:
            status = "N1_THERMAL_RISK"

        maintenance_safe = (
            _in_window(timestamp, rules["maintenance_window"])
            and utilization < float(rules["maintenance_utilization_limit"])
        )
        block = {
            "timestamp": _iso_timestamp(timestamp),
            "p95_mw": p95,
            "temperature_c": temperature,
            "nominal_limit_mw": nominal_limit,
            "derated_limit_mw": derated_limit,
            "utilization_pct": utilization * 100.0,
            "status": status,
            "safe_maintenance_window": maintenance_safe,
        }
        blocks.append(block)
        if maintenance_safe:
            safe_maintenance_blocks.append(block)
        if utilization > peak_utilization:
            peak_utilization = utilization
            peak_status = status

    return {
        "mode": "CONFIGURABLE_SIMULATOR",
        "profile": {"nominal_limit_mw": nominal_limit},
        "blocks": blocks,
        "peak_utilization_pct": peak_utilization * 100.0,
        "peak_status": peak_status,
        "safe_maintenance_blocks": safe_maintenance_blocks,
        "assumption": (
            "Forecast P95 and ambient air temperature only; no conductor temperature, "
            "topology, line rating, or live SCADA telemetry is connected."
        ),
    }


def simulate_bess_schedule(
    forecast: pd.DataFrame,
    target: str,
    config: dict[str, Any],
    profile_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if target not in TARGETS:
        raise ValueError(f"Unknown forecast target: {target}")
    _require_forecast_columns(forecast, (target,))
    profile = {**config["bess"], **(profile_override or {})}
    power_mw = _positive_number(profile["power_mw"], "bess.power_mw")
    energy_mwh = _positive_number(profile["energy_mwh"], "bess.energy_mwh")
    min_soc = _bounded_fraction(profile["min_soc_pct"], "bess.min_soc_pct")
    max_soc = _bounded_fraction(profile["max_soc_pct"], "bess.max_soc_pct")
    initial_soc = _bounded_fraction(profile["initial_soc_pct"], "bess.initial_soc_pct")
    efficiency = _positive_number(
        profile["round_trip_efficiency"], "bess.round_trip_efficiency"
    )
    if efficiency > 1 or min_soc > initial_soc or initial_soc > max_soc:
        raise ValueError("BESS SOC limits or round-trip efficiency are invalid")
    charge_window = profile["charge_window"]
    discharge_windows = profile["discharge_windows"]
    if not isinstance(discharge_windows, list) or not discharge_windows:
        raise ValueError("BESS requires at least one discharge window")
    charge_start, charge_end = _window_bounds(charge_window)
    discharge_bounds = [_window_bounds(window) for window in discharge_windows]
    if (
        charge_start >= charge_end
        or any(start >= end for start, end in discharge_bounds)
        or charge_end > min(start for start, _ in discharge_bounds)
    ):
        raise ValueError("BESS charge window must finish before its discharge windows")
    charge_eta = math.sqrt(efficiency)
    discharge_eta = math.sqrt(efficiency)
    minimum_energy = energy_mwh * min_soc
    maximum_energy = energy_mwh * max_soc
    stored_energy = energy_mwh * initial_soc
    actions_mw = [0.0] * len(forecast)
    p50_values = pd.to_numeric(forecast[target], errors="raise").to_numpy(dtype="float64")
    dates: dict[date, list[int]] = {}
    for position, timestamp in enumerate(forecast.index):
        dates.setdefault(_local_timestamp(timestamp).date(), []).append(position)

    for positions in dates.values():
        charge_positions = [
            position
            for position in positions
            if _in_window(forecast.index[position], charge_window)
            and not any(
                _in_window(forecast.index[position], window)
                for window in discharge_windows
            )
        ]
        discharge_positions = [
            position
            for position in positions
            if any(
                _in_window(forecast.index[position], window)
                for window in discharge_windows
            )
        ]
        charge_room = maximum_energy - stored_energy
        for position in sorted(charge_positions, key=lambda item: p50_values[item]):
            if charge_room <= 1e-9:
                break
            charge_mw = min(
                power_mw,
                charge_room / (INTERVAL_HOURS * charge_eta),
            )
            actions_mw[position] = -charge_mw
            charge_room -= charge_mw * INTERVAL_HOURS * charge_eta
        energy_after_charge = min(maximum_energy, maximum_energy - max(0.0, charge_room))

        discharge_budget_mwh = max(0.0, energy_after_charge - minimum_energy) * discharge_eta
        for position in sorted(
            discharge_positions,
            key=lambda item: p50_values[item],
            reverse=True,
        ):
            if discharge_budget_mwh <= 1e-9:
                break
            discharge_mw = min(power_mw, discharge_budget_mwh / INTERVAL_HOURS)
            actions_mw[position] = discharge_mw
            discharge_budget_mwh -= discharge_mw * INTERVAL_HOURS

        delivered_mwh = sum(
            actions_mw[position] * INTERVAL_HOURS
            for position in discharge_positions
        )
        stored_energy = max(
            minimum_energy,
            energy_after_charge - delivered_mwh / discharge_eta,
        )

    soc_values = []
    state_energy = energy_mwh * initial_soc
    for action in actions_mw:
        if action < 0:
            state_energy += -action * INTERVAL_HOURS * charge_eta
        elif action > 0:
            state_energy -= action * INTERVAL_HOURS / discharge_eta
        state_energy = min(maximum_energy, max(minimum_energy, state_energy))
        soc_values.append(state_energy / energy_mwh * 100.0)

    blocks = [
        {
            "timestamp": _iso_timestamp(timestamp),
            "load_p50_mw": float(forecast.iloc[position][target]),
            "bess_mw": actions_mw[position],
            "soc_pct": soc_values[position],
            "peak_shaved_mw": max(0.0, actions_mw[position]),
        }
        for position, timestamp in enumerate(forecast.index)
    ]
    return {
        "mode": "CONFIGURABLE_SIMULATOR",
        "profile": profile,
        "blocks": blocks,
        "energy_charged_mwh": sum(max(0.0, -action) for action in actions_mw)
        * INTERVAL_HOURS,
        "energy_discharged_mwh": sum(max(0.0, action) for action in actions_mw)
        * INTERVAL_HOURS,
        "peak_shaved_mw": max((block["peak_shaved_mw"] for block in blocks), default=0.0),
        "ending_soc_pct": soc_values[-1] if soc_values else initial_soc * 100.0,
        "assumption": "Greedy schedule from forecast P50 only; no live BESS SOC or dispatch telemetry is connected.",
    }


def simulate_ev_valley_fill(
    forecast: pd.DataFrame,
    target: str,
    config: dict[str, Any],
    profile_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if target not in TARGETS:
        raise ValueError(f"Unknown forecast target: {target}")
    _require_forecast_columns(forecast, (target,))
    profile = {**config["ev_fleet"], **(profile_override or {})}
    bus_count = _positive_number(profile["bus_count"], "ev_fleet.bus_count")
    charger_kw = _positive_number(
        profile["charger_kw_per_bus"], "ev_fleet.charger_kw_per_bus"
    )
    target_energy = _finite_number(
        profile["target_energy_mwh"], "ev_fleet.target_energy_mwh"
    )
    if target_energy < 0:
        raise ValueError("EV target energy cannot be negative")
    max_charger_mw = bus_count * charger_kw / 1000.0
    p50_values = pd.to_numeric(forecast[target], errors="raise").to_numpy(dtype="float64")
    valley_positions = [
        position
        for position, timestamp in enumerate(forecast.index)
        if _in_window(timestamp, profile["valley_window"])
        and _in_window(timestamp, profile["charging_window"])
    ]
    total_positions = [
        position
        for position, timestamp in enumerate(forecast.index)
        if _in_window(timestamp, profile["charging_window"])
    ]
    available_valley_energy = len(valley_positions) * max_charger_mw * INTERVAL_HOURS
    selected_positions = (
        valley_positions
        if available_valley_energy >= target_energy
        else total_positions
    )
    allocations = _water_fill(
        [p50_values[position] for position in selected_positions],
        target_energy,
        max_charger_mw,
    )
    block_power = [0.0] * len(forecast)
    for position, power in zip(selected_positions, allocations):
        block_power[position] = power

    scheduled_energy = sum(block_power) * INTERVAL_HOURS
    blocks = [
        {
            "timestamp": _iso_timestamp(timestamp),
            "load_p50_mw": float(forecast.iloc[position][target]),
            "charging_mw": block_power[position],
            "energy_mwh": block_power[position] * INTERVAL_HOURS,
            "valley_window": position in valley_positions,
        }
        for position, timestamp in enumerate(forecast.index)
    ]
    profile["max_charger_mw"] = max_charger_mw
    return {
        "mode": "CONFIGURABLE_SIMULATOR",
        "profile": profile,
        "blocks": blocks,
        "scheduled_energy_mwh": scheduled_energy,
        "unallocated_energy_mwh": max(0.0, target_energy - scheduled_energy),
        "water_level_mw": _water_level(
            [p50_values[position] for position in selected_positions],
            allocations,
        ),
        "assumption": "Water-filled forecast P50 valley schedule; no vehicle availability or depot telemetry is connected.",
    }


def simulate_demand_response(
    forecast: pd.DataFrame,
    target: str,
    config: dict[str, Any],
    profile_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if target not in TARGETS:
        raise ValueError(f"Unknown forecast target: {target}")
    _require_forecast_columns(forecast, (f"{target}_p95",))
    profile = {**config["demand_response"], **(profile_override or {})}
    enrolled = _positive_number(
        profile["enrolled_capacity_mw"], "demand_response.enrolled_capacity_mw"
    )
    curtailable = _unit_fraction(
        profile["curtailable_fraction"], "demand_response.curtailable_fraction"
    )
    duration_hours = _positive_number(
        profile["event_duration_hours"], "demand_response.event_duration_hours"
    )
    lead_hours = _positive_number(
        profile["lead_time_hours"], "demand_response.lead_time_hours"
    )
    threshold = profile.get("threshold_mw")
    if threshold is None:
        threshold = config["demand_response"]["trigger_threshold_mw_by_target"].get(target)
    max_shave = enrolled * curtailable
    if threshold is None:
        return {
            "mode": "CONFIGURABLE_SIMULATOR",
            "profile": {**profile, "threshold_mw": None},
            "configured": False,
            "triggered": False,
            "reason": "Set a P95 trigger threshold for this selected area.",
            "peak_timestamp": None,
            "peak_p95_mw": None,
            "precooling_window": None,
            "active_curtailment_blocks": [],
            "mw_shaved": 0.0,
            "assumption": "Planning trigger only; no enrolled-customer telemetry or curtailment command is connected.",
        }
    threshold = _finite_number(threshold, "demand_response.threshold_mw")
    if threshold < 0:
        raise ValueError("Demand response threshold cannot be negative")

    p95_values = pd.to_numeric(forecast[f"{target}_p95"], errors="raise").to_numpy(dtype="float64")
    peak_position = int(p95_values.argmax())
    peak_timestamp = _local_timestamp(forecast.index[peak_position])
    peak_p95 = float(p95_values[peak_position])
    triggered = peak_p95 > threshold
    active_blocks = []
    if triggered:
        event_end = peak_timestamp + pd.Timedelta(hours=duration_hours)
        for position, timestamp in enumerate(forecast.index):
            local_timestamp = _local_timestamp(timestamp)
            p95 = float(p95_values[position])
            if peak_timestamp <= local_timestamp < event_end and p95 > threshold:
                active_blocks.append(
                    {
                        "timestamp": _iso_timestamp(timestamp),
                        "p95_mw": p95,
                        "mw_shaved": min(max_shave, max(0.0, p95 - threshold)),
                    }
                )
    peak_shaved = max(
        (block["mw_shaved"] for block in active_blocks),
        default=0.0,
    )
    precooling_start = peak_timestamp - pd.Timedelta(hours=lead_hours) if triggered else None
    return {
        "mode": "CONFIGURABLE_SIMULATOR",
        "profile": {
            **profile,
            "threshold_mw": threshold,
            "max_shave_mw": max_shave,
        },
        "configured": True,
        "triggered": triggered,
        "peak_timestamp": _iso_timestamp(peak_timestamp),
        "peak_p95_mw": peak_p95,
        "precooling_window": (
            {
                "start": _iso_timestamp(precooling_start),
                "end": _iso_timestamp(peak_timestamp),
            }
            if triggered
            else None
        ),
        "active_curtailment_blocks": active_blocks,
        "mw_shaved": peak_shaved,
        "total_shaved_energy_mwh": sum(
            block["mw_shaved"] for block in active_blocks
        )
        * INTERVAL_HOURS,
        "assumption": "Two-hour-ahead planning trigger only; no enrolled-customer telemetry or curtailment command is connected.",
    }


def simulate_assets(
    forecast: pd.DataFrame,
    target: str,
    config: dict[str, Any],
    profile_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    overrides = profile_overrides or {}
    return {
        "mode": "CONFIGURABLE_SIMULATOR",
        "operational_dispatch": False,
        "target": target,
        "data_source": "P50/P95 model forecast and forecast ambient temperature; no live SCADA or asset telemetry",
        "defaults": {
            "corridor_limits_mw": config["corridor_limits_mw"],
            "bess": config["bess"],
            "ev_fleet": config["ev_fleet"],
            "demand_response": config["demand_response"],
        },
        "corridor": simulate_corridor_stress(
            forecast,
            target,
            config,
            overrides.get("corridor_capacity_mw"),
        ),
        "bess": simulate_bess_schedule(
            forecast,
            target,
            config,
            overrides.get("bess"),
        ),
        "ev_fleet": simulate_ev_valley_fill(
            forecast,
            target,
            config,
            overrides.get("ev_fleet"),
        ),
        "demand_response": simulate_demand_response(
            forecast,
            target,
            config,
            overrides.get("demand_response"),
        ),
    }


def _water_fill(loads_mw: list[float], target_energy_mwh: float, power_cap_mw: float) -> list[float]:
    if not loads_mw or target_energy_mwh <= 0:
        return [0.0] * len(loads_mw)
    available = len(loads_mw) * power_cap_mw * INTERVAL_HOURS
    allocated_energy = min(target_energy_mwh, available)
    low = min(loads_mw)
    high = max(loads_mw) + power_cap_mw
    for _ in range(80):
        level = (low + high) / 2.0
        energy = sum(
            min(power_cap_mw, max(0.0, level - load)) * INTERVAL_HOURS
            for load in loads_mw
        )
        if energy < allocated_energy:
            low = level
        else:
            high = level
    level = (low + high) / 2.0
    allocations = [
        min(power_cap_mw, max(0.0, level - load))
        for load in loads_mw
    ]
    residual_mwh = allocated_energy - sum(allocations) * INTERVAL_HOURS
    for position, power in enumerate(allocations):
        if abs(residual_mwh) < 1e-10:
            break
        adjustment_mw = min(power_cap_mw - power, residual_mwh / INTERVAL_HOURS)
        if residual_mwh < 0:
            adjustment_mw = max(-power, adjustment_mw)
        allocations[position] += adjustment_mw
        residual_mwh -= adjustment_mw * INTERVAL_HOURS
    return allocations


def _water_level(loads_mw: list[float], allocations_mw: list[float]) -> float | None:
    if not loads_mw:
        return None
    active_levels = [
        load + allocation
        for load, allocation in zip(loads_mw, allocations_mw)
        if allocation > 0
    ]
    return max(active_levels) if active_levels else None


def _require_forecast_columns(forecast: pd.DataFrame, columns: tuple[str, ...]) -> None:
    if forecast.empty:
        raise ValueError("Asset simulation requires forecast rows")
    missing = [column for column in columns if column not in forecast.columns]
    if missing:
        raise ValueError(f"Asset simulation forecast is missing: {', '.join(missing)}")


def _finite_number(value: Any, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} must be a number") from error
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result


def _positive_number(value: Any, label: str) -> float:
    result = _finite_number(value, label)
    if result <= 0:
        raise ValueError(f"{label} must be positive")
    return result


def _bounded_fraction(value: Any, label: str) -> float:
    result = _finite_number(value, label) / 100.0
    if not 0 <= result <= 1:
        raise ValueError(f"{label} must be between 0 and 100")
    return result


def _unit_fraction(value: Any, label: str) -> float:
    result = _finite_number(value, label)
    if not 0 <= result <= 1:
        raise ValueError(f"{label} must be between 0 and 1")
    return result


def _local_timestamp(value: Any) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is not None:
        return timestamp.tz_convert(LOCAL_TIMEZONE)
    return timestamp


def _iso_timestamp(value: Any) -> str:
    timestamp = _local_timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize(LOCAL_TIMEZONE)
    return timestamp.isoformat()


def _in_window(timestamp: Any, window: dict[str, str]) -> bool:
    local_timestamp = _local_timestamp(timestamp)
    current_minute = local_timestamp.hour * 60 + local_timestamp.minute
    start, end = _window_bounds(window)
    if start <= end:
        return start <= current_minute < end
    return current_minute >= start or current_minute < end


def _window_bounds(window: dict[str, str]) -> tuple[int, int]:
    try:
        start_hour, start_minute = (int(value) for value in window["start"].split(":"))
        end_hour, end_minute = (int(value) for value in window["end"].split(":"))
    except (AttributeError, KeyError, ValueError) as error:
        raise ValueError("Time window values must use HH:MM format") from error
    if (
        not 0 <= start_hour < 24
        or not 0 <= end_hour < 24
        or not 0 <= start_minute < 60
        or not 0 <= end_minute < 60
    ):
        raise ValueError("Time window values must be valid local times")
    return start_hour * 60 + start_minute, end_hour * 60 + end_minute
