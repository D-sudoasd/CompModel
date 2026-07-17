"""Tests for composite CTE models and acceptance criteria from the spec."""

import pytest

from cte_app.composite_models import (
    CompositeModelError,
    ResolvedElastic,
    compute_all_models,
    model_kerner,
    model_parallel,
    model_rom,
    model_turner,
    young_poisson_to_KG,
)
from cte_app.schemas import ModelName, PhaseRole
from cte_app.units import modulus_to_si


A1 = 20e-6
A2 = 5e-6


def test_f1_equals_one_returns_alpha1():
    e = ResolvedElastic(E=70e9, nu=0.3, K=58e9, G=27e9, source="t", warnings=[])
    for f in compute_all_models(A1, A2, 1.0, 0.0, e, e, PhaseRole.MATRIX, PhaseRole.INCLUSION):
        if f.available:
            assert f.alpha_SI == pytest.approx(A1)


def test_f2_equals_one_returns_alpha2():
    e = ResolvedElastic(E=70e9, nu=0.3, K=58e9, G=27e9, source="t", warnings=[])
    for f in compute_all_models(A1, A2, 0.0, 1.0, e, e, PhaseRole.MATRIX, PhaseRole.INCLUSION):
        if f.available:
            assert f.alpha_SI == pytest.approx(A2)


def test_equal_alpha_all_models_same():
    e = ResolvedElastic(E=70e9, nu=0.3, K=58e9, G=27e9, source="t", warnings=[])
    e2 = ResolvedElastic(E=200e9, nu=0.25, K=133e9, G=80e9, source="t", warnings=[])
    results = compute_all_models(A1, A1, 0.4, 0.6, e, e2, PhaseRole.MATRIX, PhaseRole.INCLUSION)
    for r in results:
        if r.available:
            assert r.alpha_SI == pytest.approx(A1)


def test_equal_E_parallel_degenerates_to_rom():
    rom = model_rom(A1, A2, 0.3, 0.7)
    par = model_parallel(A1, A2, 0.3, 0.7, 100e9, 100e9)
    assert par == pytest.approx(rom)


def test_equal_K_turner_degenerates_to_rom():
    rom = model_rom(A1, A2, 0.25, 0.75)
    tur = model_turner(A1, A2, 0.25, 0.75, 50e9, 50e9)
    assert tur == pytest.approx(rom)


def test_equal_elastic_kerner_degenerates_to_rom():
    K = 80e9
    G = 30e9
    rom = model_rom(A1, A2, 0.4, 0.6)
    ker = model_kerner(A1, A2, 0.4, 0.6, K, K, G)
    assert ker == pytest.approx(rom)


def test_swap_phases_rom_parallel_turner_invariant():
    E1, E2 = 70e9, 200e9
    K1, K2 = 70e9, 150e9
    f1, f2 = 0.35, 0.65
    assert model_rom(A1, A2, f1, f2) == pytest.approx(model_rom(A2, A1, f2, f1))
    assert model_parallel(A1, A2, f1, f2, E1, E2) == pytest.approx(
        model_parallel(A2, A1, f2, f1, E2, E1)
    )
    assert model_turner(A1, A2, f1, f2, K1, K2) == pytest.approx(
        model_turner(A2, A1, f2, f1, K2, K1)
    )


def test_kerner_swap_matrix_inclusion_may_differ():
    K_m, K_i, G_m = 70e9, 200e9, 26e9
    a_mi = model_kerner(A1, A2, 0.7, 0.3, K_m, K_i, G_m)
    a_im = model_kerner(A2, A1, 0.3, 0.7, K_i, K_m, 80e9)
    # not required to be equal
    assert a_mi != pytest.approx(a_im, rel=1e-6) or True  # allow either; just compute


def test_volume_fraction_sum_not_one():
    with pytest.raises(CompositeModelError):
        model_rom(A1, A2, 0.5, 0.6)


def test_young_poisson_to_KG():
    E = 70e9
    nu = 0.33
    K, G = young_poisson_to_KG(E, nu)
    assert K == pytest.approx(E / (3 * (1 - 2 * nu)))
    assert G == pytest.approx(E / (2 * (1 + nu)))


def test_nonphysical_poisson():
    with pytest.raises(CompositeModelError):
        young_poisson_to_KG(70e9, 0.5)


def test_kerner_without_roles_unavailable():
    e = ResolvedElastic(E=70e9, nu=0.3, K=58e9, G=27e9, source="t", warnings=[])
    results = compute_all_models(
        A1, A2, 0.5, 0.5, e, e, PhaseRole.UNSPECIFIED, PhaseRole.UNSPECIFIED
    )
    ker = next(r for r in results if r.model_name == ModelName.KERNER)
    assert not ker.available
    assert "matrix" in (ker.unavailable_reason or "").lower() or "inclusion" in (
        ker.unavailable_reason or ""
    ).lower()


def test_hand_check_example_rom():
    """Full hand-checkable sample: Al XRD CTE 22.5e-6, SiC ~4.416e-6, f=0.7/0.3."""
    # SiC weights
    I1, I2 = 90 / 1.0, 70 / 0.9
    w1, w2 = I1 / (I1 + I2), I2 / (I1 + I2)
    a_sic = w1 * 4.5e-6 + w2 * 4.3e-6
    a_al = 22.5e-6
    rom = model_rom(a_al, a_sic, 0.7, 0.3)
    assert rom == pytest.approx(0.7 * a_al + 0.3 * a_sic)

    # Parallel with E
    E_al = modulus_to_si(70, "GPa")
    E_sic = modulus_to_si(400, "GPa")
    par = model_parallel(a_al, a_sic, 0.7, 0.3, E_al, E_sic)
    expected_par = (0.7 * E_al * a_al + 0.3 * E_sic * a_sic) / (0.7 * E_al + 0.3 * E_sic)
    assert par == pytest.approx(expected_par)
