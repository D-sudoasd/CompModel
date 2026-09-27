"""Versioned project interchange, composition sweeps and explicit phase reuse."""

from copy import deepcopy
from dataclasses import asdict
import json
import math

from cte_app.homogenization import (
    Composite, Constituent, HomogenizationError, PROPERTIES, evaluate, volume_fractions,
)

FORMAT = "compmodel.project"
VERSION = 1


def project_dict(project: Composite) -> dict:
    volume_fractions(project)
    return {"format": FORMAT, "schema_version": VERSION, **asdict(project)}


def load_project(data: dict) -> Composite:
    if not isinstance(data, dict):
        raise HomogenizationError("工程必须为 JSON 对象。")
    if "project" in data:
        data = data["project"]
    if not isinstance(data, dict) or data.get("format") != FORMAT or data.get("schema_version") != VERSION:
        raise HomogenizationError("需要 CompModel v1 工程；旧 CTE JSON 请在 CTE / XRD 专用页面导入。")
    try:
        project = Composite(
            phases=[Constituent(**row) for row in data["phases"]],
            basis=data.get("basis", "volume"), title=data.get("title", "复合材料"),
            custom_name=data.get("custom_name", "自定义系数"), custom_unit=data.get("custom_unit", "1"),
        )
        if any(not isinstance(p.properties, dict) or not isinstance(p.provenance, dict) for p in project.phases):
            raise TypeError("属性及来源必须为对象")
        volume_fractions(project)
    except (TypeError, KeyError, AttributeError) as exc:
        raise HomogenizationError(f"工程结构无效：{exc}") from exc
    return project


def report_dict(project: Composite, family: str, xi: float = 2.0) -> dict:
    return {"project": project_dict(project), "family": family, "parameters": {"xi": xi},
            "internal_units": "SI; custom uses project.custom_unit",
            "volume_fractions": volume_fractions(project),
            "results": [asdict(r) for r in evaluate(project, family, xi=xi)]}


def json_bytes(data: dict) -> bytes:
    return json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")


def analysis_settings(data: dict) -> dict:
    """Restore UI analysis choices from either an input package or a full report."""
    from cte_app.homogenization import FAMILIES

    settings = data.get("analysis", {})
    if "family" in data:
        parameters = data.get("parameters", {})
        if not isinstance(parameters, dict):
            raise HomogenizationError("模型参数必须为对象。")
        settings = {"family": data["family"], "xi": parameters.get("xi", 2.0)}
    if not isinstance(settings, dict):
        raise HomogenizationError("分析设置必须为对象。")
    if not settings:
        return {}
    family, xi = settings.get("family"), settings.get("xi", 2.0)
    if not isinstance(family, str) or family not in FAMILIES:
        raise HomogenizationError("工程中的建模物理量无效。")
    if isinstance(xi, bool) or not isinstance(xi, (float, int)) or not math.isfinite(xi) or xi < .001:
        raise HomogenizationError("工程中的 ξ 必须为 ≥0.001 的有限数值。")
    return {"family": family, "xi": float(xi)}


def sweep(project: Composite, family: str, phase_index: int, points: int = 51, xi: float = 2.0) -> list[dict]:
    """Vary one volume fraction, preserving the remaining phases' volume ratios."""
    f = volume_fractions(project)
    if isinstance(phase_index, bool) or not isinstance(phase_index, int) or not 0 <= phase_index < len(f):
        raise HomogenizationError("扫描相索引无效。")
    if isinstance(points, bool) or not isinstance(points, int) or not 2 <= points <= 501:
        raise HomogenizationError("扫描点数必须为 2–501 的整数。")
    remainder = sum(v for j, v in enumerate(f) if j != phase_index)
    if remainder <= 0:
        raise HomogenizationError("其余相体积分数之和必须 > 0，才能保持它们的比例。")
    rows = []
    for step in range(points):
        value = step/(points-1)
        current = deepcopy(project)
        current.basis = "volume"
        for j, phase in enumerate(current.phases):
            phase.fraction = value if j == phase_index else (1-value)*f[j]/remainder
        for result in evaluate(current, family, xi=xi):
            if result.reason:
                rows.append({"fraction": value, "model": result.model, "property": "", "value_SI": None, "reason": result.reason})
            else:
                rows.extend({"fraction": value, "model": result.model, "property": key,
                             "value_SI": val, "reason": ""} for key, val in result.values.items())
    return rows


