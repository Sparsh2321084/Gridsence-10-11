"""Compatibility exports; implementation lives in :mod:`Web.Backend.domain`."""

from Web.Backend.domain.grid_metrics import (
    TARGETS,
    build_ramp_metrics,
    calculate_reserve_dispatch,
    classify_ramp,
    estimate_thermal_coal_burn,
    load_grid_norms,
)

__all__ = [
    "TARGETS",
    "build_ramp_metrics",
    "calculate_reserve_dispatch",
    "classify_ramp",
    "estimate_thermal_coal_burn",
    "load_grid_norms",
]
