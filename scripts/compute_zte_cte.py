"""
Compute XRD-intensity-weighted apparent CTE for ZTE state (beta + alpha'')
using two R tables: CrystalShift vs Rietveld.

Input:
  E:\\文件备份\\飞书文件下载\\ZTE状态各晶面参数.xlsx

R definition used:
  corrected_intensity = Area / R   (theoretical_relative_intensity)

Outputs under results/analysis_ZTE/.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from cte_app.composite_models import model_parallel, model_rom
from cte_app.phase_weighting import compute_phase_xrd_cte
from cte_app.schemas import (
    PhaseInput,
    PhaseRole,
    PlaneFamilyRow,
    RFactorDefinition,
)
from cte_app.units import alpha_from_si

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "analysis_ZTE"
# Optional local data path — override with env ZTE_XLSX if needed
DEFAULT_XLSX = Path(
    __import__("os").environ.get(
        "ZTE_XLSX",
        str(ROOT / "raw_sources" / "zte" / "ZTE状态各晶面参数.xlsx"),
    )
)

R_COLS = {
    "CrystalShift": "R_no_LP_CrystalShift",
    "Rietveld": "R_no_LP_Rietveld",
}

# User-provided volume fractions & elastic moduli
F_BETA = 0.60
F_ALPHA_PP = 0.40
E_BETA_GPA = 45.0  # beta
E_ALPHA_PP_GPA = 60.0  # orthorhombic alpha''


def load_plane_table(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path)
    # normalize column names
    df.columns = [str(c).strip() for c in df.columns]
    # Texture column may be "Texture" or "Texture "
    tex_col = next(c for c in df.columns if c.lower().startswith("texture"))
    df = df.rename(columns={tex_col: "Texture"})
    df["Texture"] = df["Texture"].astype(str).str.strip()
    for col in ["Area", "CTE", "R_no_LP_CrystalShift", "R_no_LP_Rietveld"]:
        if col not in df.columns:
            raise KeyError(f"Missing column: {col}")
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["Area", "CTE", "R_no_LP_CrystalShift", "R_no_LP_Rietveld"])
    return df


def split_phase(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Split by phase tag in Texture: beta vs alpha''."""
    is_beta = df["Texture"].str.contains("β|beta", case=False, regex=True)
    is_app = df["Texture"].str.contains('α"|α″|alpha|a"', case=False, regex=True) & ~is_beta
    # also accept plain alpha double prime without greek
    if not is_app.any():
        is_app = df["Texture"].str.contains("α", regex=False) & ~is_beta
    parts = {
        "beta": df.loc[is_beta].copy(),
        "alpha_pp": df.loc[is_app].copy(),
    }
    if parts["beta"].empty or parts["alpha_pp"].empty:
        raise ValueError(
            f"Phase split failed: beta={len(parts['beta'])}, alpha_pp={len(parts['alpha_pp'])}. "
            f"Textures={df['Texture'].tolist()}"
        )
    return parts


def rows_from_df(sub: pd.DataFrame, r_col: str) -> list[PlaneFamilyRow]:
    rows: list[PlaneFamilyRow] = []
    for _, rec in sub.iterrows():
        rows.append(
            PlaneFamilyRow(
                plane_family_label=str(rec["Texture"]),
                alpha_hkl=float(rec["CTE"]),
                alpha_unit="1e-6/K",
                peak_area=float(rec["Area"]),
                R_factor=float(rec[r_col]),
                enabled=True,
            )
        )
    return rows


def make_phase(name: str, sub: pd.DataFrame, r_col: str, role: PhaseRole) -> PhaseInput:
    return PhaseInput(
        phase_name=name,
        role=role,
        volume_fraction=0.5,  # placeholder; composite uses explicit f scan
        r_factor_definition=RFactorDefinition.THEORETICAL_RELATIVE_INTENSITY,
        plane_rows=rows_from_df(sub, r_col),
    )


def detail_table(w, unit: str = "1e-6/K") -> pd.DataFrame:
    if w.used_direct_scalar:
        return pd.DataFrame([{"mode": "direct"}])
    return pd.DataFrame(
        {
            "label": w.labels,
            "I_corr = Area/R": w.corrected_intensities,
            "weight": w.weights,
            f"contrib ({unit})": [alpha_from_si(c, unit) for c in w.contributions],
            f"alpha_hkl ({unit})": [
                alpha_from_si(c, unit) / w_ if abs(w_) > 1e-30 else float("nan")
                for c, w_ in zip(w.contributions, w.weights)
            ],
        }
    )


