"""Project JSON load/save (input round-trip) — no Streamlit dependency."""

from __future__ import annotations

from typing import Any, Optional

from cte_app.schemas import PhaseInput, ProjectSettings

# Bump when input document shape changes incompatibly.
PROJECT_SCHEMA_VERSION = "1.0"


class ProjectIOError(ValueError):
    """Invalid or incomplete project document."""


def _require_mapping(data: Any, name: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ProjectIOError(f"{name} 必须是 JSON 对象")
    return data


def extract_input_document(data: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize full export or input-only JSON to {schema_version, settings, phase1, phase2}.
    Extra result fields are ignored.
    """
    raw = _require_mapping(data, "root")
    if "phase1" not in raw or "phase2" not in raw:
        raise ProjectIOError("缺少 phase1 或 phase2；需要 example_project / 导出 JSON 形状")
    settings_raw = raw.get("settings") or {}
    if not isinstance(settings_raw, dict):
        raise ProjectIOError("settings 必须是对象")
    return {
        "schema_version": str(raw.get("schema_version") or settings_raw.get("schema_version") or "1.0"),
        "settings": settings_raw,
        "phase1": raw["phase1"],
        "phase2": raw["phase2"],
        "meta": {
            k: raw[k]
            for k in ("r_match_reports", "warnings", "assumptions", "model_interval")
            if k in raw
        },
    }


def parse_project_inputs(
    data: dict[str, Any],
) -> tuple[ProjectSettings, PhaseInput, PhaseInput, dict[str, Any]]:
    """Validate and return settings + two phases. Raises ProjectIOError on failure."""
    doc = extract_input_document(data)
    try:
        settings = ProjectSettings.model_validate(doc["settings"])
        phase1 = PhaseInput.model_validate(doc["phase1"])
        phase2 = PhaseInput.model_validate(doc["phase2"])
    except Exception as e:  # pydantic ValidationError
        raise ProjectIOError(f"项目字段校验失败: {e}") from e
    meta = {
        "schema_version": doc["schema_version"],
        **doc.get("meta", {}),
    }
    return settings, phase1, phase2, meta


def dump_project_input(
    settings: ProjectSettings,
    phase1: PhaseInput,
    phase2: PhaseInput,
    *,
    extra: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Serializable input-only project (reloadable)."""
    out: dict[str, Any] = {
        "schema_version": PROJECT_SCHEMA_VERSION,
        "settings": settings.model_dump(mode="json"),
        "phase1": phase1.model_dump(mode="json"),
        "phase2": phase2.model_dump(mode="json"),
    }
    if extra:
        out.update(extra)
    return out


def plane_rows_to_ui_records(plane_rows: list[Any]) -> list[dict[str, Any]]:
    """Convert PhaseInput.plane_rows (models or dicts) to UI table records."""
    out: list[dict[str, Any]] = []
    for r in plane_rows:
        if hasattr(r, "model_dump"):
            d = r.model_dump()
        elif isinstance(r, dict):
            d = r
        else:
            continue
        label = d.get("plane_family_label") or f"({d.get('h', 0)} {d.get('k', 0)} {d.get('l', 0)})"
        out.append(
            {
                "晶面": label,
                "α (10⁻⁶/K)": d.get("alpha_hkl", 0.0),
                "峰面积": d.get("peak_area", 0.0),
                "R因子": d.get("R_factor", 1.0),
            }
        )
    return out


def project_to_ui_state(
    settings: ProjectSettings,
    phase1: PhaseInput,
    phase2: PhaseInput,
) -> dict[str, Any]:
    """
    Map validated project → session_state keys used by app.py.
    Does not touch Streamlit; caller assigns into st.session_state.
    """
    use_scalar = bool(phase1.use_direct_scalar_cte and phase2.use_direct_scalar_cte)
    # If only one phase uses scalar, treat as XRD for safety (mixed rare).
    if phase1.use_direct_scalar_cte != phase2.use_direct_scalar_cte:
        use_scalar = False

    swap = (
        phase1.role.value == "inclusion"
        and phase2.role.value == "matrix"
    )

    a1 = phase1.direct_alpha if phase1.direct_alpha is not None else 22.5
    a2 = phase2.direct_alpha if phase2.direct_alpha is not None else 4.5

    # Prefer display unit from file; input tables stay 1e-6/K semantics.
    return {
        "p1_name": phase1.phase_name,
        "p2_name": phase2.phase_name,
        "f1": float(phase1.volume_fraction),
        "a1_direct": float(a1),
        "a2_direct": float(a2),
        "E1": float(phase1.Young_modulus_E) if phase1.Young_modulus_E else 0.0,
        "E2": float(phase2.Young_modulus_E) if phase2.Young_modulus_E else 0.0,
        "nu1": float(phase1.Poisson_ratio_nu) if phase1.Poisson_ratio_nu is not None else 0.33,
        "nu2": float(phase2.Poisson_ratio_nu) if phase2.Poisson_ratio_nu is not None else 0.17,
        "input_mode": "scalar" if use_scalar else "xrd",
        "rdef": phase1.r_factor_definition.value,
        "microstructure": settings.microstructure.value,
        "direction": settings.measurement_direction.value,
        "porosity": float(settings.porosity),
        "renorm": bool(settings.renormalize_solid_fractions),
        "crystal1": phase1.crystal_system.value,
        "crystal2": phase2.crystal_system.value,
        "swap_roles": swap,
        "planes_1_records": plane_rows_to_ui_records(phase1.plane_rows),
        "planes_2_records": plane_rows_to_ui_records(phase2.plane_rows),
        "alpha_display_unit": settings.alpha_display_unit,
        "display_sig_figs": int(settings.display_sig_figs),
        "project_name": settings.project_name,
    }


def snapshot_inputs_from_calc(
    phase1: PhaseInput,
    phase2: PhaseInput,
    settings: ProjectSettings,
    *,
    input_mode: str,
    rdef: str,
    swap_roles: bool,
    planes_1_records: list[dict[str, Any]],
    planes_2_records: list[dict[str, Any]],
) -> dict[str, Any]:
    """Lightweight UI snapshot for 'restore last ok calculation'."""
    return {
        "p1_name": phase1.phase_name,
        "p2_name": phase2.phase_name,
        "f1": float(phase1.volume_fraction),
        "a1_direct": float(phase1.direct_alpha) if phase1.direct_alpha is not None else 22.5,
        "a2_direct": float(phase2.direct_alpha) if phase2.direct_alpha is not None else 4.5,
        "E1": float(phase1.Young_modulus_E) if phase1.Young_modulus_E else 0.0,
        "E2": float(phase2.Young_modulus_E) if phase2.Young_modulus_E else 0.0,
        "nu1": float(phase1.Poisson_ratio_nu) if phase1.Poisson_ratio_nu is not None else 0.33,
        "nu2": float(phase2.Poisson_ratio_nu) if phase2.Poisson_ratio_nu is not None else 0.17,
        "input_mode": input_mode,
        "rdef": rdef,
        "microstructure": settings.microstructure.value,
        "direction": settings.measurement_direction.value,
        "porosity": float(settings.porosity),
        "renorm": bool(settings.renormalize_solid_fractions),
        "crystal1": phase1.crystal_system.value,
        "crystal2": phase2.crystal_system.value,
        "swap_roles": swap_roles,
        "planes_1_records": planes_1_records,
        "planes_2_records": planes_2_records,
        "alpha_display_unit": settings.alpha_display_unit,
        "display_sig_figs": int(settings.display_sig_figs),
        "project_name": settings.project_name,
    }
