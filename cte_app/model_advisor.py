"""Rule-based model recommendation (no black-box ML)."""

from __future__ import annotations

from cte_app.composite_models import ResolvedElastic
from cte_app.schemas import (
    ConfidenceLevel,
    MeasurementDirection,
    MicrostructureType,
    ModelName,
    ModelResult,
    PhaseRole,
    Recommendation,
)


def advise_models(
    microstructure: MicrostructureType,
    direction: MeasurementDirection,
    elastic1: ResolvedElastic,
    elastic2: ResolvedElastic,
    role1: PhaseRole,
    role2: PhaseRole,
    model_results: list[ModelResult],
) -> Recommendation:
    """
    Recommend applicable models based on microstructure, direction, and available inputs.
    Never claims a single true CTE value.
    """
    has_E = elastic1.E is not None and elastic2.E is not None
    has_K = elastic1.K is not None and elastic2.K is not None
    has_G_m = False
    if role1 == PhaseRole.MATRIX:
        has_G_m = elastic1.G is not None and has_K
    elif role2 == PhaseRole.MATRIX:
        has_G_m = elastic2.G is not None and has_K
    matrix_defined = (
        (role1 == PhaseRole.MATRIX and role2 == PhaseRole.INCLUSION)
        or (role2 == PhaseRole.MATRIX and role1 == PhaseRole.INCLUSION)
    )

    notes: list[str] = [
        "不宣称存在唯一正确 CTE 值；下列推荐仅基于输入完整度与微结构假设。"
    ]
    risks: list[str] = []
    assumptions: list[str] = []
    show: list[ModelName] = [ModelName.ROM]
    recommended: ModelName | None = ModelName.ROM
    reason = "仅有体积分数与 CTE 时，只能计算体积分数混合 (ROM)，可信等级为筛选级。"
    confidence = ConfidenceLevel.SCREENING
    assumptions_satisfied = True

    # Default: only ROM
    only_vf_cte = not has_E and not has_K

    if only_vf_cte:
        show = [ModelName.ROM]
        recommended = ModelName.ROM
        confidence = ConfidenceLevel.SCREENING
        reason = "只有体积分数和 CTE：只能计算 ROM；可信等级：筛选级。"
        assumptions = ["无弹性约束的体积分数加权"]
        risks = ["未计入弹性不匹配与微结构约束，仅作粗筛"]

    elif microstructure == MicrostructureType.LAYERED:
        if direction in (
            MeasurementDirection.IN_PLANE,
            MeasurementDirection.LONGITUDINAL,
            MeasurementDirection.ISOTROPIC_AVERAGE,
        ):
            # prefer parallel (iso-strain)
            if has_E:
                recommended = ModelName.PARALLEL
                show = [ModelName.PARALLEL, ModelName.ROM]
                confidence = ConfidenceLevel.MEDIUM
                reason = "层状结构、沿层方向：优先等应变并联模型；同时显示 ROM。"
                assumptions = [
                    "层状、沿层方向近似等应变",
                    "界面完全结合",
                    "线弹性",
                ]
            else:
                recommended = ModelName.ROM
                show = [ModelName.ROM]
                confidence = ConfidenceLevel.SCREENING
                reason = "层状结构沿层方向建议并联模型，但缺少 E，回退 ROM。"
        elif direction in (
            MeasurementDirection.THROUGH_THICKNESS,
            MeasurementDirection.TRANSVERSE,
        ):
            recommended = ModelName.ROM
            show = [ModelName.ROM]
            if has_E:
                show = [ModelName.ROM, ModelName.PARALLEL]
            confidence = ConfidenceLevel.MEDIUM
            reason = "层状结构、垂直层方向：优先显示自由伸长一维模型 (ROM)。"
            assumptions = ["层状、厚度方向近似自由伸长/串联"]
            notes.append("提示：三维泊松耦合未考虑。")
            risks.append("一维模型忽略三维泊松耦合")

    elif microstructure == MicrostructureType.SPHERICAL_PARTICLES:
        if matrix_defined and has_K and has_G_m:
            recommended = ModelName.KERNER
            show = [ModelName.KERNER, ModelName.TURNER, ModelName.ROM]
            confidence = ConfidenceLevel.MEDIUM
            reason = "球形颗粒分散在连续基体：有 K 和 G 时优先 Kerner。"
            assumptions = [
                "连续基体中分散近似球形颗粒",
                "近似各向同性",
                "界面完全结合",
            ]
        elif has_K:
            recommended = ModelName.TURNER
            show = [ModelName.TURNER, ModelName.ROM]
            confidence = ConfidenceLevel.MEDIUM
            reason = "球形颗粒但仅有 K 时优先 Turner；同时显示 ROM。"
            assumptions = ["体积/静水约束主导"]
        else:
            recommended = ModelName.ROM
            show = [ModelName.ROM]
            if has_E:
                show = [ModelName.ROM, ModelName.PARALLEL]
            confidence = ConfidenceLevel.SCREENING
            reason = "球形颗粒但弹性参数不足，仅作 ROM 筛选。"

    elif microstructure in (
        MicrostructureType.RANDOM_PARTICLES,
        MicrostructureType.ELLIPSOIDAL_PARTICLES,
    ):
        if has_K:
            recommended = ModelName.TURNER
            show = [ModelName.TURNER, ModelName.ROM]
            if matrix_defined and has_G_m:
                show = [ModelName.TURNER, ModelName.KERNER, ModelName.ROM]
            confidence = ConfidenceLevel.MEDIUM
            reason = "随机颗粒但颗粒形貌未知：同时显示 ROM、Turner 和 Kerner（若可用）。"
            notes.append("不宣称存在唯一正确值。")
            risks.append("颗粒形貌未知，解析模型可信度中等")
        else:
            recommended = ModelName.ROM
            show = [ModelName.ROM]
            confidence = ConfidenceLevel.SCREENING
            reason = "随机颗粒且弹性参数不足：仅 ROM。"

    elif microstructure in (
        MicrostructureType.CO_CONTINUOUS,
        MicrostructureType.INTERPENETRATING,
    ):
        show = [m for m in [ModelName.ROM, ModelName.PARALLEL, ModelName.TURNER, ModelName.KERNER]
                if any(r.model_name == m and r.available for r in model_results)]
        if not show:
            show = [ModelName.ROM]
        recommended = None
        confidence = ConfidenceLevel.SCREENING
        reason = "双连续或互穿网络：显示所有可用解析模型。"
        notes.append("解析模型可信度有限，建议 RVE 均匀化。")
        risks.append("解析模型可能不足以描述互穿网络")
        assumptions = ["解析近似，微结构复杂"]
        assumptions_satisfied = False

    elif microstructure == MicrostructureType.ALIGNED_FIBER:
        show = [m for m in [ModelName.ROM, ModelName.PARALLEL, ModelName.TURNER]
                if any(r.model_name == m and r.available for r in model_results)]
        if direction in (MeasurementDirection.LONGITUDINAL, MeasurementDirection.IN_PLANE):
            recommended = ModelName.PARALLEL if has_E else ModelName.ROM
            reason = "高长宽比/取向纤维，纵向：优先等应变并联；标量模型可能不足。"
        else:
            recommended = ModelName.ROM
            reason = "取向纤维横向：优先 ROM；标量模型可能不足。"
        confidence = ConfidenceLevel.SCREENING
        notes.append("标量模型可能不足，需要张量模型、Mori-Tanaka 或有限元 RVE。")
        risks.append("强织构/高长宽比超出标量解析模型适用范围")

    else:  # UNKNOWN
        show = [m.model_name for m in model_results if m.available]
        if not show:
            show = [ModelName.ROM]
        vals = [m.alpha_SI for m in model_results if m.available]
        recommended = None
        confidence = ConfidenceLevel.SCREENING
        reason = "微结构未知：不自动指定单一最终值；将模型结果的最小/最大值作为模型离散区间。"
        if vals:
            notes.append(
                f"模型离散区间: [{min(vals):.6e}, {max(vals):.6e}] 1/K"
            )
        risks.append("微结构未知导致模型选择不确定")

    # Annotate model results
    for m in model_results:
        m.recommended = m.model_name == recommended and m.available
        if m.model_name in show and m.available:
            m.confidence = confidence
        m.risks = list(risks)

    return Recommendation(
        recommended_model=recommended,
        reason=reason,
        assumptions=assumptions,
        assumptions_satisfied=assumptions_satisfied,
        confidence=confidence,
        risks=risks,
        show_models=show,
        notes=notes,
    )
