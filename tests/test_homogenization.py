"""Analytical checks, invariances and invalid-input contracts for new models."""
from copy import deepcopy
import json

import pytest

from cte_app.composite_project import (
    analysis_settings, apply_table_edits, demo_project, editor_rows, effective_phase, from_editor,
    json_bytes, load_project, project_dict, report_dict, sweep,
)
from cte_app.homogenization import Composite, Constituent, HomogenizationError, evaluate, volume_fractions


def result(project, family, model):
    r = next(r for r in evaluate(project, family) if r.model == model)
    assert not r.reason, r.reason
    return r.values


def test_hand_calculated_scalar_models():
    p = Composite([Constituent("a", .5, {"k": 1.}, "matrix"),
                   Constituent("b", .5, {"k": 4.}, "inclusion")])
    assert result(p, "k", "Arithmetic")["k"] == pytest.approx(2.5)
    assert result(p, "k", "Harmonic")["k"] == pytest.approx(1.6)
    assert result(p, "k", "Geometric")["k"] == pytest.approx(2.)
    assert result(p, "k", "Maxwell")["k"] == pytest.approx(2.)
    assert result(p, "k", "Hashin–Shtrikman lower")["k"] == pytest.approx(2.)
    assert result(p, "k", "Hashin–Shtrikman upper")["k"] == pytest.approx(16/7)


def test_elastic_hand_example_and_bounds():
    p = Composite([Constituent("a", .5, {"K": 10e9, "G": 5e9}, "matrix"),
                   Constituent("b", .5, {"K": 20e9, "G": 10e9}, "inclusion")])
    assert result(p, "elastic", "Voigt")["K"] == pytest.approx(15e9)
    assert result(p, "elastic", "Reuss")["K"] == pytest.approx(40e9/3)
    assert result(p, "elastic", "Hill")["K"] == pytest.approx(85e9/6)
    mt = result(p, "elastic", "Mori–Tanaka")
    assert mt["K"] == pytest.approx(180e9/13)
    # ζ_m = 65/12 GPa; ΔG term = (5/2)/(1 + 6/25) = 125/62 GPa.
    assert mt["G"] == pytest.approx((5+125/62)*1e9)
    for key in ("K", "G", "E"):
        vals = [result(p, "elastic", name)[key] for name in
                ("Reuss", "Hashin–Shtrikman lower", "Hashin–Shtrikman upper", "Voigt")]
        assert vals == sorted(vals)
        assert mt[key] == pytest.approx(vals[1])


@pytest.mark.parametrize("family", ["elastic", "alpha", "k", "sigma", "thermal", "custom"])
@pytest.mark.parametrize("endpoint", [0, 1])
def test_pure_phase_limits(family, endpoint):
    p = demo_project()
    p.phases[0].fraction = float(endpoint)
    p.phases[1].fraction = 1-float(endpoint)
    expected = p.phases[0 if endpoint else 1].properties
    for r in evaluate(p, family):
        if r.reason:
            # Zero electrical conductivity has no logarithmic mean.
            assert family == "sigma" and r.model == "Geometric"
            continue
        for key, value in r.values.items():
            if key in expected:
                assert value == pytest.approx(expected[key], rel=1e-12, abs=1e-12)


@pytest.mark.parametrize("family", ["elastic", "alpha", "k", "sigma", "thermal", "custom"])
def test_identical_phases_and_permutation(family):
    p = demo_project()
    reversed_p = deepcopy(p)
    reversed_p.phases.reverse()
    for a, b in zip(evaluate(p, family), evaluate(reversed_p, family)):
        assert a.values == pytest.approx(b.values)
    p.phases[1].properties = dict(p.phases[0].properties)
    for r in evaluate(p, family):
        assert not r.reason
        for key, value in r.values.items():
            if key in p.phases[0].properties:
                assert value == pytest.approx(p.phases[0].properties[key])


def test_mass_volume_equivalence_and_specific_heat():
    p = Composite([Constituent("a", .5, {"rho": 1000., "cp": 1000.}),
                   Constituent("b", .5, {"rho": 2000., "cp": 500.})], basis="mass")
    assert volume_fractions(p) == pytest.approx([2/3, 1/3])
    heat = result(p, "thermal", "Mass heat capacity")
    assert heat == pytest.approx({"rho": 4000/3, "cp": 750.})
    p.basis = "volume"
    p.phases[0].fraction, p.phases[1].fraction = 2/3, 1/3
    assert result(p, "thermal", "Mass heat capacity") == pytest.approx(heat)


def test_three_phase_models_and_explicit_roles():
    p = Composite([Constituent(str(i), 1/3, {"k": float(i+1)}) for i in range(3)])
    assert result(p, "k", "Arithmetic")["k"] == 2.
    unavailable = next(r for r in evaluate(p, "k") if r.model == "Maxwell")
    assert "两相" in unavailable.reason
    p = demo_project()
    p.phases[0].role = "unspecified"
    assert next(r for r in evaluate(p, "elastic") if r.model == "Mori–Tanaka").reason


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -0.1, 1.1, True])
def test_invalid_fractions(bad):
    p = demo_project()
    p.phases[0].fraction = bad
    with pytest.raises(HomogenizationError):
        evaluate(p, "k")