def effective_phase(project: Composite, family: str, model: str, name: str, xi: float = 2.0) -> Constituent:
    """A selected estimate becomes an input, with the entire source composition attached."""
    candidates = [r for r in evaluate(project, family, xi=xi) if r.model == model and not r.reason]
    if len(candidates) != 1:
        raise HomogenizationError("必须显式选择一个可用模型。")
    result = candidates[0]
    return Constituent(name, 0.5, dict(result.values), "unspecified",
                       {"project": project_dict(project), "family": family, "model": model,
                        "parameters": {"xi": xi}, "estimate": asdict(result),
                        "assumption": "尺度分离；选定均匀化结果在下一层作为均匀相。"})


def demo_project() -> Composite:
    """Illustrative inputs, not a validated material database."""
    return Composite([
        Constituent("示例基体", 0.7, {"E": 70e9, "nu": 0.3, "alpha": 23e-6,
                                     "k": 200., "sigma": 3.5e7, "rho": 2700., "cp": 900., "custom": 2.}, "matrix"),
        Constituent("示例夹杂", 0.3, {"E": 400e9, "nu": 0.2, "alpha": 4e-6,
                                     "k": 100., "sigma": 0., "rho": 3200., "cp": 750., "custom": 8.}, "inclusion"),
    ], title="两相教学示例（参数仅用于演示）")


def editor_rows(project: Composite) -> list[dict]:
    return [{"name": p.name, "_source_name": p.name, "fraction": p.fraction, "role": p.role,
             **{key: p.properties[key]/meta.scale if key in p.properties else None
                for key, meta in PROPERTIES.items()}} for p in project.phases]


def from_editor(rows: list[dict], base: Composite, *, basis: str, title: str,
                custom_name: str, custom_unit: str) -> Composite:
    phases = []
    prior = {p.name: p for p in base.phases}
    for row in rows:
        props = {}
        for key, meta in PROPERTIES.items():
            value = row.get(key)
            if value is None or (isinstance(value, float) and math.isnan(value)):
                continue
            try:
                props[key] = float(value)*meta.scale
            except (TypeError, ValueError) as exc:
                raise HomogenizationError(f"{key} 需要数值。") from exc
        old = prior.get(row.get("_source_name") or row.get("name"))
        provenance = deepcopy(old.provenance) if old else {}
        if provenance and props != old.properties:
            provenance["properties_edited_after_homogenization"] = True
        phases.append(Constituent(row.get("name"), row.get("fraction"), props,
                                  row.get("role") or "unspecified", provenance))
    project = Composite(phases, basis, title, custom_name, custom_unit)
    volume_fractions(project)
    return project


def apply_table_edits(rows: list[dict], changes: dict) -> list[dict]:
    """Commit Streamlit's table delta before another widget changes visible columns."""
    edited = deepcopy(rows)
    for index, values in changes.get("edited_rows", {}).items():
        edited[int(index)].update(values)
    deleted = set(changes.get("deleted_rows", []))
    return [row for i, row in enumerate(edited) if i not in deleted] + deepcopy(changes.get("added_rows", []))


def display_rows(results: list[dict], project: Composite) -> list[dict]:
    rows = []
    for result in results:
        for key, value in result["values"].items():
            meta = PROPERTIES[key]
            rows.append({"模型": result["model"], "物理量": project.custom_name if key == "custom" else meta.label,
                         "结果": value/meta.scale, "单位": project.custom_unit if key == "custom" else meta.unit,
                         "类型": "由 K、G 换算，非 ν 界限" if key == "nu" else result["kind"]})
    return rows


def display_sweep(rows: list[dict], key: str) -> list[dict]:
    return [{"体积分数": r["fraction"], "模型": r["model"],
             "结果": r["value_SI"]/PROPERTIES[key].scale}
            for r in rows if r["property"] == key and not r["reason"]]
