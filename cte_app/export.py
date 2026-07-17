"""Export project results to CSV, Excel, JSON."""

from __future__ import annotations

import io
import json
from typing import Any, Optional, Sequence

import pandas as pd

from cte_app.schemas import (
    ModelResult,
    PhaseInput,
    PhaseWeightingResult,
    ProjectSettings,
    Recommendation,
)
from cte_app.uncertainty import MCResult
from cte_app.units import alpha_from_si, format_alpha


def phase_raw_df(phase: PhaseInput) -> pd.DataFrame:
    rows = []
    for r in phase.plane_rows:
        rows.append(
            {
                "h": r.h,
                "k": r.k,
                "l": r.l,
                "plane_family_label": r.plane_family_label,
                "alpha_hkl": r.alpha_hkl,
                "alpha_unit": r.alpha_unit,
                "alpha_standard_deviation": r.alpha_standard_deviation,
                "peak_area": r.peak_area,
                "peak_area_standard_deviation": r.peak_area_standard_deviation,
                "R_factor": r.R_factor,
                "R_factor_standard_deviation": r.R_factor_standard_deviation,
                "custom_weight": r.custom_weight,
                "enabled": r.enabled,
                "notes": r.notes,
            }
        )
    return pd.DataFrame(rows)


def phase_weights_df(w: PhaseWeightingResult, unit: str = "1e-6/K") -> pd.DataFrame:
    if w.used_direct_scalar:
        return pd.DataFrame(
            [
                {
                    "mode": "direct_scalar",
                    "alpha_phase_xrd": alpha_from_si(w.alpha_phase_xrd_SI, unit),
                    "alpha_unit": unit,
                }
            ]
        )
    return pd.DataFrame(
        {
            "label": w.labels,
            "corrected_intensity": w.corrected_intensities,
            "weight": w.weights,
            "contribution_SI": w.contributions,
            "contribution_display": [alpha_from_si(c, unit) for c in w.contributions],
        }
    )


def model_results_df(
    results: Sequence[ModelResult],
    unit: str = "1e-6/K",
    sig: int = 3,
) -> pd.DataFrame:
    rows = []
    for r in results:
        rows.append(
            {
                "model": r.model_name.value,
                "display_name": r.display_name,
                "available": r.available,
                "alpha": format_alpha(r.alpha_SI, unit, sig) if r.available else "",
                "alpha_SI": r.alpha_SI if r.available else None,
                "unit": unit,
                "formula": r.formula,
                "substituted": r.substituted,
                "required_inputs": "; ".join(r.required_inputs),
                "assumptions": "; ".join(r.assumptions),
                "assumptions_satisfied": r.assumptions_satisfied,
                "recommended": r.recommended,
                "confidence": r.confidence.value if r.available else "",
                "unavailable_reason": r.unavailable_reason or "",
                "risks": "; ".join(r.risks),
            }
        )
    return pd.DataFrame(rows)


def project_to_dict(
    settings: ProjectSettings,
    phase1: PhaseInput,
    phase2: PhaseInput,
    w1: Optional[PhaseWeightingResult],
    w2: Optional[PhaseWeightingResult],
    results: Sequence[ModelResult],
    recommendation: Optional[Recommendation],
    warnings: list[str],
    assumptions: list[str],
    *,
    r_match_reports: Optional[dict[str, Any]] = None,
    model_interval: Optional[dict[str, Any]] = None,
    schema_version: str = "1.0",
) -> dict[str, Any]:
    """Full audit package: inputs + results + R match + model interval (not a single truth)."""
    from cte_app.project_io import PROJECT_SCHEMA_VERSION
    from cte_app.r_integrity import model_interval_summary

    unit = settings.alpha_display_unit
    sig = settings.display_sig_figs
    interval = model_interval
    if interval is None and results:
        interval = model_interval_summary(list(results), unit=unit, sig=sig)

    return {
        "schema_version": schema_version or PROJECT_SCHEMA_VERSION,
        "settings": settings.model_dump(mode="json"),
        "phase1": phase1.model_dump(mode="json"),
        "phase2": phase2.model_dump(mode="json"),
        "phase1_weighting": w1.model_dump(mode="json") if w1 else None,
        "phase2_weighting": w2.model_dump(mode="json") if w2 else None,
        "model_results": [r.model_dump(mode="json") for r in results],
        "model_interval": interval,
        "recommendation": recommendation.model_dump(mode="json") if recommendation else None,
        "r_match_reports": r_match_reports or {},
        "warnings": warnings,
        "assumptions": assumptions,
        "audit_notes": [
            "model_interval 为多模型离散范围，非实验误差棒。",
            "XRD 加权相 CTE 为表观量，不等于严格本征宏观 CTE。",
            "请勿将单一 recommended 模型当作唯一真值。",
            "settings+phase1+phase2 可再导入 UI 续算（忽略结果字段）。",
        ],
    }


def export_json_bytes(data: dict[str, Any]) -> bytes:
    return json.dumps(data, indent=2, ensure_ascii=False).encode("utf-8")


def export_summary_csv(
    results: Sequence[ModelResult],
    unit: str,
    sig: int,
) -> bytes:
    return model_results_df(results, unit, sig).to_csv(index=False).encode("utf-8-sig")


