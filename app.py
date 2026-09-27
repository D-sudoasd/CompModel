"""
Two-Phase Composite CTE Calculator / 两相复合材料 CTE 计算器
P0：工程 JSON 往返、结构模板、R 匹配门闩、稳定 session、可审计导出。
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from cte_app.composite_models import compute_all_models, resolve_elastic_properties
from cte_app.export import (
    export_excel_bytes,
    export_json_bytes,
    export_summary_csv,
    phase_weights_df,
    project_to_dict,
)
from cte_app.model_advisor import advise_models
from cte_app.phase_weighting import PhaseWeightingError, compute_phase_xrd_cte
from cte_app.plotting import (
    mc_histogram,
    model_comparison_bar,
    phase_weight_bars,
    sensitivity_bar,
    series_parallel_delta_gauge,
)
from cte_app import ui_style
from cte_app.project_io import (
    PROJECT_SCHEMA_VERSION,
    ProjectIOError,
    dump_project_input,
    parse_project_inputs,
    project_to_ui_state,
    snapshot_inputs_from_calc,
)
from cte_app.r_integrity import UnmatchedRPolicy, evaluate_r_gate, model_interval_summary
from cte_app.r_library import apply_r_to_plane_df, list_r_libraries, suggest_library_for_phase
from cte_app.schemas import (
    R_FACTOR_FORMULAS,
    CrystalSystem,
    MeasurementDirection,
    MicrostructureType,
    ModelName,
    PhaseInput,
    PhaseRole,
    PlaneFamilyRow,
    ProjectSettings,
    RFactorDefinition,
)
from cte_app.uncertainty import run_monte_carlo
from cte_app.units import format_alpha, modulus_from_si
from cte_app.validation import effective_volume_fractions, validate_project

SAMPLE_DIR = Path(__file__).resolve().parent / "sample_data"
TEMPLATE_DIR = SAMPLE_DIR / "templates"

PLANE_COLS = ["晶面", "α (10⁻⁶/K)", "峰面积", "R因子"]
PLANE_DEFAULT_1 = pd.DataFrame(
    [
        {"晶面": "(1 1 0)β", "α (10⁻⁶/K)": 4.50, "峰面积": 55.6, "R因子": 1.0},
        {"晶面": "(2 0 0)β", "α (10⁻⁶/K)": -0.15, "峰面积": 1.3, "R因子": 1.0},
        {"晶面": "(2 1 1)β", "α (10⁻⁶/K)": 5.00, "峰面积": 2.8, "R因子": 1.0},
    ]
)
PLANE_DEFAULT_2 = pd.DataFrame(
    [
        {"晶面": '(0 2 0)α"', "α (10⁻⁶/K)": -17.04, "峰面积": 40.4, "R因子": 1.0},
        {"晶面": '(1 1 1)α"', "α (10⁻⁶/K)": 8.02, "峰面积": 24.6, "R因子": 1.0},
        {"晶面": '(0 2 1)α"', "α (10⁻⁶/K)": -8.51, "峰面积": 8.1, "R因子": 1.0},
    ]
)

MICRO_LABELS = {
    "spherical_particles": "球形颗粒（基体+增强相）",
    "random_particles": "随机颗粒",
    "layered": "层状",
    "aligned_fiber": "取向纤维",
    "co_continuous": "双连续",
    "unknown": "未知 / 只做筛选",
}

RDEF_LABELS = {
    "theoretical_relative_intensity": "理论相对强度：I = 峰面积 / R",
    "multiplicative_correction": "乘性修正：I = 峰面积 × R",
    "already_corrected_weight": "已是权重：I = 峰面积",
    "custom_weight": "自定义权重列（高级）",
}

TEMPLATE_META = {
    "al_sic.json": {
        "label": "Al–SiC 教学示例（XRD 手填 R）",
        "note": "手算对照；非你的实验数据。",
    },
    "beta_alpha_pp_structure.json": {
        "label": "β–α″ 结构模板（空峰面积，填测后点填充 R）",
        "note": "结构骨架；E/ν 为占位，α/峰面积请换成实测。",
    },
    "rom_blank.json": {
        "label": "纯 ROM 空白（直接标量 CTE）",
        "note": "仅 f+α 起点；E 为空则并联不可用。",
    },
}

# Widget keys owned by apply_ui_state / restore
_UI_SCALAR_KEYS = (
    "p1_name",
    "p2_name",
    "f1",
    "a1_direct",
    "a2_direct",
    "E1",
    "E2",
    "nu1",
    "nu2",
    "input_mode",
    "rdef",
    "microstructure",
    "direction",
    "porosity",
    "renorm",
    "crystal1",
    "crystal2",
    "swap_roles",
)


def _empty_planes() -> pd.DataFrame:
    return pd.DataFrame(columns=PLANE_COLS)


def _records_to_df(records: list | None) -> pd.DataFrame:
    if not records:
        return _empty_planes()
    df = pd.DataFrame(records)
    for c in PLANE_COLS:
        if c not in df.columns:
            df[c] = 0.0 if c != "晶面" else ""
    return df[PLANE_COLS].copy()


def _init_state() -> None:
    defaults = {
        "planes_1": PLANE_DEFAULT_1.copy(),
        "planes_2": PLANE_DEFAULT_2.copy(),
        "calc_result": None,
        "mc_result": None,
        "p1_name": "相1-基体",
        "p2_name": "相2-增强相",
        "f1": 0.7,
        "a1_direct": 22.5,
        "a2_direct": 4.5,
        "E1": 70.0,
        "E2": 400.0,
        "nu1": 0.33,
        "nu2": 0.17,
        "input_mode": "scalar",
        "rdef": "theoretical_relative_intensity",
        "microstructure": "spherical_particles",
        "direction": MeasurementDirection.ISOTROPIC_AVERAGE.value,
        "porosity": 0.0,
        "renorm": False,
        "crystal1": CrystalSystem.CUBIC.value,
        "crystal2": CrystalSystem.CUBIC.value,
        "swap_roles": False,
        "unmatched_r_policy": UnmatchedRPolicy.FAIL.value,
        "accept_unmatched_r": False,
        "last_ok_inputs": None,
        "r_fill_report_planes_1": None,
        "r_fill_report_planes_2": None,
        "sidebar_alpha_unit": "1e-6/K",
        "sidebar_sig_figs": 3,
        "scroll_to_results": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _clear_plane_editors() -> None:
    for ed_key in ("ed_planes_1", "ed_planes_2"):
        if ed_key in st.session_state:
            del st.session_state[ed_key]


def apply_ui_state(ui: dict, *, clear_results: bool = True) -> None:
    """Write project_to_ui_state / snapshot dict into session_state."""
    st.session_state["p1_name"] = ui.get("p1_name", "相1")
    st.session_state["p2_name"] = ui.get("p2_name", "相2")
    st.session_state["f1"] = float(ui.get("f1", 0.5))
    st.session_state["a1_direct"] = float(ui.get("a1_direct", 10.0))
    st.session_state["a2_direct"] = float(ui.get("a2_direct", 5.0))
    st.session_state["E1"] = float(ui.get("E1", 0.0))
    st.session_state["E2"] = float(ui.get("E2", 0.0))
    st.session_state["nu1"] = float(ui.get("nu1", 0.33))
    st.session_state["nu2"] = float(ui.get("nu2", 0.33))
    st.session_state["input_mode"] = ui.get("input_mode", "scalar")
    st.session_state["rdef"] = ui.get("rdef", "theoretical_relative_intensity")
    micro = ui.get("microstructure", "unknown")
    if micro not in MICRO_LABELS:
        micro = "unknown"
    st.session_state["microstructure"] = micro
    st.session_state["direction"] = ui.get(
        "direction", MeasurementDirection.ISOTROPIC_AVERAGE.value
    )
    st.session_state["porosity"] = float(ui.get("porosity", 0.0))
    st.session_state["renorm"] = bool(ui.get("renorm", False))
    st.session_state["crystal1"] = ui.get("crystal1", "unknown")
    st.session_state["crystal2"] = ui.get("crystal2", "unknown")
    st.session_state["swap_roles"] = bool(ui.get("swap_roles", False))
    st.session_state["planes_1"] = _records_to_df(ui.get("planes_1_records"))
    st.session_state["planes_2"] = _records_to_df(ui.get("planes_2_records"))
    if ui.get("alpha_display_unit"):
        st.session_state["sidebar_alpha_unit"] = ui["alpha_display_unit"]
    if ui.get("display_sig_figs"):
        st.session_state["sidebar_sig_figs"] = int(ui["display_sig_figs"])
    st.session_state["r_fill_report_planes_1"] = None
    st.session_state["r_fill_report_planes_2"] = None
    st.session_state["accept_unmatched_r"] = False
    _clear_plane_editors()
    if clear_results:
        st.session_state["calc_result"] = None
        st.session_state["mc_result"] = None


def load_project_dict(data: dict) -> None:
    settings, phase1, phase2, _meta = parse_project_inputs(data)
    ui = project_to_ui_state(settings, phase1, phase2)
    apply_ui_state(ui, clear_results=True)


@st.cache_data
def load_json_path(path_str: str) -> dict:
    path = Path(path_str)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def list_templates() -> list[tuple[str, str]]:
    """Return [(filename, label), ...]."""
    out = []
    if not TEMPLATE_DIR.is_dir():
        return out
    for name, meta in TEMPLATE_META.items():
        if (TEMPLATE_DIR / name).exists():
            out.append((name, meta["label"]))
    # any extra json in templates
    for p in sorted(TEMPLATE_DIR.glob("*.json")):
        if p.name not in TEMPLATE_META:
            out.append((p.name, p.stem))
    return out


def plane_df_to_rows(df: pd.DataFrame) -> list[PlaneFamilyRow]:
    rows: list[PlaneFamilyRow] = []
    if df is None or df.empty:
        return rows
    for rec in df.to_dict(orient="records"):
        label = str(rec.get("晶面") or "").strip() or "(hkl)"
        alpha = rec.get("α (10⁻⁶/K)")
        area = rec.get("峰面积", 0.0)
        rfac = rec.get("R因子", 1.0)
        if alpha is None or (isinstance(alpha, float) and np.isnan(alpha)):
            continue
        try:
            rows.append(
                PlaneFamilyRow(
                    plane_family_label=label,
                    alpha_hkl=float(alpha),
                    alpha_unit="1e-6/K",
                    peak_area=float(area) if area is not None and not pd.isna(area) else 0.0,
                    R_factor=float(rfac) if rfac is not None and not pd.isna(rfac) else 1.0,
                    enabled=True,
                )
            )
        except Exception:
            continue
    return rows


def sample_planes_to_simple(plane_rows: list[dict]) -> pd.DataFrame:
    out = []
    for r in plane_rows:
        out.append(
            {
                "晶面": r.get("plane_family_label")
                or f"({r.get('h', 0)}{r.get('k', 0)}{r.get('l', 0)})",
                "α (10⁻⁶/K)": r.get("alpha_hkl", 0.0),
                "峰面积": r.get("peak_area", 0.0),
                "R因子": r.get("R_factor", 1.0),
            }
        )
    return pd.DataFrame(out) if out else _empty_planes()


def build_phase(
    name: str,
    role: PhaseRole,
    vf: float,
    use_direct: bool,
    direct_alpha: float | None,
    planes_df: pd.DataFrame,
    rdef: str,
    E: float | None,
    nu: float | None,
    crystal: str = "cubic",
) -> PhaseInput:
    return PhaseInput(
        phase_name=name,
        crystal_system=CrystalSystem(crystal),
        role=role,
        volume_fraction=vf,
        Young_modulus_E=E if E and E > 0 else None,
        Poisson_ratio_nu=nu if nu is not None else None,
        modulus_unit="GPa",
        temperature_min=20.0,
        temperature_max=300.0,
        r_factor_definition=RFactorDefinition(rdef),
        plane_rows=[] if use_direct else plane_df_to_rows(planes_df),
        use_direct_scalar_cte=use_direct,
        direct_alpha=direct_alpha,
        direct_alpha_unit="1e-6/K",
    )


def run_calculation(
    phase1: PhaseInput,
    phase2: PhaseInput,
    settings: ProjectSettings,
    *,
    r_match_reports: dict | None = None,
    r_gate_warnings: list[str] | None = None,
) -> dict:
    """Core pipeline; only called on button click."""
    report = validate_project(phase1, phase2, settings)
    warnings = list(report.warnings)
    if r_gate_warnings:
        warnings.extend(r_gate_warnings)
    if not report.ok:
        return {"ok": False, "errors": report.errors, "warnings": warnings}

    try:
        w1 = compute_phase_xrd_cte(phase1, settings.cubic_cte_tolerance_relative)
        w2 = compute_phase_xrd_cte(phase2, settings.cubic_cte_tolerance_relative)
    except PhaseWeightingError as e:
        return {"ok": False, "errors": [str(e)], "warnings": warnings}

    warnings.extend(w1.warnings)
    warnings.extend(w2.warnings)

    f1, f2, notes = effective_volume_fractions(phase1, phase2, settings)
    warnings.extend(notes)
    e1 = resolve_elastic_properties(phase1, settings.elastic_consistency_tolerance_relative)
    e2 = resolve_elastic_properties(phase2, settings.elastic_consistency_tolerance_relative)
    warnings.extend(e1.warnings)
    warnings.extend(e2.warnings)

    results = compute_all_models(
        w1.alpha_phase_xrd_SI,
        w2.alpha_phase_xrd_SI,
        f1,
        f2,
        e1,
        e2,
        phase1.role,
        phase2.role,
        phase1.phase_name,
        phase2.phase_name,
    )
    recommendation = advise_models(
        settings.microstructure,
        settings.measurement_direction,
        e1,
        e2,
        phase1.role,
        phase2.role,
        results,
    )
    warnings.extend(recommendation.notes)
    warnings.extend(recommendation.risks)

    unit = settings.alpha_display_unit
    sig = settings.display_sig_figs
    interval = model_interval_summary(results, unit=unit, sig=sig)

    return {
        "ok": True,
        "errors": [],
        "warnings": warnings,
        "phase1": phase1,
        "phase2": phase2,
        "settings": settings,
        "w1": w1,
        "w2": w2,
        "f1": f1,
        "f2": f2,
        "e1": e1,
        "e2": e2,
        "results": results,
        "recommendation": recommendation,
        "assumptions": list(recommendation.assumptions),
        "r_match_reports": r_match_reports or {},
        "model_interval": interval,
    }


def _editor_height(n_rows: int, user_height: int | None = None) -> int:
    if user_height is not None:
        return int(user_height)
    auto = 48 + 38 * max(n_rows, 4) + 40
    return int(min(520, max(320, auto)))


def simple_plane_editor(
    state_key: str,
    height: int | None = None,
    title: str = "",
) -> pd.DataFrame:
    base = st.session_state[state_key]
    if not isinstance(base, pd.DataFrame):
        base = pd.DataFrame(base)
    for c in PLANE_COLS:
        if c not in base.columns:
            base[c] = 0.0 if c != "晶面" else ""
    base = base[PLANE_COLS].copy()
    st.session_state[state_key] = base

    n = len(base)
    h = _editor_height(n, height)
    if title:
        st.caption(f"{title} · 当前 **{n}** 行 · 表高 {h}px")

    edited = st.data_editor(
        base,
        num_rows="dynamic",
        use_container_width=True,
        height=h,
        hide_index=True,
        key=f"ed_{state_key}",
        column_config={
            "晶面": st.column_config.TextColumn(
                "晶面 (hkl)",
                width="large",
                help="如 (1 1 0)β 或 (020)α\"，用于匹配内置 R 表",
            ),
            "α (10⁻⁶/K)": st.column_config.NumberColumn(
                "α (10⁻⁶/K)",
                format="%.4f",
                width="medium",
                help="该晶面族 CTE（输入固定 10⁻⁶/K，与侧栏显示单位无关）",
            ),
            "峰面积": st.column_config.NumberColumn(
                "峰面积 Area",
                format="%.3f",
                width="medium",
            ),
            "R因子": st.column_config.NumberColumn(
                "R 因子",
                format="%.5f",
                width="medium",
                help="可用上方内置 R 表一键填充",
            ),
        },
    )
    st.caption("提示：双击单元格编辑 · Tab 下一格 · 表格底部 **＋** 添加晶面行")
    return edited


def _fill_r_from_library(phase_key: str, lib_id: str) -> None:
    base = st.session_state.get(phase_key, PLANE_DEFAULT_1.copy())
    if not isinstance(base, pd.DataFrame):
        base = pd.DataFrame(base)
    ed_key = f"ed_{phase_key}"
    if ed_key in st.session_state and isinstance(st.session_state[ed_key], pd.DataFrame):
        base = st.session_state[ed_key]
    filled, report = apply_r_to_plane_df(base, lib_id)
    st.session_state[phase_key] = (
        filled[PLANE_COLS] if all(c in filled.columns for c in PLANE_COLS) else filled
    )
    if ed_key in st.session_state:
        del st.session_state[ed_key]
    st.session_state[f"r_fill_report_{phase_key}"] = report


def _show_r_fill_report(rep: dict | None) -> None:
    if not rep:
        return
    matched = rep.get("matched", 0)
    total = rep.get("total", 0)
    lib = rep.get("lib_id", "?")
    if rep.get("all_matched") or (
        matched == total and (total or 0) > 0 and not rep.get("unmatched")
    ):
        ui_style.chips(
            [
                (f"R 全匹配 {matched}/{total}", "cte-chip-ok"),
                (f"库 {lib}", "cte-chip-info"),
            ]
        )
        st.success(f"已匹配全部晶面 → `{lib}`。可继续计算。")
    else:
        un = ", ".join((rep.get("unmatched") or [])[:8]) or "—"
        ui_style.chips(
            [
                (f"匹配 {matched}/{total}", "cte-chip-warn"),
                ("未匹配行 R 常为 1.0", "cte-chip-err"),
            ]
        )
        st.warning(
            f"未匹配：{un}。未匹配行保留原 R（常 1.0），会扭曲 I=Area/R 权重。"
            " 默认策略下将阻止计算（见侧栏）。"
        )


def render_inputs(alpha_unit: str, sig_figs: int) -> None:
    ui_style.section_open("① 两相基本信息", "组成", "cte-badge-in")
    ui_style.hint(
        "体积分数 <strong>f</strong> 必须是 <strong>体积分数</strong>，不是质量分数 wt%。"
        " 相2 的 f₂ 自动 = 1−f₁。Kerner 需要明确 matrix / inclusion。"
    )
    c1, c2, c3 = st.columns([1.2, 1.2, 1.05])
    with c1:
        p1_name = st.text_input(
            "相1 名称（默认基体）",
            key="p1_name",
            help="显示用标签，如 β-Ti、Al、基体。不参与公式计算。",
        )
        f1 = st.slider(
            "相1 体积分数 f₁",
            0.0,
            1.0,
            step=0.01,
            help=(
                "体积分数 0–1。勿填质量分数。"
                "若只有 wt%，需用密度换算后再填（当前版本不做自动换算）。"
            ),
            key="f1",
        )
        f2 = 1.0 - float(f1)
        ui_style.vf_bar(float(f1), str(p1_name or "相1"), str(st.session_state.get("p2_name") or "相2"))
    with c2:
        p2_name = st.text_input(
            "相2 名称（默认增强相/夹杂）",
            key="p2_name",
            help="显示用标签，如 α″、SiC。",
        )
        micro_opts = list(MICRO_LABELS.keys())
        micro = st.selectbox(
            "微结构（影响模型推荐，不改公式本身）",
            options=micro_opts,
            format_func=lambda x: MICRO_LABELS.get(x, x),
            key="microstructure",
            help=(
                "球形颗粒 → 更倾向 Kerner；层状 → 更倾向并联；"
                "未知则多模型并列，不给唯一真值。"
            ),
        )
    with c3:
        ui_style.role_card(
            str(p1_name or "相1"),
            str(p2_name or "相2"),
            bool(st.session_state.get("swap_roles", False)),
        )
    ui_style.section_close()

    ui_style.section_open("② 各相 CTE 输入", "热膨胀", "cte-badge-in")
    ui_style.hint(
        f"输入框 CTE <strong>固定按 10⁻⁶/K</strong> 填写（例 22.5 表示 22.5×10⁻⁶/K）。"
        f" 侧栏「显示单位」当前为 <strong>{alpha_unit}</strong>，只影响结果展示。"
    )
    input_mode = st.radio(
        "输入方式",
        options=["scalar", "xrd"],
        horizontal=True,
        format_func=lambda x: (
            "⚡ 直接填单相 CTE（最快）" if x == "scalar" else "📐 晶面族 + 峰面积加权（XRD）"
        ),
        key="input_mode",
        help=(
            "标量：跳过 XRD 加权，直接用文献/测量的相表观 CTE。"
            " XRD：用峰面积与 R 因子做强度加权，得到表观相 CTE（≠ 本征宏观 CTE）。"
        ),
    )

    rdef = st.session_state.get("rdef", "theoretical_relative_intensity")
    df1 = st.session_state["planes_1"]
    df2 = st.session_state["planes_2"]
    a1_direct = float(st.session_state.get("a1_direct", 22.5))
    a2_direct = float(st.session_state.get("a2_direct", 4.5))

    if input_mode == "scalar":
        ui_style.chips(
            [
                ("路径：标量 CTE", "cte-chip-info"),
                ("跳过 XRD 加权", "cte-chip"),
            ]
        )
        sc1, sc2 = st.columns(2)
        with sc1:
            a1_direct = st.number_input(
                f"{p1_name}  CTE  (10⁻⁶/K)",
                step=0.1,
                format="%.3f",
                key="a1_direct",
                help="相1 表观/有效线性 CTE。例：铝约 23，SiC 约 4–5（数量级参考，非真值库）。",
            )
        with sc2:
            a2_direct = st.number_input(
                f"{p2_name}  CTE  (10⁻⁶/K)",
                step=0.1,
                format="%.3f",
                key="a2_direct",
                help="相2 表观/有效线性 CTE。请填你的测量或文献值，并在导出备注中可追溯。",
            )
        st.caption("此路径不做峰面积加权；适合快速筛选与文献两相估算。")
    else:
        ui_style.chips(
            [
                ("路径：XRD 加权", "cte-chip-info"),
                ("默认 I = Area / R", "cte-chip-warn"),
                ("未匹配默认阻止计算", "cte-chip-err"),
            ]
        )
        rdef = st.selectbox(
            "R 因子含义（按实验室定义选，勿混用口径）",
            options=list(RDEF_LABELS.keys()),
            format_func=lambda x: RDEF_LABELS[x],
            key="rdef",
            help=(
                "不同实验室 R 定义可能不同。"
                " 本项目内置 no_LP 库默认配合 I = 峰面积 / R。"
                " 选错定义会系统性偏置权重且可能不报错。"
            ),
        )
        st.caption(f"公式：`{R_FACTOR_FORMULAS[RFactorDefinition(rdef)]}`")

        libs = list_r_libraries()
        lib_ids = ["manual"] + [x["id"] for x in libs]
        lib_labels = {"manual": "手动输入（不自动填 R）"}
        for x in libs:
            lib_labels[x["id"]] = x["label"]

        table_h = st.slider(
            "晶面表显示高度（像素）",
            min_value=280,
            max_value=600,
            value=int(st.session_state.get("plane_table_height", 400)),
            step=20,
            help="调大可一次看到更多晶面，类似加高 Excel 窗口。",
            key="plane_table_height",
        )

        ui_style.hint(
            "内置库：β-Ti no_LP · α″ Shuffle-58/73。"
            " 晶面可写 <code>(1 1 0)</code>、<code>(110)β</code>、<code>(0 2 0)α\"</code>。"
            " 先填 α 与峰面积，再点 <strong>填充 R</strong>；未匹配默认阻止计算。"
        )

        st.markdown(f"##### 相1 · {p1_name} 晶面数据")
        t1a, t1b = st.columns([3, 1])
        with t1a:
            default_p1 = suggest_library_for_phase(1)
            idx1 = lib_ids.index(default_p1) if default_p1 in lib_ids else 0
            if "rlib_p1" not in st.session_state:
                st.session_state["rlib_p1"] = lib_ids[idx1]
            lib_p1 = st.selectbox(
                "内置 R 表（相1）",
                options=lib_ids,
                format_func=lambda i: lib_labels.get(i, i),
                key="rlib_p1",
                help="选库后点右侧「填充本相 R」。选「手动」则完全手填 R 列。",
            )
        with t1b:
            st.write("")
            st.write("")
            if st.button(
                "填充本相 R",
                use_container_width=True,
                disabled=(lib_p1 == "manual"),
                key="btn_fill_p1",
                help="按晶面标签查表写入 R；未命中行保持原 R。",
            ):
                _fill_r_from_library("planes_1", lib_p1)
                st.rerun()
        _show_r_fill_report(st.session_state.get("r_fill_report_planes_1"))
        df1 = simple_plane_editor("planes_1", height=table_h, title=str(p1_name))

        st.divider()

        st.markdown(f"##### 相2 · {p2_name} 晶面数据")
        t2a, t2b, t2c = st.columns([3, 1, 1])
        with t2a:
            default_p2 = suggest_library_for_phase(2)
            if "rlib_p2" not in st.session_state:
                st.session_state["rlib_p2"] = (
                    default_p2 if default_p2 in lib_ids else "manual"
                )
            lib_p2 = st.selectbox(
                "内置 R 表（相2）",
                options=lib_ids,
                format_func=lambda i: lib_labels.get(i, i),
                key="rlib_p2",
                help="α″ 常用 Shuffle-58（Rietveld）或 Shuffle-73（CrystalShift），数值不同。",
            )
        with t2b:
            st.write("")
            st.write("")
            if st.button(
                "填充本相 R",
                use_container_width=True,
                disabled=(lib_p2 == "manual"),
                key="btn_fill_p2",
            ):
                _fill_r_from_library("planes_2", lib_p2)
                st.rerun()
        with t2c:
            st.write("")
            st.write("")
            if st.button("两相都填充", type="primary", use_container_width=True, key="btn_fill_both"):
                if lib_p1 != "manual":
                    _fill_r_from_library("planes_1", lib_p1)
                if lib_p2 != "manual":
                    _fill_r_from_library("planes_2", lib_p2)
                st.rerun()
        _show_r_fill_report(st.session_state.get("r_fill_report_planes_2"))
        df2 = simple_plane_editor("planes_2", height=table_h, title=str(p2_name))

        st.checkbox(
            "确认：存在未匹配晶面时仍用当前 R 参与加权（写入警告与导出）",
            key="accept_unmatched_r",
            help="仅当侧栏策略为「阻止计算」时用于强制放行。发表级结果请优先修正 hkl 标签。",
        )

    ui_style.section_close()

    ui_style.section_open("③ 弹性模量 E、ν", "力学", "cte-badge-in")
    ui_style.hint(
        "默认同时算 <strong>串联 (ROM)</strong> 与 <strong>并联 (等应变)</strong>。"
        " E=0 时并联 / Turner / Kerner 可能不可用。"
        " 预填值为占位，请按材料修改；不是手册真值。"
    )
    e1c, e2c = st.columns(2)
    with e1c:
        E1 = st.number_input(
            f"{p1_name}  E (GPa)",
            min_value=0.0,
            step=1.0,
            key="E1",
            help="杨氏模量，单位 GPa。内部换算为 Pa。填 0 表示缺失。",
        )
        nu1 = st.number_input(
            f"{p1_name}  ν",
            min_value=-0.99,
            max_value=0.49,
            step=0.01,
            format="%.2f",
            key="nu1",
            help="泊松比，须满足 −1 < ν < 0.5。用于由 E 换算 K、G。",
        )
    with e2c:
        E2 = st.number_input(
            f"{p2_name}  E (GPa)",
            min_value=0.0,
            step=1.0,
            key="E2",
            help="相2 杨氏模量 (GPa)。",
        )
        nu2 = st.number_input(
            f"{p2_name}  ν",
            min_value=-0.99,
            max_value=0.49,
            step=0.01,
            format="%.2f",
            key="nu2",
            help="相2 泊松比。",
        )
    # quick elastic status chips
    e_chips = []
    if float(st.session_state.get("E1") or 0) > 0 and float(st.session_state.get("E2") or 0) > 0:
        e_chips.append(("并联可用（有 E）", "cte-chip-ok"))
    else:
        e_chips.append(("并联可能不可用", "cte-chip-warn"))
    e_chips.append(("Turner/Kerner 需 E+ν", "cte-chip-info"))
    ui_style.chips(e_chips)
    ui_style.section_close()

    with st.expander("高级选项 · 方向 / 孔隙 / 晶系 / 交换角色", expanded=False):
        ui_style.hint("这些项多数只影响<strong>推荐与警告</strong>；孔隙不会被静默当成零模量第三相。")
        st.selectbox(
            "测量方向",
            options=[d.value for d in MeasurementDirection],
            key="direction",
            help="影响模型顾问推荐（如层状面内/厚度），不直接改公式数值。",
        )
        st.number_input(
            "孔隙率",
            0.0,
            0.99,
            step=0.01,
            key="porosity",
            help="0–1。>0 时显示警告；首版不把孔隙当第三相塞进全部两相公式。",
        )
        st.checkbox(
            "孔隙>0 时仅按实体相归一化体积分数（筛选）",
            key="renorm",
            help="将实体相体积分数重新归一到和为 1，仅作筛选用途。",
        )
        st.selectbox(
            "相1 晶系",
            [c.value for c in CrystalSystem],
            key="crystal1",
            help="立方系且多晶面 CTE 离散过大时会警告（可能织构/误差）。",
        )
        st.selectbox(
            "相2 晶系",
            [c.value for c in CrystalSystem],
            key="crystal2",
            help="同上。",
        )
        st.checkbox(
            "交换 matrix / inclusion（相2 为基体）",
            key="swap_roles",
            help="Kerner 对角色不对称；交换后数值可能改变。必须显式选择，不会静默猜测。",
        )

    st.markdown("")
    calc_col, tip_col = st.columns([2.2, 1])
    with calc_col:
        do_calc = st.button(
            "▶  计算 CTE",
            type="primary",
            use_container_width=True,
            help="校验输入 → XRD 加权（若启用）→ 全模型 → 推荐与警告。",
        )
    with tip_col:
        st.caption("算完后看：**模型区间 → 串并联对照 → 明细/导出**")

    if do_calc:
        if input_mode == "xrd":
            st.session_state["planes_1"] = df1
            st.session_state["planes_2"] = df2

        role1, role2 = PhaseRole.MATRIX, PhaseRole.INCLUSION
        if st.session_state.get("swap_roles"):
            role1, role2 = PhaseRole.INCLUSION, PhaseRole.MATRIX

        use_xrd = input_mode == "xrd"
        fill_reports = {}
        if use_xrd:
            r1 = st.session_state.get("r_fill_report_planes_1")
            r2 = st.session_state.get("r_fill_report_planes_2")
            if r1:
                fill_reports["phase1"] = r1
            if r2:
                fill_reports["phase2"] = r2

        policy = st.session_state.get("unmatched_r_policy", UnmatchedRPolicy.FAIL.value)
        gate = evaluate_r_gate(
            use_xrd=use_xrd,
            policy=policy,
            fill_reports=fill_reports,
            accept_unmatched=bool(st.session_state.get("accept_unmatched_r")),
        )
        if not gate["ok"]:
            st.session_state["calc_result"] = {
                "ok": False,
                "errors": gate["errors"],
                "warnings": gate["warnings"],
            }
            st.session_state["mc_result"] = None
            st.session_state["scroll_to_results"] = True
            st.rerun()

        settings = ProjectSettings(
            project_name=f"{p1_name}+{p2_name}",
            microstructure=MicrostructureType(micro),
            measurement_direction=MeasurementDirection(st.session_state["direction"]),
            porosity=float(st.session_state.get("porosity") or 0.0),
            renormalize_solid_fractions=bool(st.session_state.get("renorm")),
            alpha_display_unit=alpha_unit,
            display_sig_figs=int(sig_figs),
            language="zh",
        )
        phase1 = build_phase(
            p1_name,
            role1,
            float(f1),
            use_direct=(input_mode == "scalar"),
            direct_alpha=float(a1_direct) if input_mode == "scalar" else None,
            planes_df=df1,
            rdef=rdef if use_xrd else "theoretical_relative_intensity",
            E=float(E1),
            nu=float(nu1),
            crystal=st.session_state.get("crystal1", "cubic"),
        )
        phase2 = build_phase(
            p2_name,
            role2,
            float(f2),
            use_direct=(input_mode == "scalar"),
            direct_alpha=float(a2_direct) if input_mode == "scalar" else None,
            planes_df=df2,
            rdef=rdef if use_xrd else "theoretical_relative_intensity",
            E=float(E2),
            nu=float(nu2),
            crystal=st.session_state.get("crystal2", "cubic"),
        )
        result = run_calculation(
            phase1,
            phase2,
            settings,
            r_match_reports=gate["reports"],
            r_gate_warnings=gate["warnings"],
        )
        st.session_state["calc_result"] = result
        st.session_state["mc_result"] = None
        st.session_state["ui_alpha_unit"] = alpha_unit
        st.session_state["ui_sig_figs"] = int(sig_figs)
        st.session_state["scroll_to_results"] = True
        if result.get("ok"):
            # snapshot planes as records for restore
            def _df_recs(df: pd.DataFrame) -> list:
                if df is None or not isinstance(df, pd.DataFrame) or df.empty:
                    return []
                return df[PLANE_COLS].to_dict(orient="records")

            st.session_state["last_ok_inputs"] = snapshot_inputs_from_calc(
                phase1,
                phase2,
                settings,
                input_mode=input_mode,
                rdef=rdef if use_xrd else "theoretical_relative_intensity",
                swap_roles=bool(st.session_state.get("swap_roles")),
                planes_1_records=_df_recs(
                    df1 if use_xrd else st.session_state.get("planes_1")
                ),
                planes_2_records=_df_recs(
                    df2 if use_xrd else st.session_state.get("planes_2")
                ),
            )
        st.rerun()


def _find_model(results, name: ModelName):
    return next((r for r in results if r.model_name == name), None)


def render_results(alpha_unit: str, sig_figs: int) -> None:
    ui_style.results_anchor()
    res = st.session_state.get("calc_result")
    if res is None:
        st.markdown("---")
        ui_style.section_open("结果预览 · 计算后显示在此", "待计算", "cte-badge-muted")
        ui_style.empty_results_panel()
        with st.expander("还想再确认一遍三层 CTE？", expanded=False):
            ui_style.three_layer_concept()
        ui_style.section_close()
        ui_style.maybe_scroll_to_results()
        return

    if not res.get("ok"):
        st.markdown("---")
        ui_style.section_open("计算未通过", "检查输入", "cte-badge-err")
        ui_style.chips([("失败", "cte-chip-err"), ("请根据下列信息修正", "cte-chip-warn")])
        for e in res.get("errors", []):
            st.error(e)
        for w in res.get("warnings", [])[:8]:
            st.warning(w)
        ui_style.hint(
            "常见原因：R 库未匹配且策略为阻止 · 峰面积全 0 · f 非法 · "
            "XRD 无有效行 · 自定义权重缺列。修正后再次点 <strong>计算 CTE</strong>。"
        )
        ui_style.section_close()
        ui_style.maybe_scroll_to_results()
        return

    alpha_unit = st.session_state.get("ui_alpha_unit", alpha_unit)
    sig_figs = int(st.session_state.get("ui_sig_figs", sig_figs))

    w1, w2 = res["w1"], res["w2"]
    results = res["results"]
    recommendation = res["recommendation"]
    settings = res["settings"]
    phase1, phase2 = res["phase1"], res["phase2"]
    e1, e2 = res["e1"], res["e2"]
    f1r, f2r = res["f1"], res["f2"]
    all_warnings = res["warnings"]
    assumptions = res["assumptions"]
    r_match_reports = res.get("r_match_reports") or {}
    interval = res.get("model_interval") or model_interval_summary(
        results, unit=alpha_unit, sig=sig_figs
    )

    rom = _find_model(results, ModelName.ROM)
    par = _find_model(results, ModelName.PARALLEL)

    st.markdown("---")
    ui_style.section_open("结果 · 模型区间与对照", "输出", "cte-badge-out")
    ui_style.chips(
        [
            (f"f₁={f1r:.2f}", "cte-chip-info"),
            (f"f₂={f2r:.2f}", "cte-chip-info"),
            (f"显示单位 {alpha_unit}", "cte-chip"),
            (f"{interval.get('n_available', 0)} 个可用模型", "cte-chip-ok"),
        ]
    )
    ui_style.result_legend()

    # Model interval first (anti single-truth narrative)
    if interval.get("n_available", 0) > 0:
        ui_style.interval_banner(
            str(interval.get("alpha_min_display")),
            str(interval.get("alpha_max_display")),
            str(interval.get("unit")),
            int(interval.get("n_available") or 0),
            str(interval.get("note") or "多模型离散区间，非实验误差棒。"),
        )

    pcol1, pcol2 = st.columns(2)
    pcol1.metric(
        f"{phase1.phase_name} · 表观 CTE",
        f"{format_alpha(w1.alpha_phase_xrd_SI, alpha_unit, sig_figs)}",
        help="第 2 层：XRD 加权或直接标量得到的相表观 CTE，不等于严格本征宏观 CTE。",
    )
    pcol1.caption(
        f"单位 {alpha_unit} · **第2层·相表观**"
        + (" · 直接标量" if w1.used_direct_scalar else " · XRD 加权")
    )
    pcol2.metric(
        f"{phase2.phase_name} · 表观 CTE",
        f"{format_alpha(w2.alpha_phase_xrd_SI, alpha_unit, sig_figs)}",
        help="第 2 层：相表观 CTE。下方串并联/模型表属于第 3 层（复合有效 CTE）。",
    )
    pcol2.caption(
        f"单位 {alpha_unit} · **第2层·相表观**"
        + (" · 直接标量" if w2.used_direct_scalar else " · XRD 加权")
    )

    st.markdown("##### 串联 vs 并联 · **第3层·复合有效 CTE**")
    c_s, c_p, c_d = st.columns(3)

    rom_txt = "—"
    par_txt = "—"
    if rom and rom.available:
        rom_txt = f"{format_alpha(rom.alpha_SI, alpha_unit, sig_figs)}"
    if par and par.available:
        par_txt = f"{format_alpha(par.alpha_SI, alpha_unit, sig_figs)}"

    c_s.metric(
        "串联 · ROM",
        rom_txt,
        help="α = f₁α₁ + f₂α₂。无弹性约束的体积分数混合，常作筛选上界/参考。",
    )
    c_s.caption(alpha_unit)
    c_p.metric(
        "并联 · 等应变",
        par_txt,
        help="E 加权：α = (f₁E₁α₁+f₂E₂α₂)/(f₁E₁+f₂E₂)。需要两相 E>0。",
    )
    c_p.caption(alpha_unit)

    if rom and rom.available and par and par.available:
        from cte_app.units import alpha_from_si

        d_si = par.alpha_SI - rom.alpha_SI
        d_disp = alpha_from_si(d_si, alpha_unit)
        rel = abs(d_si) / max(abs(rom.alpha_SI), 1e-30) * 100
        c_d.metric(
            "并联 − 串联",
            f"{d_disp:+.{sig_figs}g}",
            delta=f"相对差 {rel:.{max(sig_figs - 1, 1)}g}%",
            delta_color="off",
            help="两模型差。真实复合 CTE 还依赖微结构，未必夹在两者之间。",
        )
        c_d.caption(alpha_unit)

        g1, g2 = st.columns([1.15, 1])
        with g1:
            st.plotly_chart(
                model_comparison_bar([rom, par], alpha_unit, sig_figs),
                use_container_width=True,
                config={"displayModeBar": False},
            )
        with g2:
            st.plotly_chart(
                series_parallel_delta_gauge(rom.alpha_SI, par.alpha_SI, alpha_unit, sig_figs),
                use_container_width=True,
                config={"displayModeBar": False},
            )
            compare_df = pd.DataFrame(
                [
                    {
                        "模型": "串联 (ROM)",
                        "物理图像": "自由伸长 / 体积分数混合",
                        f"CTE ({alpha_unit})": format_alpha(rom.alpha_SI, alpha_unit, sig_figs),
                        "需要": "f、α",
                    },
                    {
                        "模型": "并联 (等应变)",
                        "物理图像": "总应变相同，E 加权",
                        f"CTE ({alpha_unit})": format_alpha(par.alpha_SI, alpha_unit, sig_figs),
                        "需要": "f、α、E",
                    },
                ]
            )
            st.dataframe(compare_df, use_container_width=True, hide_index=True)
            st.caption(f"f₁={f1r:.3f}, f₂={f2r:.3f} · 图表悬停可看数值细节")
    elif rom and rom.available and (not par or not par.available):
        st.warning(
            "串联已算出；并联不可用（需要两相 E>0）。"
            + (f" 原因：{par.unavailable_reason}" if par and par.unavailable_reason else "")
        )
    else:
        st.error("串联模型未能计算，请检查体积分数与 CTE 输入。")

    rec_r = None
    if recommendation.recommended_model:
        rec_r = next(
            (x for x in results if x.model_name == recommendation.recommended_model and x.available),
            None,
        )
    if rec_r:
        st.info(
            f"**规则推荐（非唯一真值）：** {rec_r.display_name} → "
            f"**{format_alpha(rec_r.alpha_SI, alpha_unit, sig_figs)} {alpha_unit}**　"
            f"（{recommendation.confidence.value}）  \n{recommendation.reason}"
        )
    else:
        st.info(f"{recommendation.reason} ｜ f₁={f1r:.3f}, f₂={f2r:.3f}")

    st.markdown("##### 全部模型一览")
    rows = [
        {
            "模型": r.display_name,
            "类别": {
                ModelName.ROM: "串联/混合",
                ModelName.PARALLEL: "并联",
                ModelName.TURNER: "体积约束",
                ModelName.KERNER: "颗粒-基体",
            }.get(r.model_name, ""),
            "可用": "✓" if r.available else "—",
            f"CTE ({alpha_unit})": (
                format_alpha(r.alpha_SI, alpha_unit, sig_figs) if r.available else "—"
            ),
            "推荐": "★" if r.recommended else "",
            "说明": r.unavailable_reason or r.confidence.value,
        }
        for r in results
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    show_all_chart = st.checkbox(
        "显示全部可用模型对比图",
        value=False,
        help="含 Turner / Kerner（若可用）。红色柱为规则推荐项。",
    )
    if show_all_chart and any(r.available for r in results):
        st.plotly_chart(
            model_comparison_bar(results, alpha_unit, sig_figs),
            use_container_width=True,
            config={"displayModeBar": False},
        )

    # XRD weight visualization
    if (not w1.used_direct_scalar) or (not w2.used_direct_scalar):
        with st.expander("XRD 晶面权重图（悬停看贡献）", expanded=not (w1.used_direct_scalar and w2.used_direct_scalar)):
            ui_style.hint(
                "权重来自校正强度归一；柱越长表示该晶面对相表观 CTE 影响越大。"
                " 这是<strong>表观</strong>分解，不是本征 CTE 的严格分解。"
            )
            wc1, wc2 = st.columns(2)
            with wc1:
                if not w1.used_direct_scalar and w1.labels:
                    st.plotly_chart(
                        phase_weight_bars(
                            w1.labels,
                            w1.weights,
                            w1.contributions,
                            unit=alpha_unit,
                            phase_name=phase1.phase_name,
                            sig_figs=sig_figs,
                        ),
                        use_container_width=True,
                        config={"displayModeBar": False},
                    )
                else:
                    st.caption(f"{phase1.phase_name}：直接标量，无晶面权重")
            with wc2:
                if not w2.used_direct_scalar and w2.labels:
                    st.plotly_chart(
                        phase_weight_bars(
                            w2.labels,
                            w2.weights,
                            w2.contributions,
                            unit=alpha_unit,
                            phase_name=phase2.phase_name,
                            sig_figs=sig_figs,
                        ),
                        use_container_width=True,
                        config={"displayModeBar": False},
                    )
                else:
                    st.caption(f"{phase2.phase_name}：直接标量，无晶面权重")

    with st.expander("明细 · 公式 · 弹性常数", expanded=False):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**{phase1.phase_name}**")
            if not w1.used_direct_scalar:
                st.dataframe(
                    phase_weights_df(w1, alpha_unit),
                    use_container_width=True,
                    hide_index=True,
                )
            st.caption(
                f"E={modulus_from_si(e1.E, 'GPa') if e1.E else '—'} GPa, "
                f"ν={e1.nu if e1.nu is not None else '—'}, "
                f"K={modulus_from_si(e1.K, 'GPa') if e1.K else '—'} GPa"
            )
        with c2:
            st.markdown(f"**{phase2.phase_name}**")
            if not w2.used_direct_scalar:
                st.dataframe(
                    phase_weights_df(w2, alpha_unit),
                    use_container_width=True,
                    hide_index=True,
                )
            st.caption(
                f"E={modulus_from_si(e2.E, 'GPa') if e2.E else '—'} GPa, "
                f"ν={e2.nu if e2.nu is not None else '—'}, "
                f"K={modulus_from_si(e2.K, 'GPa') if e2.K else '—'} GPa"
            )
        for r in results:
            if r.available:
                st.markdown(f"**{r.display_name}** `{r.formula}`")
                st.caption(r.substituted)

    with st.expander("R 匹配报告", expanded=bool(r_match_reports)):
        if not r_match_reports:
            st.caption("本次未使用内置 R 库填充（标量路径或手动 R）。")
        else:
            for key, rep in r_match_reports.items():
                ok = not rep.get("has_unmatched") and (rep.get("matched") == rep.get("total"))
                ui_style.chips(
                    [
                        (key, "cte-chip-info"),
                        (f"库 {rep.get('lib_id')}", "cte-chip"),
                        (
                            f"{rep.get('matched')}/{rep.get('total')}",
                            "cte-chip-ok" if ok else "cte-chip-warn",
                        ),
                    ]
                )
                if rep.get("row_status"):
                    st.dataframe(
                        pd.DataFrame(rep["row_status"]),
                        use_container_width=True,
                        hide_index=True,
                    )
                elif rep.get("unmatched"):
                    st.warning("未匹配: " + ", ".join(rep["unmatched"]))

    n_warn = len(list(dict.fromkeys(all_warnings)))
    with st.expander(f"警告（{n_warn}）", expanded=n_warn > 0 and n_warn <= 4):
        if not all_warnings:
            st.caption("无警告。")
        for w in list(dict.fromkeys(all_warnings))[:16]:
            st.warning(w)

    ui_style.section_close()

    with st.expander("Monte Carlo（可选）", expanded=False):
        n_mc = st.number_input("抽样次数", 100, 20000, 2000, 100)
        model_choice = st.selectbox("目标模型", [m.value for m in ModelName])
        st.caption("未设置输入标准差时，MC 几乎不展开；结果勿当实验误差棒。")
        if st.button("运行 MC"):
            settings_mc = settings.model_copy(
                update={"mc_n_samples": int(n_mc), "mc_seed": 42, "uncertainty_enabled": True}
            )
            st.session_state["mc_result"] = run_monte_carlo(
                phase1, phase2, settings_mc, model=ModelName(model_choice), n_samples=int(n_mc)
            )
        mc = st.session_state.get("mc_result")
        if mc is not None and mc.n_accepted > 0:
            c1, c2, c3 = st.columns(3)
            c1.metric("均值", format_alpha(mc.mean, alpha_unit, sig_figs))
            c2.metric("Std", format_alpha(mc.std, alpha_unit, sig_figs))
            c3.metric(
                "95%",
                f"[{format_alpha(mc.p2_5, alpha_unit, sig_figs)}, "
                f"{format_alpha(mc.p97_5, alpha_unit, sig_figs)}]",
            )
            st.plotly_chart(
                mc_histogram(mc, alpha_unit),
                use_container_width=True,
                config={"displayModeBar": False},
            )
            st.plotly_chart(
                sensitivity_bar(mc),
                use_container_width=True,
                config={"displayModeBar": False},
            )

    with st.expander("导出（可审计包 / 可再导入输入）", expanded=False):
        data = project_to_dict(
            settings,
            phase1,
            phase2,
            w1,
            w2,
            results,
            recommendation,
            all_warnings,
            assumptions,
            r_match_reports=r_match_reports,
            model_interval=interval,
            schema_version=PROJECT_SCHEMA_VERSION,
        )
        input_only = dump_project_input(
            settings,
            phase1,
            phase2,
            extra={"schema_version": PROJECT_SCHEMA_VERSION},
        )
        mc = st.session_state.get("mc_result")
        d1, d2, d3, d4 = st.columns(4)
        with d1:
            st.download_button(
                "完整 JSON（含结果）",
                export_json_bytes(data),
                "cte_result.json",
                "application/json",
            )
        with d2:
            st.download_button(
                "仅输入 JSON（可再导入）",
                export_json_bytes(input_only),
                "cte_project_input.json",
                "application/json",
                help="settings+phase1+phase2，侧栏可回载",
            )
        with d3:
            st.download_button(
                "CSV 模型摘要",
                export_summary_csv(results, alpha_unit, sig_figs),
                "cte_results.csv",
                "text/csv",
            )
        with d4:
            st.download_button(
                "Excel 报告",
                export_excel_bytes(
                    settings,
                    phase1,
                    phase2,
                    w1,
                    w2,
                    results,
                    recommendation,
                    all_warnings,
                    assumptions,
                    mc=mc,
                    r_match_reports=r_match_reports,
                    model_interval=interval,
                ),
                "cte_report.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        st.caption(
            f"schema_version={PROJECT_SCHEMA_VERSION} · "
            "完整 JSON 含 model_interval / r_match_reports / audit_notes。"
        )

    ui_style.section_close()
    ui_style.maybe_scroll_to_results()


def render_sidebar() -> tuple[str, int]:
    st.markdown('<div class="cte-side-title">📁 工程与模板</div>', unsafe_allow_html=True)
    st.caption("加载结构骨架或回载上次工程，避免重复填表。")

    templates = list_templates()
    if templates:
        labels = {fn: lab for fn, lab in templates}
        choice = st.selectbox(
            "结构模板",
            options=[fn for fn, _ in templates],
            format_func=lambda fn: labels.get(fn, fn),
            key="template_choice",
            help="模板只提供结构/教学起点，不是材料手册 CTE 真值。",
        )
        note = TEMPLATE_META.get(choice, {}).get("note", "结构模板，非测量真值。")
        st.caption(f"💡 {note}")
        if st.button("加载模板", use_container_width=True, key="btn_load_template"):
            try:
                data = load_json_path(str(TEMPLATE_DIR / choice))
                if not data:
                    st.error("模板文件不存在或为空")
                else:
                    load_project_dict(data)
                    st.success(f"已加载：{labels.get(choice, choice)}")
                    st.rerun()
            except ProjectIOError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"加载失败: {e}")

    st.markdown('<div class="cte-side-title">📥 导入 / 恢复</div>', unsafe_allow_html=True)
    up = st.file_uploader(
        "工程 JSON",
        type=["json"],
        help=(
            "支持 example_project 形状，或完整导出 JSON。"
            " 只读取 settings + phase1 + phase2；结果字段自动忽略。"
        ),
        key="project_uploader",
    )
    if st.button("加载上传的 JSON", use_container_width=True, key="btn_load_upload"):
        if up is None:
            st.warning("请先选择 JSON 文件")
        else:
            try:
                data = json.loads(up.getvalue().decode("utf-8"))
                load_project_dict(data)
                st.success("项目已导入")
                st.rerun()
            except ProjectIOError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"JSON 解析/校验失败: {e}")

    has_last = st.session_state.get("last_ok_inputs") is not None
    if st.button(
        "↩ 恢复上次成功输入",
        use_container_width=True,
        disabled=not has_last,
        key="btn_restore_last",
        help="恢复本会话中上一次计算成功时的全部输入（非磁盘文件）。",
    ):
        snap = st.session_state.get("last_ok_inputs")
        if snap:
            apply_ui_state(snap, clear_results=True)
            st.success("已恢复上次成功输入")
            st.rerun()
    if not has_last:
        st.caption("尚无成功计算快照。")

    st.divider()
    st.markdown('<div class="cte-side-title">👁 显示</div>', unsafe_allow_html=True)
    alpha_unit = st.selectbox(
        "CTE 显示单位",
        ["1e-6/K", "1/K", "ppm/K"],
        key="sidebar_alpha_unit",
        help="只改结果展示与图表纵轴；输入表/标量框始终按 10⁻⁶/K 语义填写。",
    )
    sig_figs = st.select_slider(
        "有效数字",
        options=[2, 3, 4, 5, 6],
        key="sidebar_sig_figs",
        help="结果数字的有效位数。不提高输入数据的真实精度。",
    )

    st.markdown('<div class="cte-side-title">🛡 R 匹配策略（XRD）</div>', unsafe_allow_html=True)
    st.selectbox(
        "未匹配晶面时",
        options=[UnmatchedRPolicy.FAIL.value, UnmatchedRPolicy.WARN.value],
        format_func=lambda x: (
            "阻止计算（推荐 / 发表级）"
            if x == UnmatchedRPolicy.FAIL.value
            else "警告后仍计算（筛选）"
        ),
        key="unmatched_r_policy",
        help=(
            "仅当本会话点过「填充 R」且存在未匹配时生效。"
            " 手动填 R、未点填充 → 不受此门闩限制。"
        ),
    )

    with st.expander("三层 CTE 速查", expanded=False):
        st.markdown(
            """