@pytest.mark.parametrize("key,bad", [("E", 0), ("k", -1), ("nu", .5), ("rho", -1), ("alpha", float("nan"))])
def test_invalid_properties(key, bad):
    p = demo_project()
    p.phases[0].properties[key] = bad
    with pytest.raises(HomogenizationError):
        evaluate(p, "elastic")


def test_missing_data_does_not_block_other_models():
    p = Composite([Constituent("a", .5, {"alpha": 1e-6, "E": 10e9}),
                   Constituent("b", .5, {"alpha": 3e-6, "E": 30e9})])
    assert result(p, "alpha", "Parallel")["alpha"] == pytest.approx(2.5e-6)
    assert result(p, "alpha", "ROM")["alpha"] == pytest.approx(2e-6)
    assert next(r for r in evaluate(p, "alpha") if r.model == "Turner").reason


def test_inconsistent_elastic_constants_rejected():
    p = demo_project()
    p.phases[0].properties["K"] = 1e9
    for r in evaluate(p, "elastic"):
        if r.model != "Halpin–Tsai":
            assert "不一致" in r.reason


def test_zero_transport_and_signed_custom():
    p = Composite([Constituent("a", .5, {"sigma": 0., "custom": -2.}, "matrix"),
                   Constituent("b", .5, {"sigma": 4., "custom": 2.}, "inclusion")])
    assert result(p, "sigma", "Harmonic")["sigma"] == 0
    assert result(p, "sigma", "Hashin–Shtrikman lower")["sigma"] == 0
    assert next(r for r in evaluate(p, "sigma") if r.model == "Maxwell").reason
    assert result(p, "custom", "Arithmetic")["custom"] == 0
    assert all(r.reason for r in evaluate(p, "custom")[1:])


def test_interchange_editor_units_and_hierarchy():
    p = demo_project()
    rows = editor_rows(p)
    assert rows[0]["E"] == 70
    assert rows[0]["alpha"] == pytest.approx(23)
    restored = from_editor(rows, p, basis=p.basis, title=p.title, custom_name=p.custom_name, custom_unit=p.custom_unit)
    assert restored == p
    report = report_dict(p, "elastic")
    assert load_project(json.loads(json_bytes(report))) == p
    phase = effective_phase(p, "elastic", "Hill", "aggregate")
    next_level = Composite([phase, Constituent("third", .5, {"E": 10e9, "nu": .3})])
    assert result(next_level, "elastic", "Hill")["E"] > 10e9
    assert load_project(json.loads(json_bytes(project_dict(next_level)))) == next_level
    assert phase.provenance["model"] == "Hill"
    assert phase.role == "unspecified"
    with pytest.raises(HomogenizationError):
        effective_phase(p, "elastic", "unknown", "bad")


def test_sweep_keeps_other_phase_ratios_and_si_values():
    p = Composite([Constituent("a", .2, {"k": 10.}), Constituent("b", .3, {"k": 2.}),
                   Constituent("c", .5, {"k": 4.})])
    rows = [r for r in sweep(p, "k", 0, 3) if r["model"] == "Arithmetic"]
    assert [r["value_SI"] for r in rows] == pytest.approx([3.25, 6.625, 10.])
    assert p.phases[0].fraction == .2


@pytest.mark.parametrize("payload", [{}, [], {"project": None}, {"format": "compmodel.project", "schema_version": 1, "phases": [{}]}])
def test_malformed_json(payload):
    with pytest.raises(HomogenizationError):
        load_project(payload)


def test_editor_delta_and_renamed_effective_phase_preserve_provenance():
    phase = effective_phase(demo_project(), "elastic", "Hill", "aggregate")
    phase.fraction = 1.
    p = Composite([phase])
    rows = apply_table_edits(editor_rows(p), {"edited_rows": {0: {"name": "renamed"}}})
    restored = from_editor(rows, p, basis="volume", title=p.title, custom_name=p.custom_name, custom_unit=p.custom_unit)
    assert restored.phases[0].provenance == phase.provenance
    assert restored.phases[0].name == "renamed"
    assert apply_table_edits(rows, {"deleted_rows": [0], "added_rows": [{"name": "new"}]}) == [{"name": "new"}]


def test_analysis_settings_roundtrip_and_invalid_options():
    report = report_dict(demo_project(), "elastic", xi=3.)
    assert analysis_settings(report) == {"family": "elastic", "xi": 3.}
    assert analysis_settings({"analysis": {"family": "k"}}) == {"family": "k", "xi": 2.}
    for data in ({"analysis": []}, {"family": "elastic", "parameters": []},
                 {"analysis": {"family": "elastic", "xi": float("nan")}}):
        with pytest.raises(HomogenizationError):
            analysis_settings(data)


def test_multiphase_elastic_bounds_for_cross_ordered_moduli():
    # Independent maxima for K and G must remain valid reference media.
    p = Composite([Constituent("a", .2, {"K": 200e9, "G": 5e9}),
                   Constituent("b", .3, {"K": 10e9, "G": 100e9}),
                   Constituent("c", .5, {"K": 60e9, "G": 30e9})])
    for key in ("K", "G", "E"):
        bounds = [result(p, "elastic", model)[key] for model in
                  ("Reuss", "Hashin–Shtrikman lower", "Hashin–Shtrikman upper", "Voigt")]
        assert bounds == sorted(bounds)