def hand_check_beta(sub: pd.DataFrame, r_col: str) -> float:
    """Manual weighted mean in 1e-6/K for verification."""
    I = sub["Area"] / sub[r_col]
    w = I / I.sum()
    return float((w * sub["CTE"]).sum())


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    xlsx = DEFAULT_XLSX
    if not xlsx.exists():
        raise FileNotFoundError(xlsx)

    raw = load_plane_table(xlsx)
    parts = split_phase(raw)

    summary_rows = []
    detail_sheets: dict[str, pd.DataFrame] = {"raw_input": raw}
    weight_results = {}  # (phase, rset) -> PhaseWeightingResult

    for rset, r_col in R_COLS.items():
        for phase_key, phase_name, role in [
            ("beta", "β", PhaseRole.MATRIX),
            ("alpha_pp", 'α"', PhaseRole.INCLUSION),
        ]:
            sub = parts[phase_key]
            phase = make_phase(phase_name, sub, r_col, role)
            w = compute_phase_xrd_cte(phase)
            weight_results[(phase_key, rset)] = w
            alpha_e6 = alpha_from_si(w.alpha_phase_xrd_SI, "1e-6/K")
            summary_rows.append(
                {
                    "phase": phase_name,
                    "R_table": rset,
                    "R_column": r_col,
                    "n_planes": len(sub),
                    "alpha_XRD_1e-6_per_K": alpha_e6,
                    "alpha_SI_1_per_K": w.alpha_phase_xrd_SI,
                    "N_eff": w.n_eff,
                    "CV_alpha_hkl": w.cv,
                    "weighted_std_1e-6_per_K": alpha_from_si(w.weighted_std, "1e-6/K"),
                }
            )
            det = detail_table(w)
            det.insert(0, "R_table", rset)
            det.insert(0, "phase", phase_name)
            # attach Area, R, CTE from input
            det["Area"] = sub["Area"].values
            det["R"] = sub[r_col].values
            det["CTE_1e-6_per_K"] = sub["CTE"].values
            detail_sheets[f"{phase_key}_{rset}"] = det

    summary = pd.DataFrame(summary_rows)

    # beta consistency check
    beta_cs = hand_check_beta(parts["beta"], R_COLS["CrystalShift"])
    beta_rv = hand_check_beta(parts["beta"], R_COLS["Rietveld"])
    beta_script_cs = alpha_from_si(weight_results[("beta", "CrystalShift")].alpha_phase_xrd_SI, "1e-6/K")
    beta_script_rv = alpha_from_si(weight_results[("beta", "Rietveld")].alpha_phase_xrd_SI, "1e-6/K")

    # alpha'' weight comparison
    d_cs = detail_sheets["alpha_pp_CrystalShift"]
    d_rv = detail_sheets["alpha_pp_Rietveld"]
    wcmp = pd.DataFrame(
        {
            "label": d_cs["label"],
            "CTE_1e-6": d_cs["CTE_1e-6_per_K"],
            "Area": d_cs["Area"],
            "R_CrystalShift": d_cs["R"],
            "R_Rietveld": d_rv["R"],
            "w_CrystalShift": d_cs["weight"],
            "w_Rietveld": d_rv["weight"],
            "dw (RV-CS)": d_rv["weight"] - d_cs["weight"],
            "contrib_CS": d_cs["contrib (1e-6/K)"],
            "contrib_RV": d_rv["contrib (1e-6/K)"],
        }
    ).sort_values("dw (RV-CS)", key=abs, ascending=False)

    # Composite: f_beta / f_alpha'', E_beta=45, E_alpha''=60 GPa
    E_B_SI = E_BETA_GPA * 1e9
    E_A_SI = E_ALPHA_PP_GPA * 1e9
    composite_rows = []
    for rset in R_COLS:
        a_b = weight_results[("beta", rset)].alpha_phase_xrd_SI
        a_a = weight_results[("alpha_pp", rset)].alpha_phase_xrd_SI
        a_rom = model_rom(a_b, a_a, F_BETA, F_ALPHA_PP)
        a_par = model_parallel(a_b, a_a, F_BETA, F_ALPHA_PP, E_B_SI, E_A_SI)
        composite_rows.append(
            {
                "R_table": rset,
                "f_beta": F_BETA,
                "f_alpha_pp": F_ALPHA_PP,
                "E_beta_GPa": E_BETA_GPA,
                "E_alpha_pp_GPa": E_ALPHA_PP_GPA,
                "alpha_beta_1e-6": alpha_from_si(a_b, "1e-6/K"),
                "alpha_alpha_pp_1e-6": alpha_from_si(a_a, "1e-6/K"),
                "alpha_series_ROM_1e-6": alpha_from_si(a_rom, "1e-6/K"),
                "alpha_parallel_1e-6": alpha_from_si(a_par, "1e-6/K"),
                "parallel_minus_series_1e-6": alpha_from_si(a_par - a_rom, "1e-6/K"),
                "note": f"E_β={E_BETA_GPA:g}, E_α″={E_ALPHA_PP_GPA:g} GPa",
            }
        )
    composite = pd.DataFrame(composite_rows)

    # Optional ROM scan for context
    rom_rows = []
    for rset in R_COLS:
        a_b = weight_results[("beta", rset)].alpha_phase_xrd_SI
        a_a = weight_results[("alpha_pp", rset)].alpha_phase_xrd_SI
        for f_a in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
            f_b = 1.0 - f_a
            a_rom = model_rom(a_b, a_a, f_b, f_a)
            rom_rows.append(
                {
                    "R_table": rset,
                    "f_beta": f_b,
                    "f_alpha_pp": f_a,
                    "alpha_ROM_1e-6": alpha_from_si(a_rom, "1e-6/K"),
                    "is_user_f": abs(f_b - F_BETA) < 1e-9,
                }
            )
    rom_scan = pd.DataFrame(rom_rows)

    # write excel
    xlsx_out = OUT / "zte_xrd_cte_detail.xlsx"
    with pd.ExcelWriter(xlsx_out, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="Summary", index=False)
        composite.to_excel(writer, sheet_name="Composite_user_f", index=False)
        wcmp.to_excel(writer, sheet_name="AlphaPP_WeightDiff", index=False)
        rom_scan.to_excel(writer, sheet_name="ROM_f_scan", index=False)
        for name, df in detail_sheets.items():
            sheet = name[:31]
            df.to_excel(writer, sheet_name=sheet, index=False)

    # markdown report
    a_app_cs = alpha_from_si(weight_results[("alpha_pp", "CrystalShift")].alpha_phase_xrd_SI, "1e-6/K")
    a_app_rv = alpha_from_si(weight_results[("alpha_pp", "Rietveld")].alpha_phase_xrd_SI, "1e-6/K")
    a_b = alpha_from_si(weight_results[("beta", "CrystalShift")].alpha_phase_xrd_SI, "1e-6/K")
    def _comp(rset: str) -> tuple[float, float]:
        a_b_si = weight_results[("beta", rset)].alpha_phase_xrd_SI
        a_a_si = weight_results[("alpha_pp", rset)].alpha_phase_xrd_SI
        rom = model_rom(a_b_si, a_a_si, F_BETA, F_ALPHA_PP)
        par = model_parallel(a_b_si, a_a_si, F_BETA, F_ALPHA_PP, E_B_SI, E_A_SI)
        return alpha_from_si(rom, "1e-6/K"), alpha_from_si(par, "1e-6/K")

    rom_cs, par_cs = _comp("CrystalShift")
    rom_rv, par_rv = _comp("Rietveld")

    md = []
    md.append("# ZTE 状态 · 两相 XRD 加权表观 CTE 报告\n")
    md.append("## 数据与方法\n")
    md.append(f"- 输入：`{xlsx}`\n")
    md.append("- 分相：β（3 峰）、α\" 正交相（9 峰）\n")
    md.append("- R 用法：**I = Area / R**（theoretical_relative_intensity）\n")
    md.append("- 两套 R：`R_no_LP_CrystalShift` vs `R_no_LP_Rietveld`\n")
    md.append("- CTE 输入单位按 **10⁻⁶/K**\n")
    md.append(f"- **体积分数：f_β = {F_BETA:.0%}，f_α\" = {F_ALPHA_PP:.0%}**\n")
    md.append(
        f"- **弹性模量：E_β = {E_BETA_GPA:g} GPa，E_α\"(orthorhombic) = {E_ALPHA_PP_GPA:g} GPa**\n"
    )
    md.append("\n## 各相 XRD 加权表观 CTE\n\n")
    md.append("| 相 | R 表 | α_XRD (10⁻⁶/K) | N_eff | CV(α_hkl) |\n")
    md.append("|----|------|----------------|-------|----------|\n")
    for _, r in summary.iterrows():
        md.append(
            f"| {r['phase']} | {r['R_table']} | **{r['alpha_XRD_1e-6_per_K']:.4g}** | "
            f"{r['N_eff']:.2f} | {r['CV_alpha_hkl']:.3f} |\n"
        )

    md.append("\n### 要点\n\n")
    md.append(f"- **β**：两套 R 相同 → 表观 CTE **{a_b:.4g}×10⁻⁶/K**\n")
    md.append(
        f"- **α\"**：CrystalShift **{a_app_cs:.4g}** vs Rietveld **{a_app_rv:.4g}** "
        f"（差 {a_app_rv - a_app_cs:+.4g}×10⁻⁶/K）\n"
    )
    md.append(
        f"- 手算校验 β：CS {beta_cs:.6g} / 脚本 {beta_script_cs:.6g}；"
        f"RV {beta_rv:.6g} / 脚本 {beta_script_rv:.6g}\n"
    )

    md.append(
        f"\n## 复合 CTE · 串联 vs 并联"
        f"（f_β={F_BETA:.0%}，E_β={E_BETA_GPA:g} / E_α\"={E_ALPHA_PP_GPA:g} GPa）\n\n"
    )
    md.append("| R 表 | α_β | α_α\" | 串联 ROM | 并联(等应变) | 并联−串联 |\n")
    md.append("|------|-----|------|----------|--------------|----------|\n")
    md.append(
        f"| CrystalShift | {a_b:.4g} | {a_app_cs:.4g} | **{rom_cs:.4g}** | **{par_cs:.4g}** | "
        f"{par_cs - rom_cs:+.4g} |\n"
    )
    md.append(
        f"| Rietveld | {a_b:.4g} | {a_app_rv:.4g} | **{rom_rv:.4g}** | **{par_rv:.4g}** | "
        f"{par_rv - rom_rv:+.4g} |\n"
    )
    md.append(
        "\n公式：\n"
        "- 串联：α = f_β α_β + f_α\" α_α\"\n"
        "- 并联：α = (f_β E_β α_β + f_α\" E_α\" α_α\") / (f_β E_β + f_α\" E_α\")\n\n"
        f"E_α\" ({E_ALPHA_PP_GPA:g} GPa) > E_β ({E_BETA_GPA:g} GPa)，"
        "并联更偏向较硬的 α\"（负 CTE 更大），故 **并联 < 串联**。\n"
    )

    md.append("\n## α\" 权重差异最大的晶面（Rietveld − CrystalShift）\n\n")
    try:
        md.append(wcmp.head(6).to_markdown(index=False))
    except Exception:
        md.append("```\n" + wcmp.head(6).to_string(index=False) + "\n```")
    md.append("\n\n## ROM(f) 扫描（附）\n\n")
    show = rom_scan[rom_scan["f_alpha_pp"].isin([0.3, 0.4, 0.5, 0.7])]
    try:
        md.append(show.to_markdown(index=False))
    except Exception:
        md.append("```\n" + show.to_string(index=False) + "\n```")
    md.append("\n\n## 假设与局限\n\n")
    md.append("1. XRD 加权表观 CTE ≠ 严格本征宏观 CTE。\n")
    md.append("2. α\" 各晶面 CTE 离散很大（含大幅负膨胀），各向同性假设不适用。\n")
    md.append(
        f"3. E_β={E_BETA_GPA:g} GPa、E_α\"={E_ALPHA_PP_GPA:g} GPa 为用户给定（各向同性标量近似）。\n"
    )
    md.append("4. 体积分数 f_β=60% 为用户给定，未从峰面积推算。\n")
    md.append("5. Turner/Kerner 另需 K、G（或 ν）；本次未算。\n")
    md.append(f"\n详细表：`{xlsx_out}`\n")

    report_path = OUT / "zte_xrd_cte_report.md"
    report_path.write_text("".join(md), encoding="utf-8")

    print("=== Summary (10^-6/K) ===")
    print(summary.to_string(index=False))
    print("\n=== Composite @ f_beta=0.6 (series ROM) ===")
    print(composite.to_string(index=False))
    print("\n=== Alpha'' weight diff (top) ===")
    print(wcmp.head(6).to_string(index=False))
    print(f"\nWrote: {report_path}")
    print(f"Wrote: {xlsx_out}")


if __name__ == "__main__":
    main()