1. **α_hkl** — 晶面输入  
2. **相表观 α** — XRD 加权或标量  
3. **复合有效 α** — 多模型区间  

区间 ≠ 误差棒 · f = 体积分数  
            """
        )
        ui_style.chips(
            [
                ("α_hkl", "cte-chip-info"),
                ("表观相", "cte-chip-ok"),
                ("复合模型", "cte-chip-warn"),
            ]
        )

    with st.expander("术语速查", expanded=False):
        st.caption("悬停主区芯片，或展开顶部「术语词典」看完整中英表。")
        from cte_app.glossary import GLOSSARY

        for t in GLOSSARY[:8]:
            st.markdown(f"**{t['zh']}** (`{t['abbr']}`) — {t['def_zh']}")

    st.caption(
        "模板 ≠ 材料手册。f 必须是体积分数。"
        f" · schema {PROJECT_SCHEMA_VERSION}"
    )
    return str(alpha_unit), int(sig_figs)


def render_modeling_workbench() -> None:
    """Multiphase UI; computation and interchange live in the core package."""
    from cte_app.composite_project import (
        analysis_settings, apply_table_edits, demo_project, display_rows, display_sweep, editor_rows, effective_phase,
        from_editor, json_bytes, load_project, project_dict, report_dict, sweep,
    )
    from cte_app.homogenization import Composite, Constituent, FAMILIES, PROPERTIES, HomogenizationError

    st.title("CompModel · 复合材料有效性能建模")
    st.caption("多相组成 → 选择物理量 → 比较模型与边界 → 扫描配比 / 分级均匀化")
    st.session_state.setdefault("hm_base", demo_project())
    st.session_state.setdefault("hm_revision", 0)
    st.session_state.setdefault("hm_library", [])
    st.session_state.setdefault("hm_rows", editor_rows(st.session_state.hm_base))
    st.session_state.setdefault("hm_table_revision", 0)
    st.session_state.setdefault("hm_custom_name_value", st.session_state.hm_base.custom_name)
    st.session_state.setdefault("hm_custom_unit_value", st.session_state.hm_base.custom_unit)
    st.session_state.setdefault("hm_xi_value", 2.0)

    def install(project):
        st.session_state.hm_base = project
        st.session_state.hm_rows = editor_rows(project)
        st.session_state.hm_revision += 1
        st.session_state.hm_table_revision += 1
        st.session_state.hm_custom_name_value = project.custom_name
        st.session_state.hm_custom_unit_value = project.custom_unit
        st.session_state.pop("hm_report", None)
        st.session_state.pop("hm_sweep", None)
        st.rerun()

    with st.sidebar:
        st.subheader("多相工程")
        upload = st.file_uploader("导入 CompModel JSON", type=["json"], key="hm_upload")
        if st.button("载入工程", disabled=upload is None):
            try:
                data = json.loads(upload.getvalue())
                project = load_project(data)
                settings = analysis_settings(data)
                if settings:
                    st.session_state.hm_family = settings["family"]
                    st.session_state.hm_xi = settings["xi"]
                    st.session_state.hm_xi_value = settings["xi"]
                install(project)
            except (ValueError, UnicodeError) as exc:
                st.error(str(exc))
        if st.button("载入教学示例"):
            install(demo_project())
        st.caption("示例数值仅用于演示，不是经验证的材料数据库。旧工程使用上方 CTE / XRD 页面。")
        with st.expander("已保存的有效相", expanded=True):
            library = st.session_state.hm_library
            if library:
                selected = st.selectbox("选择有效相", range(len(library)), format_func=lambda i: library[i].name)
                st.json(library[selected].properties)
                st.caption("仅保存所选模型输出的属性；下一层需要的其他属性须另行填写。")
                if st.button("以此相建立下一层"):
                    from copy import deepcopy
                    phase = deepcopy(library[selected])
                    phase.fraction = 0.5
                    phase.role = "unspecified"
                    other_name = "新组成相" if phase.name != "新组成相" else "新组成相 2"
                    install(Composite([phase, Constituent(other_name, 0.5)], title=f"{phase.name} 的下一层复合材料",
                                      custom_name=phase.provenance["project"]["custom_name"],
                                      custom_unit=phase.provenance["project"]["custom_unit"]))
            else:
                st.caption("计算后显式选择一个模型，保存其结果供下一层使用。")
        with st.expander("模型说明与参考依据"):
            doc = Path(__file__).resolve().parent / "docs" / "effective_properties.md"
            if doc.exists():
                st.markdown(doc.read_text(encoding="utf-8"))

    base = st.session_state.hm_base
    rev = st.session_state.hm_revision
    title = st.text_input("工程名称", base.title, key=f"hm_title_{rev}")
    c1, c2 = st.columns(2)
    with c1:
        family = st.selectbox("建模物理量", list(FAMILIES), format_func=FAMILIES.get, key="hm_family")
    with c2:
        basis = st.selectbox("输入分数类型", ["volume", "mass"], index=0 if base.basis == "volume" else 1,
                             format_func=lambda x: "体积分数" if x == "volume" else "质量分数（需要各相密度）", key=f"hm_basis_{rev}")
    custom_name = st.session_state.hm_custom_name_value
    custom_unit = st.session_state.hm_custom_unit_value
    if family == "custom":
        c1, c2 = st.columns(2)
        custom_name = c1.text_input("系数名称", custom_name, key=f"hm_custom_name_{rev}")
        custom_unit = c2.text_input("系数单位（各相必须一致）", custom_unit, key=f"hm_custom_unit_{rev}")
        st.session_state.hm_custom_name_value = custom_name
        st.session_state.hm_custom_unit_value = custom_unit
        st.info("自定义系数提供算术、调和、几何混合规则。压电、热电等耦合系数不能仅凭标量平均得到完整有效响应。")
    fields = {"elastic": ["E", "nu", "K", "G"], "alpha": ["alpha", "E", "nu", "K", "G"],
              "k": ["k"], "sigma": ["sigma"], "thermal": ["rho", "cp"], "custom": ["custom"]}[family]
    if basis == "mass" and "rho" not in fields:
        fields = fields + ["rho"]
    st.subheader("组成相与属性")
    st.caption("可增删任意相。分数之和必须为 1；留空表示未知，0 表示真实零值。弹性输入 E+ν 或 K+G。各相参数应对应同一温度和测量条件。")
    show_all = st.checkbox("显示全部物理量列", key="hm_show_all")
    configs = {
        "name": st.column_config.TextColumn("相名称", required=True),
        "fraction": st.column_config.NumberColumn("组成分数", min_value=0., max_value=1., format="%.6f", required=True),
        "role": st.column_config.SelectboxColumn("角色", options=["unspecified", "matrix", "inclusion"], default="unspecified"),
        **{key: st.column_config.NumberColumn(f"{meta.label} [{meta.unit}]", format="%.8g") for key, meta in PROPERTIES.items()},
    }
    table_key = f"hm_editor_{st.session_state.hm_table_revision}"

    def commit_table():
        st.session_state.hm_rows = apply_table_edits(st.session_state.hm_rows, st.session_state[table_key])
        st.session_state.hm_table_revision += 1

    edited = st.data_editor(pd.DataFrame(st.session_state.hm_rows), num_rows="dynamic", use_container_width=True,
                            column_config=configs, column_order=["name", "fraction", "role"] + (list(PROPERTIES) if show_all else fields),
                            key=table_key, on_change=commit_table)
    xi = st.session_state.hm_xi_value
    if family == "elastic":
        xi = st.number_input("Halpin–Tsai 几何参数 ξ（按方向、形貌或实验标定）", min_value=0.001, value=xi, key="hm_xi")
        st.session_state.hm_xi_value = xi
        st.caption("各向同性模型输出 K、G、E、ν；Halpin–Tsai 仅输出所选方向的 E。弹性零刚度孔隙尚不在本页模型范围内。")
    try:
        current = from_editor(edited.to_dict("records"), base, basis=basis, title=title,
                              custom_name=custom_name, custom_unit=custom_unit)
        signature = json_bytes({"project": project_dict(current), "family": family, "xi": xi})
    except HomogenizationError as exc:
        st.error(str(exc))
        return
    input_package = {**project_dict(current), "analysis": {"family": family, "xi": xi}}
    st.download_button("下载输入工程 JSON", json_bytes(input_package), "compmodel_project.json", "application/json")
    if st.button("计算有效性能", type="primary"):
        st.session_state.hm_report = (signature, report_dict(current, family, xi))
    saved = st.session_state.get("hm_report")
    if not saved or saved[0] != signature:
        if saved:
            st.info("输入或模型参数已改变，请重新计算；旧结果已隐藏。")
        return
    report = saved[1]
    st.subheader("模型结果")
    st.caption("上下界依赖所述物理假设；模型之间的差异不是实验误差或置信区间。泊松比由每组 K、G 换算，不代表 ν 的上下界。")
    st.write("实际体积分数", dict(zip([p.name for p in current.phases], report["volume_fractions"])))
    table = pd.DataFrame(display_rows(report["results"], current))
    st.dataframe(table, use_container_width=True, hide_index=True,
                 column_config={"结果": st.column_config.NumberColumn(format="%.6g")})
    for result in report["results"]:
        with st.expander(result["model"] + (" · 不可用" if result["reason"] else " · " + result["kind"])):
            st.code(result["formula"], language=None)
            st.write(result["assumptions"])
            if result["reason"]:
                st.warning(result["reason"])
    c1, c2 = st.columns(2)
    c1.download_button("下载完整报告 JSON", json_bytes(report), "compmodel_report.json", "application/json")
    c2.download_button("下载结果 CSV", table.to_csv(index=False).encode("utf-8-sig"), "compmodel_results.csv", "text/csv")

    with st.expander("组成扫描", expanded=False):
        target = st.selectbox("扫描相（体积分数 0 → 1）", range(len(current.phases)), format_func=lambda i: current.phases[i].name)
        st.caption("其余相保持相互体积比；扫描始终以体积分数进行，包括质量分数输入的工程。")
        points = st.slider("扫描点数", 11, 201, 51, step=10)
        sweep_signature = (signature, target, points)
        if st.button("运行组成扫描"):
            try:
                st.session_state.hm_sweep = (sweep_signature, sweep(current, family, target, points, xi))
            except HomogenizationError as exc:
                st.error(str(exc))
        scan = st.session_state.get("hm_sweep")
        if scan and scan[0] == sweep_signature:
            keys = sorted({r["property"] for r in scan[1] if not r["reason"]})
            if keys:
                key = st.selectbox("绘图物理量", keys, format_func=lambda k: PROPERTIES[k].label)
                chart = pd.DataFrame(display_sweep(scan[1], key))
                st.caption(f"纵轴单位：{current.custom_unit if key == 'custom' else PROPERTIES[key].unit}")
                st.line_chart(chart.pivot(index="体积分数", columns="模型", values="结果"))
            failed = [r for r in scan[1] if r["reason"]]
            if failed:
                st.caption("部分模型在某些组成下不可用；完整扫描 CSV 保留原因。")
            st.download_button("下载扫描 CSV（SI）", pd.DataFrame(scan[1]).to_csv(index=False).encode("utf-8-sig"), "compmodel_sweep.csv", "text/csv")

    with st.expander("分级均匀化：将结果保存为有效相", expanded=False):
        available = [r["model"] for r in report["results"] if not r["reason"]]
        if available:
            st.caption("显式选择模型后保存。来源工程、模型和参数随有效相记录；下一层假定尺度分离，不自动描述颗粒团聚形貌。")
            model = st.selectbox("用于下一层的模型", available)
            name = st.text_input("有效相名称", f"{current.title}（有效相）")
            if st.button("保存有效相"):
                if not name.strip():
                    st.error("请输入有效相名称。")
                else:
                    phase = effective_phase(current, family, model, name.strip(), xi)
                    st.session_state.hm_library.append(phase)
                    st.rerun()
            with st.expander("本层组成相的均匀化来源"):
                st.json({p.name: p.provenance for p in current.phases if p.provenance})


def main() -> None:
    st.set_page_config(
        page_title="CompModel · 复合材料有效性能建模",
        page_icon="🔬",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    page = st.sidebar.radio("工作台", ["多相有效性能", "CTE / XRD 专用"], key="workspace")
    if page == "多相有效性能":
        render_modeling_workbench()
        return
    _init_state()
    ui_style.inject_global_css()

    ui_style.hero(
        "两相复合材料 CTE 计算器",
        "可解释 · 多模型并列 · 不包装唯一真值。先看模型区间，再看串联 / 并联对照。",
        steps=["填组成与 f", "填 CTE 或 XRD", "填 E、ν", "计算 · 读区间"],
    )
    ui_style.concept_expandable()
    ui_style.glossary_quick_chips(12)
    ui_style.glossary_panel()

    has_result = st.session_state.get("calc_result") is not None
    ui_style.jump_to_results_bar(has_result=has_result)

    with st.sidebar:
        alpha_unit, sig_figs = render_sidebar()

    if hasattr(st, "fragment"):

        @st.fragment
        def _input_fragment() -> None:
            render_inputs(alpha_unit, int(sig_figs))

        _input_fragment()
    else:
        render_inputs(alpha_unit, int(sig_figs))

    render_results(alpha_unit, int(sig_figs))


if __name__ == "__main__":
    main()
