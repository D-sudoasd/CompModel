"""Multiphase scalar and isotropic homogenization. All physical inputs use SI.

Model definitions and references: docs/effective_properties.md.
No inferred matrix, inferred units, or automatic fraction normalization.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math

from cte_app.composite_models import model_kerner, young_poisson_to_KG


class HomogenizationError(ValueError):
    """Invalid composition, physical parameter, or model selection."""


@dataclass(frozen=True)
class Property:
    label: str
    unit: str
    scale: float = 1.0


PROPERTIES = {
    "E": Property("杨氏模量 E", "GPa", 1e9),
    "nu": Property("泊松比 ν", "1"),
    "K": Property("体积模量 K", "GPa", 1e9),
    "G": Property("剪切模量 G", "GPa", 1e9),
    "alpha": Property("线膨胀系数 α", "10⁻⁶/K", 1e-6),
    "k": Property("导热系数 k", "W/(m·K)"),
    "sigma": Property("电导率 σ", "S/m"),
    "rho": Property("密度 ρ", "kg/m³"),
    "cp": Property("质量比热容 cp", "J/(kg·K)"),
    "custom": Property("自定义标量系数", "用户指定"),
}
FAMILIES = {
    "elastic": "各向同性弹性",
    "alpha": "热膨胀系数",
    "k": "导热系数",
    "sigma": "电导率",
    "thermal": "密度与比热容",
    "custom": "自定义标量系数",
}


@dataclass
class Constituent:
    name: str
    fraction: float
    properties: dict[str, float] = field(default_factory=dict)
    role: str = "unspecified"
    provenance: dict = field(default_factory=dict)


@dataclass
class Composite:
    phases: list[Constituent]
    basis: str = "volume"
    title: str = "复合材料"
    custom_name: str = "自定义系数"
    custom_unit: str = "1"


@dataclass
class Estimate:
    model: str
    values: dict[str, float]
    kind: str
    assumptions: str
    formula: str
    reason: str = ""


def _finite(value: float, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise HomogenizationError(f"{label} 必须为有限数值。")


def volume_fractions(project: Composite) -> list[float]:
    if not project.phases:
        raise HomogenizationError("至少需要一个组成相。")
    if project.basis not in {"volume", "mass"}:
        raise HomogenizationError("分数类型必须为 volume 或 mass。")
    names = [p.name for p in project.phases]
    if any(not isinstance(n, str) or not n.strip() for n in names) or len(set(names)) != len(names):
        raise HomogenizationError("相名称必须非空且不重复。")
    for p in project.phases:
        _finite(p.fraction, f"{p.name} 分数")
        if not 0 <= p.fraction <= 1:
            raise HomogenizationError("各相分数必须在 0–1 之间。")
        if p.role not in {"matrix", "inclusion", "unspecified"}:
            raise HomogenizationError(f"{p.name} 的角色无效。")
        for key, value in p.properties.items():
            if key not in PROPERTIES:
                raise HomogenizationError(f"未知属性：{key}")
            _finite(value, f"{p.name}: {key}")
            if key in {"E", "K", "G", "rho", "cp"} and value <= 0:
                raise HomogenizationError(f"{p.name}: {key} 必须 > 0。")
            if key in {"k", "sigma"} and value < 0:
                raise HomogenizationError(f"{p.name}: {key} 必须 ≥ 0。")
            if key == "nu" and not -1 < value < 0.5:
                raise HomogenizationError(f"{p.name}: ν 必须满足 −1 < ν < 0.5。")
    fractions = [p.fraction for p in project.phases]
    total = math.fsum(fractions)
    if not math.isclose(total, 1.0, rel_tol=0, abs_tol=1e-9):
        raise HomogenizationError(f"分数之和必须为 1，当前为 {total:.12g}；请显式调整。")
    if project.basis == "mass":
        fractions = [f / _required(p, "rho") if f > 0 else 0.0
                     for p, f in zip(project.phases, fractions)]
        total = math.fsum(fractions)
    return [f / total for f in fractions]


def _required(phase: Constituent, key: str) -> float:
    if key not in phase.properties:
        raise HomogenizationError(f"{phase.name} 缺少 {key}。")
    return phase.properties[key]


def _elastic(phase: Constituent) -> tuple[float, float, float]:
    p = phase.properties
    if "E" in p and "nu" in p:
        k, g = young_poisson_to_KG(p["E"], p["nu"])
        for key, computed in (("K", k), ("G", g)):
            if key in p and not math.isclose(p[key], computed, rel_tol=1e-6):
                raise HomogenizationError(f"{phase.name}: E、ν 与 {key} 不一致。")
        return k, g, p["E"]
    k, g = _required(phase, "K"), _required(phase, "G")
    values = elastic_values(k, g)
    for key in ("E", "nu"):
        if key in p and not math.isclose(p[key], values[key], rel_tol=1e-6, abs_tol=1e-12):
            raise HomogenizationError(f"{phase.name}: K、G 与 {key} 不一致。")
    return k, g, values["E"]


def elastic_values(k: float, g: float) -> dict[str, float]:
    return {"K": k, "G": g, "E": 9*k*g/(3*k+g), "nu": (3*k-2*g)/(2*(3*k+g))}


def arithmetic(values: list[float], fractions: list[float]) -> float:
    return math.fsum(x*f for x, f in zip(values, fractions))


def harmonic(values: list[float], fractions: list[float]) -> float:
    if any(x < 0 for x in values):
        raise HomogenizationError("调和平均不适用于负系数。")
    if any(x == 0 and f > 0 for x, f in zip(values, fractions)):
        return 0.0
    return 1 / math.fsum(f/x for x, f in zip(values, fractions) if f > 0)


def _shifted(values: list[float], fractions: list[float], shift: float) -> float:
    return harmonic([x+shift for x in values], fractions) - shift


def _matrix_pair(phases: list[Constituent], fractions: list[float]):
    if len(phases) != 2 or sorted(p.role for p in phases) != ["inclusion", "matrix"]:
        raise HomogenizationError("此模型需要恰好两相，并显式指定 matrix 和 inclusion。")
    m = next(i for i, p in enumerate(phases) if p.role == "matrix")
    i = 1-m
    return phases[m], phases[i], fractions[m], fractions[i]


def evaluate(project: Composite, family: str, *, xi: float = 2.0) -> list[Estimate]:
    """Return every applicable model and explicit reasons for unavailable models."""
    if family not in FAMILIES:
        raise HomogenizationError(f"未知物理量：{family}")
    fractions = volume_fractions(project)
    active = [(p, f) for p, f in zip(project.phases, fractions) if f > 0]
    phases, f = [p for p, _ in active], [v for _, v in active]
    results: list[Estimate] = []

    def add(model, kind, assumptions, formula, calculation):
        try:
            values = calculation()
            if not all(math.isfinite(v) for v in values.values()):
                raise HomogenizationError("数值超出计算范围。")
            results.append(Estimate(model, values, kind, assumptions, formula))
        except (HomogenizationError, ArithmeticError) as exc:
            results.append(Estimate(model, {}, kind, assumptions, formula, str(exc)))

    def values(key):
        return [_required(p, key) for p in phases]

    if family == "elastic":
        def kg_model(rule):
            kg = [_elastic(p) for p in phases]
            return elastic_values(rule([v[0] for v in kg], f), rule([v[1] for v in kg], f))

        assumption = "各相线弹性、各向同性、完全结合；有效材料宏观各向同性。E 由有效 K、G 换算。"
        add("Voigt", "上界", assumption + " 均匀应变。", "K=ΣfKᵢ; G=ΣfGᵢ", lambda: kg_model(arithmetic))
        add("Reuss", "下界", assumption + " 均匀应力。", "K=1/Σ(f/Kᵢ); G=1/Σ(f/Gᵢ)", lambda: kg_model(harmonic))
        add("Hill", "估计", assumption + " Voigt、Reuss 的 K、G 算术平均。", "K=(K_V+K_R)/2; G=(G_V+G_R)/2",
            lambda: kg_model(lambda x, w: (arithmetic(x, w)+harmonic(x, w))/2))

        def hs(upper):
            kg = [_elastic(p) for p in phases]
            ks, gs = [v[0] for v in kg], [v[1] for v in kg]
            select = max if upper else min
            kr, gr = select(ks), select(gs)
            zeta = gr*(9*kr+8*gr)/(6*(kr+2*gr))
            return elastic_values(_shifted(ks, f, 4*gr/3), _shifted(gs, f, zeta))

        for upper in (False, True):
            add("Hashin–Shtrikman " + ("upper" if upper else "lower"), "上界" if upper else "下界",
                assumption, "K=⟨1/(Kᵢ+4G₀/3)⟩⁻¹−4G₀/3; G=⟨1/(Gᵢ+ζ₀)⟩⁻¹−ζ₀",
                lambda upper=upper: hs(upper))

        def mt():
            m, i, fm, fi = _matrix_pair(project.phases, fractions)
            km, gm, _ = _elastic(m)
            ki, gi, _ = _elastic(i)
            z = gm*(9*km+8*gm)/(6*(km+2*gm))
            return elastic_values(km+fi*(ki-km)/(1+fm*(ki-km)/(km+4*gm/3)),
                                  gm+fi*(gi-gm)/(1+fm*(gi-gm)/(gm+z)))

        add("Mori–Tanaka", "估计", assumption + " 连续基体、球形夹杂；不描述团聚和界面层。",
            "K=Kₘ+fᵢΔK/[1+fₘΔK/(Kₘ+4Gₘ/3)]; G=Gₘ+fᵢΔG/[1+fₘΔG/(Gₘ+ζₘ)]", mt)

        def halpin():
            _finite(xi, "ξ")
            if xi <= 0:
                raise HomogenizationError("Halpin–Tsai 的 ξ 必须 > 0。")
            m, i, _, fi = _matrix_pair(project.phases, fractions)
            em, ei = _required(m, "E"), _required(i, "E")
            eta = (ei/em-1)/(ei/em+xi)
            return {"E": em*(1+xi*eta*fi)/(1-eta*fi)}

        add("Halpin–Tsai", "方向性半经验估计", "仅给出指定方向 E；ξ 由形貌、方向或标定指定，不是各向同性模量边界。",
            "E=Eₘ(1+ξηfᵢ)/(1−ηfᵢ); η=(Eᵢ/Eₘ−1)/(Eᵢ/Eₘ+ξ)", halpin)
    elif family in {"k", "sigma", "custom"}:
        key = family
        transport = family != "custom"
        add("Arithmetic", "并联 / 上界" if transport else "混合规则",
            "标量、线性、界面无阻抗；层状材料沿层方向。" if transport else "仅按体积分数算术平均；物理适用性由用户判断。",
            "x=Σfᵢxᵢ", lambda: {key: arithmetic(values(key), f)})
        add("Harmonic", "串联 / 下界" if transport else "混合规则",
            "标量、线性、界面无阻抗；层状材料垂直层方向。" if transport else "非负系数的调和平均，不自动赋予物理意义。",
            "x=1/Σ(fᵢ/xᵢ)", lambda: {key: harmonic(values(key), f)})

        def geometric():
            x = values(key)
            if min(x) <= 0:
                raise HomogenizationError("几何平均要求所有参与相系数 > 0。")
            return {key: math.exp(arithmetic([math.log(v) for v in x], f))}

        add("Geometric", "经验混合规则", "正标量系数；不作为严格上下界。", "x=exp(Σfᵢ ln xᵢ)", geometric)
        if transport:
            for upper in (False, True):
                def scalar_hs(upper=upper):
                    x = values(key)
                    ref = (max if upper else min)(x)
                    return {key: max(0.0, _shifted(x, f, 2*ref))}
                add("Hashin–Shtrikman " + ("upper" if upper else "lower"), "上界" if upper else "下界",
                    "三维、宏观各向同性、非负标量输运系数、界面无阻抗。", "x=⟨1/(xᵢ+2x₀)⟩⁻¹−2x₀", scalar_hs)

            def maxwell():
                m, i, fm, fi = _matrix_pair(project.phases, fractions)
                xm, xi_value = _required(m, key), _required(i, key)
                if fi == 1:
                    return {key: xi_value}
                if xm <= 0:
                    raise HomogenizationError("Maxwell 模型要求连续基体输运系数 > 0。")
                return {key: xm*(xi_value+2*xm+2*fi*(xi_value-xm))/(xi_value+2*xm-fi*(xi_value-xm))}

            add("Maxwell", "估计", "两相、连续基体、分散球形夹杂、界面无阻抗；不描述导电网络。",
                "x=xₘ[xᵢ+2xₘ+2fᵢ(xᵢ−xₘ)]/[xᵢ+2xₘ−fᵢ(xᵢ−xₘ)]", maxwell)
    elif family == "alpha":
        add("ROM", "筛选估计", "自由伸长、无弹性约束。", "α=Σfᵢαᵢ", lambda: {"alpha": arithmetic(values("alpha"), f)})

        def constrained(index):
            def stiffness(p):
                key = "E" if index == 2 else "K"
                if key in p.properties:
                    # Check consistency if a full elastic pair was also supplied.
                    if {"E", "nu"} <= p.properties.keys() or {"K", "G"} <= p.properties.keys():
                        _elastic(p)
                    return p.properties[key]
                return _elastic(p)[index]
            weights = [v*stiffness(p) for p, v in zip(phases, f)]
            return {"alpha": arithmetic(values("alpha"), weights)/sum(weights)}

        add("Parallel", "一维估计", "相同轴向总应变、线弹性、外力合力为零。", "α=ΣfᵢEᵢαᵢ/ΣfᵢEᵢ", lambda: constrained(2))
        add("Turner", "估计", "各向同性、静水约束近似、界面完全结合。", "α=ΣfᵢKᵢαᵢ/ΣfᵢKᵢ", lambda: constrained(0))

        def kerner():
            m, i, fm, fi = _matrix_pair(project.phases, fractions)
            km, gm, _ = _elastic(m)
            ki, _, _ = _elastic(i)
            return {"alpha": model_kerner(_required(m, "alpha"), _required(i, "alpha"), fm, fi, km, ki, gm)}

        add("Kerner", "估计", "两相、连续基体、球形夹杂、各向同性、完全结合。",
            "α=Σ[αⱼfⱼKⱼ/(3Kⱼ+4Gₘ)] / Σ[fⱼKⱼ/(3Kⱼ+4Gₘ)]", kerner)
    else:
        add("Volume density", "守恒混合", "体积可加，无反应引起的体积变化。", "ρ=Σfᵢρᵢ", lambda: {"rho": arithmetic(values("rho"), f)})

        def heat():
            rho = values("rho")
            volumetric = arithmetic([r*c for r, c in zip(rho, values("cp"))], f)
            effective_rho = arithmetic(rho, f)
            return {"rho": effective_rho, "cp": volumetric/effective_rho}

        add("Mass heat capacity", "守恒混合", "各相局部热平衡；无相变潜热；cp 按质量加权。", "cp=Σ(fᵢρᵢcpᵢ)/Σ(fᵢρᵢ)", heat)
    return results