def export_excel_bytes(
    settings: ProjectSettings,
    phase1: PhaseInput,
    phase2: PhaseInput,
    w1: PhaseWeightingResult,
    w2: PhaseWeightingResult,
    results: Sequence[ModelResult],
    recommendation: Optional[Recommendation],
    warnings: list[str],
    assumptions: list[str],
    mc: Optional[MCResult] = None,
    r_match_reports: Optional[dict[str, Any]] = None,
    model_interval: Optional[dict[str, Any]] = None,
) -> bytes:
    from cte_app.r_integrity import model_interval_summary

    unit = settings.alpha_display_unit
    sig = settings.display_sig_figs
    interval = model_interval or model_interval_summary(list(results), unit=unit, sig=sig)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        pd.DataFrame(
            [
                {"key": k, "value": str(v)}
                for k, v in settings.model_dump(mode="json").items()
            ]
        ).to_excel(writer, sheet_name="Project", index=False)

        phase_raw_df(phase1).to_excel(writer, sheet_name="Phase_1_Raw", index=False)
        phase_weights_df(w1, unit).to_excel(writer, sheet_name="Phase_1_Weights", index=False)
        phase_raw_df(phase2).to_excel(writer, sheet_name="Phase_2_Raw", index=False)
        phase_weights_df(w2, unit).to_excel(writer, sheet_name="Phase_2_Weights", index=False)

        elastic_rows = []
        for p in (phase1, phase2):
            elastic_rows.append(
                {
                    "phase": p.phase_name,
                    "role": p.role.value,
                    "volume_fraction": p.volume_fraction,
                    "E": p.Young_modulus_E,
                    "nu": p.Poisson_ratio_nu,
                    "K": p.bulk_modulus_K,
                    "G": p.shear_modulus_G,
                    "modulus_unit": p.modulus_unit,
                }
            )
        pd.DataFrame(elastic_rows).to_excel(writer, sheet_name="Elastic_Properties", index=False)

        model_results_df(results, unit, sig).to_excel(
            writer, sheet_name="Model_Results", index=False
        )

        pd.DataFrame(
            [
                {
                    "n_available": interval.get("n_available"),
                    "alpha_min": interval.get("alpha_min_display"),
                    "alpha_max": interval.get("alpha_max_display"),
                    "unit": interval.get("unit"),
                    "note": interval.get("note"),
                }
            ]
        ).to_excel(writer, sheet_name="Model_Interval", index=False)

        if r_match_reports:
            rows = []
            for phase_key, rep in r_match_reports.items():
                if not rep:
                    continue
                for rs in rep.get("row_status") or []:
                    rows.append(
                        {
                            "phase": phase_key,
                            "lib_id": rep.get("lib_id"),
                            "label": rs.get("label"),
                            "key": rs.get("key"),
                            "matched": rs.get("matched"),
                            "R": rs.get("R"),
                            "R_source": rs.get("R_source"),
                        }
                    )
                if not rep.get("row_status") and rep.get("unmatched"):
                    for lab in rep["unmatched"]:
                        rows.append(
                            {
                                "phase": phase_key,
                                "lib_id": rep.get("lib_id"),
                                "label": lab,
                                "key": "",
                                "matched": False,
                                "R": None,
                                "R_source": "default_unmatched",
                            }
                        )
            if rows:
                pd.DataFrame(rows).to_excel(writer, sheet_name="R_Match", index=False)
            else:
                pd.DataFrame([{"note": "no R library fill reports"}]).to_excel(
                    writer, sheet_name="R_Match", index=False
                )
        else:
            pd.DataFrame([{"note": "no R library fill in this run"}]).to_excel(
                writer, sheet_name="R_Match", index=False
            )

        if mc and mc.n_accepted > 0:
            pd.DataFrame(
                [
                    {
                        "model": mc.model_name.value,
                        "mean_SI": mc.mean,
                        "median_SI": mc.median,
                        "std_SI": mc.std,
                        "p2.5_SI": mc.p2_5,
                        "p97.5_SI": mc.p97_5,
                        "rejected_fraction": mc.rejected_fraction,
                        "n_accepted": mc.n_accepted,
                    }
                ]
            ).to_excel(writer, sheet_name="Uncertainty", index=False)
        else:
            pd.DataFrame([{"note": "Uncertainty not run"}]).to_excel(
                writer, sheet_name="Uncertainty", index=False
            )

        pd.DataFrame({"warning": warnings}).to_excel(writer, sheet_name="Warnings", index=False)
        pd.DataFrame({"assumption": assumptions}).to_excel(
            writer, sheet_name="Assumptions", index=False
        )

        if recommendation:
            pd.DataFrame(
                [
                    {
                        "recommended_model": (
                            recommendation.recommended_model.value
                            if recommendation.recommended_model
                            else ""
                        ),
                        "reason": recommendation.reason,
                        "confidence": recommendation.confidence.value,
                        "assumptions_satisfied": recommendation.assumptions_satisfied,
                        "risks": "; ".join(recommendation.risks),
                        "notes": "; ".join(recommendation.notes),
                    }
                ]
            ).to_excel(writer, sheet_name="Recommendation", index=False)

    return buf.getvalue()


