"""Bilingual term glossary for CTE calculator UI (hover / reference)."""

from __future__ import annotations

from typing import TypedDict


class Term(TypedDict):
    zh: str
    en: str
    abbr: str
    layer: str  # L1 | L2 | L3 | input | model | unit | meta
    def_zh: str
    note: str


# Curated terms shown in UI glossary (order = display order)
GLOSSARY: list[Term] = [
    {
        "zh": "线性热膨胀系数",
        "en": "Coefficient of Thermal Expansion",
        "abbr": "CTE / α",
        "layer": "meta",
        "def_zh": "温度升高 1 K 时，单位长度的相对伸长量。内部 SI 单位为 1/K。",
        "note": "界面常以 10⁻⁶/K 显示；勿与体积热膨胀 β≈3α 混淆（本工具用线性）。",
    },
    {
        "zh": "晶面族 CTE",
        "en": "Plane-family CTE",
        "abbr": "α_hkl",
        "layer": "L1",
        "def_zh": "某一晶面族方向上的晶格热膨胀，常由 d-spacing–T 拟合得到。",
        "note": "第 1 层输入。不等于材料“唯一 CTE”。",
    },
    {
        "zh": "相表观 CTE",
        "en": "Phase apparent CTE (XRD-weighted)",
        "abbr": "α_phase",
        "layer": "L2",
        "def_zh": "由多晶面 α_hkl 经强度（峰面积与 R）加权得到的相尺度表观值。",
        "note": "第 2 层。依赖织构/峰拟合/R 定义，≠ 严格本征宏观 CTE。",
    },
    {
        "zh": "复合有效 CTE",
        "en": "Effective composite CTE",
        "abbr": "α_eff",
        "layer": "L3",
        "def_zh": "两相在给定体积分数与力学/几何假设下的有效热膨胀估计。",
        "note": "第 3 层。多模型给出区间，不是单一标定真值。",
    },
    {
        "zh": "体积分数",
        "en": "Volume fraction",
        "abbr": "f₁, f₂",
        "layer": "input",
        "def_zh": "各相占总体积的比例，约束 f₁+f₂=1（孔隙另议）。",
        "note": "禁止把质量分数 wt% 直接当 f 填入。",
    },
    {
        "zh": "R 因子",
        "en": "Structure / relative intensity factor",
        "abbr": "R",
        "layer": "input",
        "def_zh": "用于把观测峰面积校正为可比较权重的因子；本库默认 no_LP 口径。",
        "note": "默认 I_corr = 峰面积 / R。不同实验室定义可能不同。",
    },
    {
        "zh": "校正强度",
        "en": "Corrected intensity",
        "abbr": "I_corr",
        "layer": "L2",
        "def_zh": "按所选 R 定义得到的权重前强度，再归一为 w_j。",
        "note": "见 R 定义四选一；错定义会系统性偏置却仍可能“算出数”。",
    },
    {
        "zh": "串联 / 混合律",
        "en": "Rule of Mixtures (iso-stress free expansion)",
        "abbr": "ROM",
        "layer": "model",
        "def_zh": "α = f₁α₁ + f₂α₂。无弹性约束的体积分数混合。",
        "note": "筛选级；E₁=E₂ 时与并联数值相同。",
    },
    {
        "zh": "并联 / 等应变",
        "en": "Parallel / iso-strain model",
        "abbr": "Parallel",
        "layer": "model",
        "def_zh": "两相总应变相同，α 按 fE 加权。",
        "note": "需要两相 E>0。",
    },
    {
        "zh": "Turner 模型",
        "en": "Turner model",
        "abbr": "Turner",
        "layer": "model",
        "def_zh": "基于体积模量约束的有效 CTE 估计。",
        "note": "需要 K（或由 E,ν 换算）。",
    },
    {
        "zh": "Kerner 模型",
        "en": "Kerner model",
        "abbr": "Kerner",
        "layer": "model",
        "def_zh": "球形夹杂–连续基体近似下的有效 CTE。",
        "note": "必须显式 matrix/inclusion；角色交换可改变数值。",
    },
    {
        "zh": "基体 / 夹杂",
        "en": "Matrix / Inclusion",
        "abbr": "role",
        "layer": "input",
        "def_zh": "Kerner 等模型中的相角色：连续相为基体，分散相为夹杂。",
        "note": "缺角色时本工具不静默计算 Kerner。",
    },
    {
        "zh": "杨氏模量",
        "en": "Young's modulus",
        "abbr": "E",
        "layer": "input",
        "def_zh": "线弹性刚度。界面输入 GPa，内部换算为 Pa。",
        "note": "并联直接使用 E；Turner/Kerner 常经 E,ν 得 K,G。",
    },
    {
        "zh": "泊松比",
        "en": "Poisson's ratio",
        "abbr": "ν",
        "layer": "input",
        "def_zh": "横向应变与轴向应变之比的负值约定下的弹性常数。",
        "note": "须 −1 < ν < 0.5。",
    },
    {
        "zh": "体积模量 / 剪切模量",
        "en": "Bulk / Shear modulus",
        "abbr": "K, G",
        "layer": "input",
        "def_zh": "由 E,ν 换算：K=E/(3(1−2ν))，G=E/(2(1+ν))。",
        "note": "UI 主路径只填 E,ν；库层支持直接 K,G。",
    },
    {
        "zh": "模型区间",
        "en": "Model discrete range",
        "abbr": "interval",
        "layer": "meta",
        "def_zh": "当前可用解析模型给出的 α_eff 最小–最大范围。",
        "note": "是模型离散，不是实验误差棒，也不是 MC 不确定度。",
    },
    {
        "zh": "Monte Carlo",
        "en": "Monte Carlo uncertainty",
        "abbr": "MC",
        "layer": "meta",
        "def_zh": "对带标准差的输入抽样，传播到选定模型的 α 分布。",
        "note": "未设输入 SD 时几乎不展开；勿把空 MC 当实验误差。",
    },
]


LAYER_LABEL = {
    "L1": "第1层·晶面",
    "L2": "第2层·相表观",
    "L3": "第3层·复合",
    "input": "输入量",
    "model": "模型",
    "unit": "单位",
    "meta": "读数/方法",
}


def glossary_as_rows() -> list[dict[str, str]]:
    """Rows for st.dataframe / markdown table."""
    rows = []
    for t in GLOSSARY:
        rows.append(
            {
                "中文": t["zh"],
                "English": t["en"],
                "符号": t["abbr"],
                "类别": LAYER_LABEL.get(t["layer"], t["layer"]),
                "定义": t["def_zh"],
                "注意": t["note"],
            }
        )
    return rows


def term_tooltip_html(abbr: str, zh: str, def_zh: str) -> str:
    """Single chip with native title tooltip."""
    safe = def_zh.replace('"', "'")
    return (
        f'<span class="cte-term" title="{safe}">{zh}'
        f'<span class="cte-term-en"> · {abbr}</span></span>'
    )
