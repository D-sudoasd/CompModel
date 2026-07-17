"""Two-phase composite effective CTE models (ROM, parallel, Turner, Kerner)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from cte_app.schemas import ConfidenceLevel, ModelName, ModelResult, PhaseInput, PhaseRole
from cte_app.units import modulus_to_si


class CompositeModelError(ValueError):
    pass


@dataclass
class ResolvedElastic:
    E: Optional[float]  # Pa
    nu: Optional[float]
    K: Optional[float]  # Pa
    G: Optional[float]  # Pa
    source: str
    warnings: list[str]


def young_poisson_to_KG(E: float, nu: float) -> tuple[float, float]:
    """Convert E, nu (SI) to bulk K and shear G (SI)."""
    if E <= 0:
        raise CompositeModelError("Young modulus E must be > 0.")
    if not (-1.0 < nu < 0.5):
        raise CompositeModelError("Poisson ratio nu must satisfy -1 < nu < 0.5.")
    denom_k = 3.0 * (1.0 - 2.0 * nu)
    if abs(denom_k) < 1e-15:
        raise CompositeModelError("Cannot compute K: (1 - 2*nu) is zero.")
    K = E / denom_k
    G = E / (2.0 * (1.0 + nu))
    if K <= 0 or G <= 0:
        raise CompositeModelError("Derived K and G must be positive.")
    return K, G


def resolve_elastic_properties(
    phase: PhaseInput,
    consistency_tol: float = 0.05,
    prefer: str = "E_nu",
) -> ResolvedElastic:
    """
    Resolve elastic constants to SI (Pa).
    prefer: 'E_nu' | 'K_G' when both sets present and inconsistent.
    """
    warnings: list[str] = []
    unit = phase.modulus_unit
    E = modulus_to_si(phase.Young_modulus_E, unit) if phase.Young_modulus_E is not None else None
    K = modulus_to_si(phase.bulk_modulus_K, unit) if phase.bulk_modulus_K is not None else None
    G = modulus_to_si(phase.shear_modulus_G, unit) if phase.shear_modulus_G is not None else None
    nu = phase.Poisson_ratio_nu

    has_Enu = E is not None and nu is not None
    has_KG = K is not None and G is not None

    if has_Enu:
        K_from, G_from = young_poisson_to_KG(E, nu)  # type: ignore[arg-type]
        if has_KG:
            # consistency check
            rel_K = abs(K_from - K) / max(abs(K_from), abs(K), 1e-30)  # type: ignore[arg-type]
            rel_G = abs(G_from - G) / max(abs(G_from), abs(G), 1e-30)  # type: ignore[arg-type]
            if rel_K > consistency_tol or rel_G > consistency_tol:
                warnings.append(
                    f"Phase '{phase.phase_name}': E/nu-derived K,G differ from provided K,G "
                    f"(rel ΔK={rel_K:.3f}, ΔG={rel_G:.3f}). Using prefer='{prefer}'."
                )
                if prefer == "K_G":
                    return ResolvedElastic(E=E, nu=nu, K=K, G=G, source="K_G", warnings=warnings)
            return ResolvedElastic(
                E=E, nu=nu, K=K_from, G=G_from, source="E_nu", warnings=warnings
            )
        return ResolvedElastic(E=E, nu=nu, K=K_from, G=G_from, source="E_nu", warnings=warnings)

    if has_KG:
        return ResolvedElastic(E=E, nu=nu, K=K, G=G, source="K_G", warnings=warnings)

    # Partial inputs
    return ResolvedElastic(E=E, nu=nu, K=K, G=G, source="partial", warnings=warnings)


def validate_volume_fractions(f1: float, f2: float, tol: float = 1e-6) -> None:
    if f1 < 0 or f2 < 0:
        raise CompositeModelError("Volume fractions must be non-negative.")
    if abs(f1 + f2 - 1.0) > tol:
        raise CompositeModelError(
            f"Volume fractions must sum to 1 (got f1+f2={f1 + f2})."
        )


def model_rom(alpha1: float, alpha2: float, f1: float, f2: float) -> float:
    validate_volume_fractions(f1, f2)
    return f1 * alpha1 + f2 * alpha2


def model_parallel(
    alpha1: float, alpha2: float, f1: float, f2: float, E1: float, E2: float
) -> float:
    validate_volume_fractions(f1, f2)
    if E1 <= 0 or E2 <= 0:
        raise CompositeModelError("Parallel model requires E1 > 0 and E2 > 0.")
    return (f1 * E1 * alpha1 + f2 * E2 * alpha2) / (f1 * E1 + f2 * E2)


def model_turner(
    alpha1: float, alpha2: float, f1: float, f2: float, K1: float, K2: float
) -> float:
    validate_volume_fractions(f1, f2)
    if K1 <= 0 or K2 <= 0:
        raise CompositeModelError("Turner model requires K1 > 0 and K2 > 0.")
    return (f1 * K1 * alpha1 + f2 * K2 * alpha2) / (f1 * K1 + f2 * K2)


def model_kerner(
    alpha_m: float,
    alpha_i: float,
    f_m: float,
    f_i: float,
    K_m: float,
    K_i: float,
    G_m: float,
) -> float:
    validate_volume_fractions(f_m, f_i)
    if K_m <= 0 or K_i <= 0 or G_m <= 0:
        raise CompositeModelError("Kerner model requires K_m, K_i, G_m > 0.")
    # numerator = alpha_i * f_i * K_i / (3K_i + 4 G_m) + alpha_m * f_m * K_m / (3K_m + 4 G_m)
    # denominator = f_i * K_i / (3K_i + 4 G_m) + f_m * K_m / (3K_m + 4 G_m)
    term_i = K_i / (3.0 * K_i + 4.0 * G_m)
    term_m = K_m / (3.0 * K_m + 4.0 * G_m)
    numerator = alpha_i * f_i * term_i + alpha_m * f_m * term_m
    denominator = f_i * term_i + f_m * term_m
    if abs(denominator) < 1e-30:
        raise CompositeModelError("Kerner model denominator is zero.")
    return numerator / denominator


def _fmt_si_alpha(a: float) -> str:
    return f"{a:.6e} 1/K"


def compute_all_models(
    alpha1: float,
    alpha2: float,
    f1: float,
    f2: float,
    elastic1: ResolvedElastic,
    elastic2: ResolvedElastic,
    role1: PhaseRole,
    role2: PhaseRole,
    phase1_name: str = "Phase 1",
    phase2_name: str = "Phase 2",
) -> list[ModelResult]:
    """Evaluate all analytical models; mark unavailable when inputs missing."""
    results: list[ModelResult] = []

    # ROM
    try:
        a = model_rom(alpha1, alpha2, f1, f2)
        results.append(
            ModelResult(
                model_name=ModelName.ROM,
                display_name="串联/自由伸长混合 (ROM)",
                alpha_SI=a,
                formula="α_rom = f₁·α₁ + f₂·α₂",
                substituted=(
                    f"α = {f1:.4f}·{_fmt_si_alpha(alpha1)} + {f2:.4f}·{_fmt_si_alpha(alpha2)} "
                    f"= {_fmt_si_alpha(a)}"
                ),
                required_inputs=["α₁", "α₂", "f₁", "f₂"],
                assumptions=[
                    "无力学约束的体积分数加权",
                    "一维自由伸长/串联思路近似",
                    "不引入弹性不匹配",
                ],
                assumptions_satisfied=True,
                available=True,
                confidence=ConfidenceLevel.SCREENING,
            )
        )
    except CompositeModelError as e:
        results.append(
            ModelResult(
                model_name=ModelName.ROM,
                display_name="串联/自由伸长混合 (ROM)",
                alpha_SI=float("nan"),
                formula="α_rom = f₁·α₁ + f₂·α₂",
                substituted="",
                required_inputs=["α₁", "α₂", "f₁", "f₂"],
                assumptions=[],
                assumptions_satisfied=False,
                available=False,
                unavailable_reason=str(e),
            )
        )

    # Parallel
    if elastic1.E is not None and elastic2.E is not None:
        try:
            a = model_parallel(alpha1, alpha2, f1, f2, elastic1.E, elastic2.E)
            results.append(
                ModelResult(
                    model_name=ModelName.PARALLEL,
                    display_name="并联/等应变一维模型",
                    alpha_SI=a,
                    formula="α_∥ = (f₁ E₁ α₁ + f₂ E₂ α₂) / (f₁ E₁ + f₂ E₂)",
                    substituted=(
                        f"α = ({f1:.4f}·{elastic1.E:.3e}·{alpha1:.3e} + "
                        f"{f2:.4f}·{elastic2.E:.3e}·{alpha2:.3e}) / "
                        f"({f1:.4f}·{elastic1.E:.3e} + {f2:.4f}·{elastic2.E:.3e}) "
                        f"= {_fmt_si_alpha(a)}"
                    ),
                    required_inputs=["α₁", "α₂", "f₁", "f₂", "E₁", "E₂"],
                    assumptions=[
                        "两相沿目标方向具有相同总应变",
                        "界面完全结合",
                        "线弹性",
                        "外部合力为零",
                    ],
                    assumptions_satisfied=True,
                    available=True,
                )
            )
        except CompositeModelError as e:
            results.append(
                ModelResult(
                    model_name=ModelName.PARALLEL,
                    display_name="并联/等应变一维模型",
                    alpha_SI=float("nan"),
                    formula="α_∥ = (f₁ E₁ α₁ + f₂ E₂ α₂) / (f₁ E₁ + f₂ E₂)",
                    substituted="",
                    required_inputs=["α₁", "α₂", "f₁", "f₂", "E₁", "E₂"],
                    assumptions=[],
                    assumptions_satisfied=False,
                    available=False,
                    unavailable_reason=str(e),
                )
            )
    else:
        results.append(
            ModelResult(
                model_name=ModelName.PARALLEL,
                display_name="并联/等应变一维模型",
                alpha_SI=float("nan"),
                formula="α_∥ = (f₁ E₁ α₁ + f₂ E₂ α₂) / (f₁ E₁ + f₂ E₂)",
                substituted="",
                required_inputs=["α₁", "α₂", "f₁", "f₂", "E₁", "E₂"],
                assumptions=[
                    "两相沿目标方向具有相同总应变",
                    "界面完全结合",
                    "线弹性",
                    "外部合力为零",
                ],
                assumptions_satisfied=False,
                available=False,
                unavailable_reason="缺少 E₁ 和/或 E₂，无法计算并联模型。",
            )
        )

    # Turner
    if elastic1.K is not None and elastic2.K is not None:
        try:
            a = model_turner(alpha1, alpha2, f1, f2, elastic1.K, elastic2.K)
            results.append(
                ModelResult(
                    model_name=ModelName.TURNER,
                    display_name="Turner 模型",
                    alpha_SI=a,
                    formula="α_Turner = (f₁ K₁ α₁ + f₂ K₂ α₂) / (f₁ K₁ + f₂ K₂)",
                    substituted=(
                        f"α = ({f1:.4f}·{elastic1.K:.3e}·{alpha1:.3e} + "
                        f"{f2:.4f}·{elastic2.K:.3e}·{alpha2:.3e}) / "
                        f"({f1:.4f}·{elastic1.K:.3e} + {f2:.4f}·{elastic2.K:.3e}) "
                        f"= {_fmt_si_alpha(a)}"
                    ),
                    required_inputs=["α₁", "α₂", "f₁", "f₂", "K₁", "K₂"],
                    assumptions=[
                        "各相近似各向同性",
                        "以体积或静水约束为主要假设",
                        "界面完全结合",
                        "线弹性",
                    ],
                    assumptions_satisfied=True,
                    available=True,
                )
            )
        except CompositeModelError as e:
            results.append(
                ModelResult(
                    model_name=ModelName.TURNER,
                    display_name="Turner 模型",
                    alpha_SI=float("nan"),
                    formula="α_Turner = (f₁ K₁ α₁ + f₂ K₂ α₂) / (f₁ K₁ + f₂ K₂)",
                    substituted="",
                    required_inputs=["α₁", "α₂", "f₁", "f₂", "K₁", "K₂"],
                    assumptions=[],
                    assumptions_satisfied=False,
                    available=False,
                    unavailable_reason=str(e),
                )
            )
    else:
        results.append(
            ModelResult(
                model_name=ModelName.TURNER,
                display_name="Turner 模型",
                alpha_SI=float("nan"),
                formula="α_Turner = (f₁ K₁ α₁ + f₂ K₂ α₂) / (f₁ K₁ + f₂ K₂)",
                substituted="",
                required_inputs=["α₁", "α₂", "f₁", "f₂", "K₁", "K₂"],
                assumptions=[
                    "各相近似各向同性",
                    "以体积或静水约束为主要假设",
                    "界面完全结合",
                    "线弹性",
                ],
                assumptions_satisfied=False,
                available=False,
                unavailable_reason="缺少 K₁ 和/或 K₂（可从 E, ν 换算）。",
            )
        )

    # Kerner — requires matrix/inclusion roles
    matrix_ok = (
        (role1 == PhaseRole.MATRIX and role2 == PhaseRole.INCLUSION)
        or (role2 == PhaseRole.MATRIX and role1 == PhaseRole.INCLUSION)
    )
    if not matrix_ok:
        results.append(
            ModelResult(
                model_name=ModelName.KERNER,
                display_name="Kerner 模型",
                alpha_SI=float("nan"),
                formula=(
                    "α_Kerner = [α_i f_i K_i/(3K_i+4G_m) + α_m f_m K_m/(3K_m+4G_m)] / "
                    "[f_i K_i/(3K_i+4G_m) + f_m K_m/(3K_m+4G_m)]"
                ),
                substituted="",
                required_inputs=["α_m", "α_i", "f_m", "f_i", "K_m", "K_i", "G_m", "matrix/inclusion 身份"],
                assumptions=[
                    "连续基体中分散近似球形颗粒",
                    "基体和颗粒近似各向同性",
                    "界面完全结合",
                    "线弹性",
                    "不考虑颗粒团聚、裂纹和界面反应层",
                ],
                assumptions_satisfied=False,
                available=False,
                unavailable_reason=(
                    "Kerner 模型不允许在 matrix/inclusion 未指定时静默计算。"
                    "请明确指定一相为 matrix、另一相为 inclusion。"
                ),
            )
        )
    else:
        if role1 == PhaseRole.MATRIX:
            alpha_m, alpha_i = alpha1, alpha2
            f_m, f_i = f1, f2
            K_m, G_m = elastic1.K, elastic1.G
            K_i = elastic2.K
            m_name, i_name = phase1_name, phase2_name
        else:
            alpha_m, alpha_i = alpha2, alpha1
            f_m, f_i = f2, f1
            K_m, G_m = elastic2.K, elastic2.G
            K_i = elastic1.K
            m_name, i_name = phase2_name, phase1_name

        if K_m is None or K_i is None or G_m is None:
            results.append(
                ModelResult(
                    model_name=ModelName.KERNER,
                    display_name="Kerner 模型",
                    alpha_SI=float("nan"),
                    formula=(
                        "α_Kerner = [α_i f_i K_i/(3K_i+4G_m) + α_m f_m K_m/(3K_m+4G_m)] / "
                        "[f_i K_i/(3K_i+4G_m) + f_m K_m/(3K_m+4G_m)]"
                    ),
                    substituted="",
                    required_inputs=["α_m", "α_i", "f_m", "f_i", "K_m", "K_i", "G_m"],
                    assumptions=[],
                    assumptions_satisfied=False,
                    available=False,
                    unavailable_reason="缺少 Kerner 所需的 K_m、K_i 或 G_m。",
                )
            )
        else:
            try:
                a = model_kerner(alpha_m, alpha_i, f_m, f_i, K_m, K_i, G_m)
                results.append(
                    ModelResult(
                        model_name=ModelName.KERNER,
                        display_name="Kerner 模型",
                        alpha_SI=a,
                        formula=(
                            "α_Kerner = [α_i f_i K_i/(3K_i+4G_m) + α_m f_m K_m/(3K_m+4G_m)] / "
                            "[f_i K_i/(3K_i+4G_m) + f_m K_m/(3K_m+4G_m)]"
                        ),
                        substituted=(
                            f"matrix={m_name}, inclusion={i_name}; "
                            f"f_m={f_m:.4f}, f_i={f_i:.4f}, "
                            f"K_m={K_m:.3e}, K_i={K_i:.3e}, G_m={G_m:.3e} → {_fmt_si_alpha(a)}"
                        ),
                        required_inputs=["α_m", "α_i", "f_m", "f_i", "K_m", "K_i", "G_m"],
                        assumptions=[
                            "连续基体中分散近似球形颗粒",
                            "基体和颗粒近似各向同性",
                            "界面完全结合",
                            "线弹性",
                            "不考虑颗粒团聚、裂纹和界面反应层",
                        ],
                        assumptions_satisfied=True,
                        available=True,
                    )
                )
            except CompositeModelError as e:
                results.append(
                    ModelResult(
                        model_name=ModelName.KERNER,
                        display_name="Kerner 模型",
                        alpha_SI=float("nan"),
                        formula=(
                            "α_Kerner = [α_i f_i K_i/(3K_i+4G_m) + α_m f_m K_m/(3K_m+4G_m)] / "
                            "[f_i K_i/(3K_i+4G_m) + f_m K_m/(3K_m+4G_m)]"
                        ),
                        substituted="",
                        required_inputs=["α_m", "α_i", "f_m", "f_i", "K_m", "K_i", "G_m"],
                        assumptions=[],
                        assumptions_satisfied=False,
                        available=False,
                        unavailable_reason=str(e),
                    )
                )

    return results
