"""Input validation for two-phase CTE projects."""

from __future__ import annotations

from dataclasses import dataclass, field

from cte_app.schemas import PhaseInput, ProjectSettings, TemperatureMode


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0


def validate_volume_fractions(
    f1: float,
    f2: float,
    tol: float = 1e-6,
    porosity: float = 0.0,
    renormalize_solid: bool = False,
) -> ValidationReport:
    report = ValidationReport()
    if f1 < 0 or f2 < 0:
        report.errors.append("体积分数不得为负。")
    if porosity < 0 or porosity >= 1:
        report.errors.append("孔隙率必须满足 0 ≤ p < 1。")
    s = f1 + f2
    if renormalize_solid and porosity > 0:
        # fractions are solid-phase fractions that should sum to 1 among solids
        if abs(s - 1.0) > tol:
            report.warnings.append(
                f"实体相体积分数之和为 {s:.6f}，将在筛选选项下重新归一化。"
            )
    else:
        if abs(s - 1.0) > tol:
            report.errors.append(
                f"两相体积分数之和必须等于 1（当前 f1+f2={s:.8f}）。"
            )
    if porosity > 0:
        report.warnings.append(
            "当前两相解析模型未显式描述孔隙形貌。"
            "请勿将孔隙简单当作零 CTE、零模量的第三相代入所有两相公式。"
        )
    return report


def validate_poisson(nu: float | None, phase_name: str) -> ValidationReport:
    report = ValidationReport()
    if nu is None:
        return report
    if not (-1.0 < nu < 0.5):
        report.errors.append(
            f"相 '{phase_name}' 泊松比 ν={nu} 非物理（要求 -1 < ν < 0.5）。"
        )
    return report


def validate_temperature_ranges(
    phase1: PhaseInput,
    phase2: PhaseInput,
    settings: ProjectSettings,
) -> ValidationReport:
    report = ValidationReport()
    if phase1.temperature_min >= phase1.temperature_max:
        report.errors.append(f"相 '{phase1.phase_name}' 温度区间无效。")
    if phase2.temperature_min >= phase2.temperature_max:
        report.errors.append(f"相 '{phase2.phase_name}' 温度区间无效。")
    if report.errors:
        return report

    common_min = max(phase1.temperature_min, phase2.temperature_min)
    common_max = min(phase1.temperature_max, phase2.temperature_max)
    if common_min >= common_max:
        report.errors.append("两相温度区间不存在共同区间。")

    if settings.temperature_mode == TemperatureMode.TABULAR:
        if not phase1.alpha_table or not phase2.alpha_table:
            report.errors.append("温度表格模式下，两相均需提供 alpha(T) 数据。")
        if settings.allow_temperature_extrapolation:
            report.warnings.append(
                "已开启温度外推：结果可能不可靠，请勿在数据范围外静默外推作为默认行为。"
            )
    return report


def validate_phase_basic(phase: PhaseInput) -> ValidationReport:
    report = ValidationReport()
    if not phase.phase_name.strip():
        report.errors.append("相名称不能为空。")
    r = validate_poisson(phase.Poisson_ratio_nu, phase.phase_name)
    report.errors.extend(r.errors)
    report.warnings.extend(r.warnings)
    for name, val in [
        ("E", phase.Young_modulus_E),
        ("K", phase.bulk_modulus_K),
        ("G", phase.shear_modulus_G),
    ]:
        if val is not None and val <= 0:
            report.errors.append(f"相 '{phase.phase_name}' 的 {name} 必须 > 0。")
    return report


def validate_project(
    phase1: PhaseInput,
    phase2: PhaseInput,
    settings: ProjectSettings,
) -> ValidationReport:
    report = ValidationReport()
    for p in (phase1, phase2):
        r = validate_phase_basic(p)
        report.errors.extend(r.errors)
        report.warnings.extend(r.warnings)

    f1, f2 = phase1.volume_fraction, phase2.volume_fraction
    if settings.renormalize_solid_fractions and settings.porosity > 0:
        s = f1 + f2
        if s > 0:
            f1, f2 = f1 / s, f2 / s
            solid = 1.0 - settings.porosity
            f1, f2 = f1 * solid, f2 * solid
            # After porosity, solid fractions sum to 1-p, not 1 — two-phase models
            # still expect f1+f2=1 among the solid continuum when renormalizing for screening.
            # Spec: provide screening option to renormalize solid phase fractions only.
            s2 = f1 + f2
            if s2 > 0:
                f1, f2 = f1 / s2, f2 / s2

    vr = validate_volume_fractions(
        phase1.volume_fraction,
        phase2.volume_fraction,
        tol=settings.volume_fraction_tolerance,
        porosity=settings.porosity,
        renormalize_solid=settings.renormalize_solid_fractions,
    )
    # When renormalize is on, sum need not be error if we will fix it
    if settings.renormalize_solid_fractions and settings.porosity > 0:
        # re-validate only non-negativity
        if phase1.volume_fraction < 0 or phase2.volume_fraction < 0:
            report.errors.append("体积分数不得为负。")
        report.warnings.extend(vr.warnings)
    else:
        report.errors.extend(vr.errors)
        report.warnings.extend(vr.warnings)

    tr = validate_temperature_ranges(phase1, phase2, settings)
    report.errors.extend(tr.errors)
    report.warnings.extend(tr.warnings)

    return report


def effective_volume_fractions(
    phase1: PhaseInput,
    phase2: PhaseInput,
    settings: ProjectSettings,
) -> tuple[float, float, list[str]]:
    """Return (f1, f2) after optional solid renormalization; f1+f2=1 for models."""
    notes: list[str] = []
    f1, f2 = phase1.volume_fraction, phase2.volume_fraction
    if settings.porosity > 0 and settings.renormalize_solid_fractions:
        s = f1 + f2
        if s <= 0:
            raise ValueError("实体相体积分数之和必须 > 0 才能归一化。")
        f1, f2 = f1 / s, f2 / s
        notes.append(
            f"已按实体相重新归一化体积分数（忽略孔隙 p={settings.porosity:.4f} 的形貌，仅筛选用途）。"
        )
    return f1, f2, notes
