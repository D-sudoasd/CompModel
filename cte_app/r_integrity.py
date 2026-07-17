"""R-factor match integrity gate for XRD weighting paths."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional


class UnmatchedRPolicy(str, Enum):
    """How to treat library-fill unmatched plane labels at calculation time."""

    WARN = "warn"  # allow compute; inject strong warnings + report
    FAIL = "fail"  # block compute unless user explicitly accepts unmatched


def enrich_fill_report(report: dict[str, Any]) -> dict[str, Any]:
    """Normalize apply_r_to_plane_df report for export / gate."""
    total = int(report.get("total") or 0)
    matched = int(report.get("matched") or 0)
    unmatched = list(report.get("unmatched") or [])
    out = dict(report)
    out["total"] = total
    out["matched"] = matched
    out["unmatched"] = unmatched
    out["unmatched_count"] = len(unmatched)
    out["all_matched"] = total > 0 and matched == total and len(unmatched) == 0
    out["has_unmatched"] = len(unmatched) > 0
    return out


def evaluate_r_gate(
    *,
    use_xrd: bool,
    policy: UnmatchedRPolicy | str,
    fill_reports: dict[str, Optional[dict[str, Any]]],
    accept_unmatched: bool = False,
) -> dict[str, Any]:
    """
    Gate XRD calculations when a library fill left unmatched hkl rows.

    fill_reports keys typically: phase1 / phase2 (or planes_1 / planes_2).
    Only reports from actual library fills (not manual) should be passed;
    missing report → no gate for that phase (manual R entry).

    Returns:
      {
        ok: bool,
        errors: list[str],
        warnings: list[str],
        reports: dict[str, enriched report],
        blocked_by_unmatched: bool,
      }
    """
    if isinstance(policy, str):
        policy = UnmatchedRPolicy(policy)

    errors: list[str] = []
    warnings: list[str] = []
    enriched: dict[str, dict[str, Any]] = {}
    blocked = False

    if not use_xrd:
        return {
            "ok": True,
            "errors": [],
            "warnings": [],
            "reports": {},
            "blocked_by_unmatched": False,
        }

    any_unmatched = False
    for key, raw in fill_reports.items():
        if not raw:
            continue
        rep = enrich_fill_report(raw)
        enriched[key] = rep
        if not rep["has_unmatched"]:
            continue
        any_unmatched = True
        labels = ", ".join(rep["unmatched"][:12])
        more = "…" if len(rep["unmatched"]) > 12 else ""
        msg = (
            f"[{key}] R 库 `{rep.get('lib_id', '?')}` 未匹配 "
            f"{rep['unmatched_count']}/{rep['total']} 个晶面"
            f"（{labels}{more}）。未匹配行保留原 R（常为 1.0），"
            f"会系统性扭曲 I = Area/R 权重。"
        )
        if policy == UnmatchedRPolicy.FAIL and not accept_unmatched:
            errors.append(msg + " 请修正晶面标签、改用手填 R，或勾选「确认未匹配仍用当前 R」。")
            blocked = True
        else:
            warnings.append(msg)
            if accept_unmatched and policy == UnmatchedRPolicy.FAIL:
                warnings.append(
                    f"[{key}] 用户已确认：允许未匹配晶面以当前 R 参与加权（已记录）。"
                )

    if any_unmatched and policy == UnmatchedRPolicy.WARN:
        warnings.append(
            "R 匹配不完整：结果仅供筛选；发表前请核对未匹配晶面或改用 fail 策略。"
        )

    return {
        "ok": not blocked,
        "errors": errors,
        "warnings": warnings,
        "reports": enriched,
        "blocked_by_unmatched": blocked,
    }


def model_interval_summary(
    results: list[Any],
    *,
    unit: str = "1e-6/K",
    sig: int = 3,
) -> dict[str, Any]:
    """Available-model CTE interval (model discrete range, not experimental error)."""
    from cte_app.units import alpha_from_si, format_alpha

    avail = [r for r in results if getattr(r, "available", False)]
    if not avail:
        return {
            "n_available": 0,
            "alpha_min_SI": None,
            "alpha_max_SI": None,
            "alpha_min_display": None,
            "alpha_max_display": None,
            "unit": unit,
            "models": [],
            "note": "无可用模型；模型区间非实验误差棒。",
        }
    alphas = [float(r.alpha_SI) for r in avail]
    amin, amax = min(alphas), max(alphas)
    return {
        "n_available": len(avail),
        "alpha_min_SI": amin,
        "alpha_max_SI": amax,
        "alpha_min_display": format_alpha(amin, unit, sig),
        "alpha_max_display": format_alpha(amax, unit, sig),
        "alpha_min_value": alpha_from_si(amin, unit),
        "alpha_max_value": alpha_from_si(amax, unit),
        "unit": unit,
        "models": [
            {
                "model": r.model_name.value if hasattr(r.model_name, "value") else str(r.model_name),
                "display_name": r.display_name,
                "alpha_SI": r.alpha_SI,
            }
            for r in avail
        ],
        "note": "多模型离散区间，非实验误差棒；亦非推荐单一真值。",
    }
