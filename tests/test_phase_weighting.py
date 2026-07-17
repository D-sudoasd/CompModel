"""Tests for XRD plane-family weighting."""

import pytest

from cte_app.phase_weighting import (
    PhaseWeightingError,
    compute_phase_xrd_cte,
    corrected_intensity,
)
from cte_app.schemas import (
    PhaseInput,
    PlaneFamilyRow,
    RFactorDefinition,
)
from cte_app.units import alpha_to_si


def test_corrected_intensity_definitions():
    assert corrected_intensity(100, 2, RFactorDefinition.THEORETICAL_RELATIVE_INTENSITY) == 50
    assert corrected_intensity(100, 2, RFactorDefinition.MULTIPLICATIVE_CORRECTION) == 200
    assert corrected_intensity(100, 2, RFactorDefinition.ALREADY_CORRECTED_WEIGHT) == 100
    assert corrected_intensity(100, 2, RFactorDefinition.CUSTOM_WEIGHT, custom_weight=7) == 7


def test_r_factor_zero_raises():
    with pytest.raises(PhaseWeightingError):
        corrected_intensity(10, 0, RFactorDefinition.THEORETICAL_RELATIVE_INTENSITY)


def test_all_peak_areas_zero_raises():
    phase = PhaseInput(
        phase_name="P",
        volume_fraction=1.0,
        plane_rows=[
            PlaneFamilyRow(h=1, k=1, l=1, alpha_hkl=10, peak_area=0, R_factor=1),
            PlaneFamilyRow(h=2, k=0, l=0, alpha_hkl=12, peak_area=0, R_factor=1),
        ],
    )
    with pytest.raises(PhaseWeightingError):
        compute_phase_xrd_cte(phase)


def test_hand_check_weights():
    """Example from sample_data: Al planes 23 & 22 with equal corrected I -> 22.5e-6."""
    phase = PhaseInput(
        phase_name="Al",
        volume_fraction=0.7,
        r_factor_definition=RFactorDefinition.THEORETICAL_RELATIVE_INTENSITY,
        plane_rows=[
            PlaneFamilyRow(
                h=1, k=1, l=1, plane_family_label="(111)",
                alpha_hkl=23.0, peak_area=100.0, R_factor=1.0,
            ),
            PlaneFamilyRow(
                h=2, k=0, l=0, plane_family_label="(200)",
                alpha_hkl=22.0, peak_area=80.0, R_factor=0.8,
            ),
        ],
    )
    w = compute_phase_xrd_cte(phase)
    assert w.corrected_intensities == pytest.approx([100.0, 100.0])
    assert w.weights == pytest.approx([0.5, 0.5])
    assert w.alpha_phase_xrd_SI == pytest.approx(alpha_to_si(22.5, "1e-6/K"))
    assert w.n_eff == pytest.approx(2.0)


def test_direct_scalar():
    phase = PhaseInput(
        phase_name="P",
        volume_fraction=1.0,
        use_direct_scalar_cte=True,
        direct_alpha=15.0,
        direct_alpha_unit="1e-6/K",
    )
    w = compute_phase_xrd_cte(phase)
    assert w.used_direct_scalar
    assert w.alpha_phase_xrd_SI == pytest.approx(15e-6)
