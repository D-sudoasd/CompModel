"""Monte Carlo uncertainty tests."""

import numpy as np
import pytest

from cte_app.composite_models import model_rom
from cte_app.phase_weighting import compute_phase_xrd_cte
from cte_app.schemas import (
    ModelName,
    PhaseInput,
    PhaseRole,
    PlaneFamilyRow,
    ProjectSettings,
    RFactorDefinition,
)
from cte_app.uncertainty import run_monte_carlo


def _phases():
    p1 = PhaseInput(
        phase_name="Al",
        role=PhaseRole.MATRIX,
        volume_fraction=0.7,
        Young_modulus_E=70,
        Poisson_ratio_nu=0.33,
        r_factor_definition=RFactorDefinition.THEORETICAL_RELATIVE_INTENSITY,
        plane_rows=[
            PlaneFamilyRow(h=1, k=1, l=1, alpha_hkl=23, peak_area=100, R_factor=1),
            PlaneFamilyRow(h=2, k=0, l=0, alpha_hkl=22, peak_area=80, R_factor=0.8),
        ],
    )
    p2 = PhaseInput(
        phase_name="SiC",
        role=PhaseRole.INCLUSION,
        volume_fraction=0.3,
        Young_modulus_E=400,
        Poisson_ratio_nu=0.17,
        plane_rows=[
            PlaneFamilyRow(h=1, k=1, l=1, alpha_hkl=4.5, peak_area=90, R_factor=1),
            PlaneFamilyRow(h=2, k=2, l=0, alpha_hkl=4.3, peak_area=70, R_factor=0.9),
        ],
    )
    return p1, p2


def test_mc_zero_sd_matches_deterministic():
    p1, p2 = _phases()
    settings = ProjectSettings(mc_n_samples=30, mc_seed=1)
    w1 = compute_phase_xrd_cte(p1)
    w2 = compute_phase_xrd_cte(p2)
    det = model_rom(w1.alpha_phase_xrd_SI, w2.alpha_phase_xrd_SI, 0.7, 0.3)
    mc = run_monte_carlo(p1, p2, settings, model=ModelName.ROM, n_samples=30, seed=1)
    assert mc.n_accepted == 30
    assert np.allclose(mc.samples, det)


def test_mc_reproducible_with_seed():
    p1, p2 = _phases()
    p1.volume_fraction_sd = 0.02
    p2.volume_fraction_sd = 0.02
    for row in p1.plane_rows:
        row.alpha_standard_deviation = 0.5
    settings = ProjectSettings(mc_n_samples=200, mc_seed=123, mc_distribution="truncated_normal")
    a = run_monte_carlo(p1, p2, settings, model=ModelName.ROM, n_samples=200, seed=123)
    b = run_monte_carlo(p1, p2, settings, model=ModelName.ROM, n_samples=200, seed=123)
    assert a.n_accepted > 0
    assert np.allclose(a.samples, b.samples)
    assert a.mean == pytest.approx(b.mean)
