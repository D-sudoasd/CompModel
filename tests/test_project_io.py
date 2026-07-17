"""Project JSON round-trip and input extraction."""

from pathlib import Path

import pytest

from cte_app.project_io import (
    PROJECT_SCHEMA_VERSION,
    ProjectIOError,
    dump_project_input,
    parse_project_inputs,
    project_to_ui_state,
)
from cte_app.schemas import PhaseInput, PhaseRole, ProjectSettings

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "sample_data" / "example_project.json"
TEMPLATES = ROOT / "sample_data" / "templates"


def test_parse_example_project():
    import json

    data = json.loads(SAMPLE.read_text(encoding="utf-8"))
    settings, p1, p2, meta = parse_project_inputs(data)
    assert p1.phase_name == "Matrix-Al"
    assert p2.volume_fraction == pytest.approx(0.3)
    assert abs(p1.volume_fraction + p2.volume_fraction - 1.0) < 1e-9
    assert meta["schema_version"]


def test_roundtrip_dump_parse():
    settings = ProjectSettings(project_name="rt")
    p1 = PhaseInput(
        phase_name="A",
        role=PhaseRole.MATRIX,
        volume_fraction=0.7,
        use_direct_scalar_cte=True,
        direct_alpha=22.5,
        Young_modulus_E=70.0,
        Poisson_ratio_nu=0.33,
    )
    p2 = PhaseInput(
        phase_name="B",
        role=PhaseRole.INCLUSION,
        volume_fraction=0.3,
        use_direct_scalar_cte=True,
        direct_alpha=4.5,
        Young_modulus_E=400.0,
        Poisson_ratio_nu=0.17,
    )
    doc = dump_project_input(settings, p1, p2)
    assert doc["schema_version"] == PROJECT_SCHEMA_VERSION
    s2, a, b, _ = parse_project_inputs(doc)
    assert a.phase_name == "A"
    assert b.direct_alpha == pytest.approx(4.5)
    assert s2.project_name == "rt"


def test_export_shape_strips_results():
    """Full export dict still loads via phase1/phase2 only."""
    import json

    data = json.loads(SAMPLE.read_text(encoding="utf-8"))
    data["model_results"] = [{"fake": True}]
    data["warnings"] = ["x"]
    data["schema_version"] = "1.0"
    settings, p1, p2, meta = parse_project_inputs(data)
    assert p1.phase_name.startswith("Matrix")
    assert "warnings" in meta


def test_missing_phases_errors():
    with pytest.raises(ProjectIOError):
        parse_project_inputs({"settings": {}})


def test_templates_exist_and_parse():
    import json

    assert TEMPLATES.is_dir()
    for name in ("al_sic.json", "rom_blank.json", "beta_alpha_pp_structure.json"):
        path = TEMPLATES / name
        assert path.exists(), name
        data = json.loads(path.read_text(encoding="utf-8"))
        settings, p1, p2, _ = parse_project_inputs(data)
        assert p1.volume_fraction + p2.volume_fraction == pytest.approx(1.0)


def test_ui_state_scalar_vs_xrd():
    import json

    data = json.loads((TEMPLATES / "rom_blank.json").read_text(encoding="utf-8"))
    settings, p1, p2, _ = parse_project_inputs(data)
    ui = project_to_ui_state(settings, p1, p2)
    assert ui["input_mode"] == "scalar"
    assert ui["E1"] == 0.0

    data2 = json.loads((TEMPLATES / "beta_alpha_pp_structure.json").read_text(encoding="utf-8"))
    s, a, b, _ = parse_project_inputs(data2)
    ui2 = project_to_ui_state(s, a, b)
    assert ui2["input_mode"] == "xrd"
    assert len(ui2["planes_1_records"]) >= 1
