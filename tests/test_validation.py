"""Validation and unit conversion tests."""

import pytest

from cte_app.schemas import PhaseInput, ProjectSettings
from cte_app.units import alpha_from_si, alpha_to_si, modulus_from_si, modulus_to_si
from cte_app.validation import validate_poisson, validate_project, validate_volume_fractions


def test_volume_fraction_sum_error():
    r = validate_volume_fractions(0.4, 0.4)
    assert not r.ok
    assert any("1" in e for e in r.errors)


def test_volume_fraction_ok():
    r = validate_volume_fractions(0.4, 0.6)
    assert r.ok


def test_r_factor_zero_via_weighting_in_validation_context():
    # covered in phase_weighting; here poisson
    r = validate_poisson(0.6, "X")
    assert not r.ok
    r2 = validate_poisson(0.3, "X")
    assert r2.ok


def test_unit_roundtrip_alpha():
    si = alpha_to_si(12.5, "1e-6/K")
    assert si == pytest.approx(12.5e-6)
    assert alpha_from_si(si, "1e-6/K") == pytest.approx(12.5)


def test_unit_roundtrip_modulus():
    si = modulus_to_si(70, "GPa")
    assert si == pytest.approx(70e9)
    assert modulus_from_si(si, "GPa") == pytest.approx(70)


def test_project_validation_temp():
    p1 = PhaseInput(phase_name="A", volume_fraction=0.5, temperature_min=100, temperature_max=50)
    p2 = PhaseInput(phase_name="B", volume_fraction=0.5, temperature_min=20, temperature_max=200)
    s = ProjectSettings()
    r = validate_project(p1, p2, s)
    assert not r.ok
