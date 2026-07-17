"""Temperature-dependent CTE table interpolation (no silent extrapolation)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.interpolate import interp1d

from cte_app.schemas import PhaseInput, TemperaturePoint
from cte_app.units import alpha_to_si


@dataclass
class TempAlphaSeries:
    T: np.ndarray
    alpha_SI: np.ndarray


def table_to_si(points: list[TemperaturePoint]) -> TempAlphaSeries:
    if not points:
        raise ValueError("Empty temperature table.")
    T = np.array([p.temperature_C for p in points], dtype=float)
    a = np.array([alpha_to_si(p.alpha, p.alpha_unit) for p in points], dtype=float)
    order = np.argsort(T)
    T, a = T[order], a[order]
    # unique T
    _, idx = np.unique(T, return_index=True)
    return TempAlphaSeries(T=T[idx], alpha_SI=a[idx])


def common_temperature_grid(
    t1: TempAlphaSeries,
    t2: TempAlphaSeries,
    n_points: int = 50,
) -> np.ndarray:
    tmin = max(float(t1.T.min()), float(t2.T.min()))
    tmax = min(float(t1.T.max()), float(t2.T.max()))
    if tmin >= tmax:
        raise ValueError("No common temperature range between the two phases.")
    return np.linspace(tmin, tmax, n_points)


def interpolate_alpha(
    series: TempAlphaSeries,
    T_query: np.ndarray,
    allow_extrapolation: bool = False,
) -> np.ndarray:
    kind = "linear" if len(series.T) > 1 else "nearest"
    if allow_extrapolation:
        f = interp1d(
            series.T,
            series.alpha_SI,
            kind=kind,
            fill_value="extrapolate",  # type: ignore[arg-type]
            bounds_error=False,
        )
    else:
        f = interp1d(
            series.T,
            series.alpha_SI,
            kind=kind,
            bounds_error=True,
        )
    return np.asarray(f(T_query), dtype=float)


def mean_cte_over_range(T: np.ndarray, alpha_SI: np.ndarray, t0: float, t1: float) -> float:
    """Average CTE over [t0, t1] via trapezoidal rule on alpha(T)."""
    mask = (T >= t0) & (T <= t1)
    if mask.sum() < 2:
        raise ValueError("Need at least 2 points in the requested temperature range.")
    return float(np.trapz(alpha_SI[mask], T[mask]) / (t1 - t0))


def phase_alpha_at_T(
    phase: PhaseInput,
    T_query: np.ndarray,
    allow_extrapolation: bool = False,
) -> np.ndarray:
    series = table_to_si(phase.alpha_table)
    return interpolate_alpha(series, T_query, allow_extrapolation=allow_extrapolation)
