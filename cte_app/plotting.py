"""Plotly figures for Streamlit UI — clearer hover, colors, annotations."""

from __future__ import annotations

from typing import Any, Optional, Sequence

import numpy as np
import plotly.graph_objects as go

from cte_app.schemas import ModelResult
from cte_app.units import alpha_from_si
from cte_app.uncertainty import MCResult

# Shared palette
COLOR_ROM = "#1A5276"
COLOR_PARALLEL = "#B9770E"
COLOR_TURNER = "#6C3483"
COLOR_KERNER = "#117A65"
COLOR_REC = "#C0392B"
COLOR_OTHER = "#5D6D7E"
COLOR_MUTED = "#85929E"

MODEL_COLORS = {
    "rom": COLOR_ROM,
    "parallel": COLOR_PARALLEL,
    "turner": COLOR_TURNER,
    "kerner": COLOR_KERNER,
}


def _short_name(r: ModelResult) -> str:
    m = r.model_name.value if hasattr(r.model_name, "value") else str(r.model_name)
    if m == "rom":
        return "串联 (ROM)"
    if m == "parallel":
        return "并联 (等应变)"
    if m == "turner":
        return "Turner"
    if m == "kerner":
        return "Kerner"
    return r.display_name


def _layout_base(fig: go.Figure, title: str, height: int = 360) -> go.Figure:
    fig.update_layout(
        title=dict(text=title, font=dict(size=15, color="#1B4F72"), x=0.0, xanchor="left"),
        template="plotly_white",
        height=height,
        margin=dict(t=48, b=56, l=56, r=24),
        font=dict(family="Segoe UI, system-ui, sans-serif", size=12, color="#2C3E50"),
        hoverlabel=dict(bgcolor="white", font_size=12, font_family="Segoe UI, system-ui, sans-serif"),
        plot_bgcolor="#FBFCFD",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(gridcolor="#E5E8E8", zeroline=True, zerolinecolor="#CCD1D1")
    return fig


def model_comparison_bar(
    results: Sequence[ModelResult],
    unit: str = "1e-6/K",
    sig_figs: int = 3,
) -> go.Figure:
    available = [r for r in results if r.available]
    if not available:
        fig = go.Figure()
        return _layout_base(fig, "无可用模型可绘制")

    names = [_short_name(r) for r in available]
    values = [alpha_from_si(r.alpha_SI, unit) for r in available]
    colors = []
    for r in available:
        m = r.model_name.value
        if r.recommended:
            colors.append(COLOR_REC)
        else:
            colors.append(MODEL_COLORS.get(m, COLOR_OTHER))

    custom = []
    for r, v in zip(available, values):
        rec = "是 ★" if r.recommended else "否"
        conf = r.confidence.value if r.available else "—"
        custom.append(
            f"模型: {_short_name(r)}<br>"
            f"CTE: {v:.{sig_figs}g} {unit}<br>"
            f"推荐: {rec}<br>"
            f"置信: {conf}<br>"
            f"<extra></extra>"
        )

    fig = go.Figure(
        data=[
            go.Bar(
                x=names,
                y=values,
                marker=dict(color=colors, line=dict(width=0)),
                text=[f"{v:.{sig_figs}g}" for v in values],
                textposition="outside",
                textfont=dict(size=11, color="#1B4F72"),
                hovertemplate="%{customdata}",
                customdata=custom,
                cliponaxis=False,
            )
        ]
    )

    if values:
        ymin = min(0.0, min(values) * 1.08) if min(values) < 0 else 0.0
        ymax = max(values) * 1.22 if max(values) >= 0 else max(values) * 0.85
        if abs(ymax - ymin) < 1e-15:
            ymax = ymin + 1.0
        # pad for outside text
        span = ymax - ymin
        fig.update_yaxes(range=[ymin, ymax + 0.08 * span])

        # band annotation for min–max if ≥2 models
        if len(values) >= 2:
            amin, amax = min(values), max(values)
            fig.add_hrect(
                y0=amin,
                y1=amax,
                fillcolor="rgba(39, 174, 96, 0.08)",
                line_width=0,
                annotation_text="模型区间",
                annotation_position="top left",
                annotation_font_size=10,
                annotation_font_color="#196F3D",
            )

    title = "串联 / 并联 CTE 对照" if len(available) == 2 else "各模型复合 CTE 比较"
    fig = _layout_base(fig, title, height=380)
    fig.update_layout(
        yaxis_title=f"CTE ({unit})",
        xaxis_title=None,
        showlegend=False,
        bargap=0.35,
    )
    fig.update_xaxes(tickangle=0)
    return fig


def phase_weight_bars(
    labels: Sequence[str],
    weights: Sequence[float],
    contributions: Optional[Sequence[float]] = None,
    *,
    unit: str = "1e-6/K",
    phase_name: str = "",
    sig_figs: int = 3,
) -> go.Figure:
    """Horizontal bars of XRD weight share (and optional contribution hover)."""
    labs = [str(x) for x in labels]
    w = [float(x) for x in weights]
    order = np.argsort(w)
    labs = [labs[i] for i in order]
    w = [w[i] for i in order]
    contrib_disp = None
    if contributions is not None and len(contributions) == len(weights):
        c = [alpha_from_si(float(contributions[i]), unit) for i in order]
        contrib_disp = c

    hover = []
    for i, lab in enumerate(labs):
        h = f"{lab}<br>权重 w = {w[i]:.3f} ({100 * w[i]:.1f}%)"
        if contrib_disp is not None:
            h += f"<br>贡献 ≈ {contrib_disp[i]:.{sig_figs}g} {unit}"
        h += "<extra></extra>"
        hover.append(h)

    fig = go.Figure(
        data=[
            go.Bar(
                x=w,
                y=labs,
                orientation="h",
                marker=dict(
                    color=w,
                    colorscale=[[0, "#D4E6F1"], [1, COLOR_ROM]],
                    line=dict(width=0),
                ),
                text=[f"{100 * x:.1f}%" for x in w],
                textposition="outside",
                hovertemplate="%{customdata}",
                customdata=hover,
                cliponaxis=False,
            )
        ]
    )
    title = f"晶面权重 · {phase_name}" if phase_name else "晶面权重"
    fig = _layout_base(fig, title, height=max(280, 40 + 28 * max(len(labs), 1)))
    fig.update_layout(
        xaxis_title="权重 w（强度归一）",
        yaxis_title=None,
        showlegend=False,
        xaxis=dict(range=[0, max(w) * 1.25 if w else 1]),
    )
    return fig


def series_parallel_delta_gauge(
    rom_si: float,
    par_si: float,
    unit: str = "1e-6/K",
    sig_figs: int = 3,
) -> go.Figure:
    """Small comparison of ROM vs Parallel as two markers on a 1D axis."""
    rom = alpha_from_si(rom_si, unit)
    par = alpha_from_si(par_si, unit)
    lo = min(rom, par)
    hi = max(rom, par)
    pad = max(abs(hi - lo) * 0.35, abs(hi) * 0.05, 0.5)

    fig = go.Figure()
    # baseline segment
    fig.add_trace(
        go.Scatter(
            x=[lo - pad, hi + pad],
            y=[0, 0],
            mode="lines",
            line=dict(color="#D5D8DC", width=6),
            hoverinfo="skip",
            showlegend=False,
        )
    )
    # interval band
    fig.add_trace(
        go.Scatter(
            x=[lo, hi, hi, lo],
            y=[-0.15, -0.15, 0.15, 0.15],
            fill="toself",
            fillcolor="rgba(39, 174, 96, 0.15)",
            line=dict(width=0),
            hoverinfo="skip",
            showlegend=False,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[rom],
            y=[0],
            mode="markers+text",
            marker=dict(size=16, color=COLOR_ROM, symbol="diamond"),
            text=["串联"],
            textposition="top center",
            name="串联 ROM",
            hovertemplate=f"串联 (ROM)<br>CTE = {rom:.{sig_figs}g} {unit}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[par],
            y=[0],
            mode="markers+text",
            marker=dict(size=16, color=COLOR_PARALLEL, symbol="circle"),
            text=["并联"],
            textposition="bottom center",
            name="并联",
            hovertemplate=f"并联 (等应变)<br>CTE = {par:.{sig_figs}g} {unit}<extra></extra>",
        )
    )
    fig = _layout_base(fig, f"串联 ↔ 并联 一维对照 ({unit})", height=200)
    fig.update_layout(
        yaxis=dict(visible=False, range=[-0.6, 0.6]),
        xaxis_title=f"CTE ({unit})",
        showlegend=False,
        margin=dict(t=40, b=40, l=40, r=24),
    )
    return fig


def mc_histogram(mc: MCResult, unit: str = "1e-6/K") -> go.Figure:
    if mc.n_accepted == 0:
        fig = go.Figure()
        return _layout_base(fig, "Monte Carlo：无接受样本")

    from cte_app.units import ALPHA_TO_SI, normalize_alpha_unit

    scale = ALPHA_TO_SI[normalize_alpha_unit(unit)]
    vals = mc.samples / scale
    mean = mc.mean / scale
    p25 = mc.p2_5 / scale
    p975 = mc.p97_5 / scale

    fig = go.Figure(
        data=[
            go.Histogram(
                x=vals,
                nbinsx=40,
                marker=dict(color="rgba(26, 82, 118, 0.75)", line=dict(width=0)),
                hovertemplate="区间内计数: %{y}<br>CTE ≈ %{x:.4g}<extra></extra>",
            )
        ]
    )
    for x, label, dash in (
        (mean, "均值", "dash"),
        (p25, "2.5%", "dot"),
        (p975, "97.5%", "dot"),
    ):
        fig.add_vline(
            x=x,
            line_dash=dash,
            line_color=COLOR_PARALLEL if "2.5" in label or "97" in label else COLOR_REC,
            annotation_text=label,
            annotation_position="top",
            annotation_font_size=10,
        )
    fig = _layout_base(fig, f"Monte Carlo 分布 · {mc.model_name.value}", height=340)
    fig.update_layout(xaxis_title=f"CTE ({unit})", yaxis_title="计数", bargap=0.05)
    return fig


def sensitivity_bar(mc: MCResult) -> go.Figure:
    if not mc.sensitivity:
        fig = go.Figure()
        return _layout_base(fig, "敏感性：无足够数据（需输入标准差）")

    names = [s[0] for s in mc.sensitivity]
    vals = [s[1] for s in mc.sensitivity]
    fig = go.Figure(
        data=[
            go.Bar(
                x=vals[::-1],
                y=names[::-1],
                orientation="h",
                marker=dict(color="#E67E22"),
                text=[f"{v:.2f}" for v in vals[::-1]],
                textposition="outside",
                hovertemplate="%{y}<br>|Spearman ρ| = %{x:.3f}<extra></extra>",
                cliponaxis=False,
            )
        ]
    )
    fig = _layout_base(fig, "Spearman |ρ| 敏感性排序", height=max(280, 36 * len(names) + 80))
    fig.update_layout(xaxis_title="|Spearman ρ|", yaxis_title=None, showlegend=False)
    return fig


def temperature_cte_curve(
    T: Sequence[float],
    alpha_eff: Sequence[float],
    unit: str = "1e-6/K",
) -> go.Figure:
    from cte_app.units import ALPHA_TO_SI, normalize_alpha_unit

    scale = ALPHA_TO_SI[normalize_alpha_unit(unit)]
    y = np.asarray(alpha_eff, dtype=float) / scale
    fig = go.Figure(
        data=[
            go.Scatter(
                x=list(T),
                y=y,
                mode="lines+markers",
                name="α_eff(T)",
                line=dict(color=COLOR_ROM, width=2.5),
                marker=dict(size=7),
                hovertemplate="T = %{x} °C<br>CTE = %{y:.4g} " + unit + "<extra></extra>",
            )
        ]
    )
    fig = _layout_base(fig, "温度相关有效 CTE")
    fig.update_layout(xaxis_title="温度 (°C)", yaxis_title=f"CTE ({unit})")
    return fig


def unavailable_models_table_rows(results: Sequence[ModelResult]) -> list[dict[str, Any]]:
    """Helper for UI: list unavailable models with reasons."""
    rows = []
    for r in results:
        if not r.available:
            rows.append(
                {
                    "模型": r.display_name,
                    "原因": r.unavailable_reason or "不可用",
                }
            )
    return rows
