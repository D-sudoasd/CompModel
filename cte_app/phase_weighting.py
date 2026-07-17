"""Single-phase XRD diffraction-intensity weighted apparent CTE."""

from __future__ import annotations

import math
from typing import Sequence

import numpy as np

from cte_app.schemas import (
    CrystalSystem,
    PhaseInput,
    PhaseWeightingResult,
    PlaneFamilyRow,
    RFactorDefinition,
)
from cte_app.units import alpha_to_si


class PhaseWeightingError(ValueError):
    """Raised when phase XRD weighting cannot be computed."""


def corrected_intensity(
    peak_area: float,
    r_factor: float,
    definition: RFactorDefinition,
    custom_weight: float | None = None,
) -> float:
    if definition == RFactorDefinition.THEORETICAL_RELATIVE_INTENSITY:
        if r_factor == 0:
            raise PhaseWeightingError("R_factor = 0 is not allowed for theoretical_relative_intensity.")
        return peak_area / r_factor
    if definition == RFactorDefinition.MULTIPLICATIVE_CORRECTION:
        return peak_area * r_factor
    if definition == RFactorDefinition.ALREADY_CORRECTED_WEIGHT:
        return peak_area
    if definition == RFactorDefinition.CUSTOM_WEIGHT:
        if custom_weight is None:
            raise PhaseWeightingError("custom_weight is required for custom_weight definition.")
        return float(custom_weight)
    raise PhaseWeightingError(f"Unknown R factor definition: {definition}")


def compute_phase_xrd_cte(
    phase: PhaseInput,
    cubic_tolerance_relative: float = 0.05,
) -> PhaseWeightingResult:
    """Compute XRD diffraction-intensity weighted apparent phase CTE (SI 1/K)."""
    warnings: list[str] = []

    if phase.use_direct_scalar_cte:
        if phase.direct_alpha is None:
            raise PhaseWeightingError(
                f"Phase '{phase.phase_name}': direct scalar CTE selected but no value provided."
            )
        alpha_si = alpha_to_si(phase.direct_alpha, phase.direct_alpha_unit)
        warnings.append(
            "使用直接输入的单相标量 CTE，未进行晶面族 XRD 强度加权。"
        )
        return PhaseWeightingResult(
            phase_name=phase.phase_name,
            alpha_phase_xrd_SI=alpha_si,
            corrected_intensities=[],
            weights=[],
            contributions=[],
            labels=[],
            weighted_std=0.0,
            cv=0.0,
            n_eff=1.0,
            warnings=warnings,
            used_direct_scalar=True,
        )

    rows = [r for r in phase.plane_rows if r.enabled]
    if not rows:
        raise PhaseWeightingError(
            f"Phase '{phase.phase_name}': at least one enabled plane family is required."
        )

    for r in rows:
        if r.peak_area < 0 and phase.r_factor_definition != RFactorDefinition.CUSTOM_WEIGHT:
            raise PhaseWeightingError(
                f"Phase '{phase.phase_name}': peak_area must not be negative ({r.plane_family_label})."
            )
        if phase.r_factor_definition != RFactorDefinition.CUSTOM_WEIGHT and r.R_factor <= 0:
            raise PhaseWeightingError(
                f"Phase '{phase.phase_name}': R_factor must be positive ({r.plane_family_label})."
            )

    intensities: list[float] = []
    alphas_si: list[float] = []
    labels: list[str] = []

    for r in rows:
        ci = corrected_intensity(
            r.peak_area,
            r.R_factor,
            phase.r_factor_definition,
            r.custom_weight,
        )
        if ci < 0:
            raise PhaseWeightingError(
                f"Phase '{phase.phase_name}': corrected intensity must not be negative "
                f"({r.plane_family_label})."
            )
        intensities.append(ci)
        alphas_si.append(alpha_to_si(r.alpha_hkl, r.alpha_unit))
        label = r.plane_family_label or f"({r.h}{r.k}{r.l})"
        labels.append(label)

    total = sum(intensities)
    if total <= 0:
        raise PhaseWeightingError(
            f"Phase '{phase.phase_name}': sum of corrected intensities must be > 0 "
            "(all peak areas may be zero)."
        )

    weights = [i / total for i in intensities]
    contributions = [w * a for w, a in zip(weights, alphas_si)]
    alpha_mean = sum(contributions)

    # Weighted standard deviation of plane CTEs
    if len(alphas_si) > 1:
        var = sum(w * (a - alpha_mean) ** 2 for w, a in zip(weights, alphas_si))
        weighted_std = math.sqrt(max(var, 0.0))
    else:
        weighted_std = 0.0

    # Unweighted CV among enabled plane alphas
    arr = np.array(alphas_si, dtype=float)
    mean_a = float(np.mean(arr))
    if abs(mean_a) > 0:
        cv = float(np.std(arr, ddof=0) / abs(mean_a))
    else:
        cv = 0.0 if float(np.std(arr, ddof=0)) == 0 else float("inf")

    n_eff = 1.0 / sum(w * w for w in weights)

    if phase.crystal_system == CrystalSystem.CUBIC and len(alphas_si) > 1:
        if cv > cubic_tolerance_relative:
            warnings.append(
                "立方晶体本征自由热膨胀通常表现为标量形式。不同 hkl 结果的明显差异可能反映织构、"
                "晶粒间约束、相间热失配应力或实验误差。"
            )

    warnings.append(
        "该结果依赖衍射几何、织构、峰拟合、理论强度修正和相间约束，"
        "不等同于严格的本征宏观热膨胀系数。"
    )

    return PhaseWeightingResult(
        phase_name=phase.phase_name,
        alpha_phase_xrd_SI=alpha_mean,
        corrected_intensities=intensities,
        weights=weights,
        contributions=contributions,
        labels=labels,
        weighted_std=weighted_std,
        cv=cv,
        n_eff=n_eff,
        warnings=warnings,
        used_direct_scalar=False,
    )


def plane_rows_from_records(records: Sequence[dict]) -> list[PlaneFamilyRow]:
    return [PlaneFamilyRow.model_validate(r) for r in records]
