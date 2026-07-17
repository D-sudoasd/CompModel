"""Streamlit visual polish: CSS, chips, section headers (no formulas)."""

from __future__ import annotations

import streamlit as st

# Palette (materials-lab calm)
C_PRIMARY = "#1B4F72"
C_ACCENT = "#2874A6"
C_SERIES = "#1A5276"  # ROM
C_PARALLEL = "#B9770E"  # Parallel
C_OK = "#196F3D"
C_WARN = "#9A7D0A"
C_ERR = "#922B21"
C_MUTED = "#5D6D7E"
C_BG_SOFT = "#F4F7FA"
C_CARD = "#FFFFFF"
C_BORDER = "#D5DDE5"


def inject_global_css() -> None:
    """Inject once per page; safe to call every run."""
    st.markdown(
        f"""
<style>
  /* ----- base ----- */
  .block-container {{
    padding-top: 1.1rem;
    padding-bottom: 2.5rem;
    max-width: 1200px;
  }}
  h1 {{
    font-weight: 700 !important;
    letter-spacing: -0.02em;
    color: {C_PRIMARY} !important;
  }}
  /* hide default streamlit chrome noise slightly */
  #MainMenu {{ visibility: hidden; }}
  footer {{ visibility: hidden; }}

  /* ----- hero ----- */
  .cte-hero {{
    background: linear-gradient(135deg, #EBF5FB 0%, #F8F9F9 55%, #FEF9E7 100%);
    border: 1px solid {C_BORDER};
    border-radius: 14px;
    padding: 1rem 1.25rem 0.9rem 1.25rem;
    margin-bottom: 0.85rem;
  }}
  .cte-hero h1 {{
    margin: 0 0 0.25rem 0;
    font-size: 1.55rem;
  }}
  .cte-hero p {{
    margin: 0;
    color: {C_MUTED};
    font-size: 0.95rem;
    line-height: 1.45;
  }}
  .cte-steps {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    margin-top: 0.7rem;
  }}
  .cte-step {{
    background: {C_CARD};
    border: 1px solid {C_BORDER};
    border-radius: 999px;
    padding: 0.22rem 0.7rem;
    font-size: 0.8rem;
    color: {C_PRIMARY};
    font-weight: 600;
  }}
  .cte-step span {{
    color: {C_ACCENT};
    margin-right: 0.25rem;
  }}

  /* ----- section header (title only; widgets cannot nest in HTML) ----- */
  .cte-section-title {{
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin: 1rem 0 0.45rem 0;
    padding: 0.55rem 0.75rem;
    font-size: 1.05rem;
    font-weight: 700;
    color: {C_PRIMARY};
    background: {C_CARD};
    border: 1px solid {C_BORDER};
    border-left: 4px solid {C_ACCENT};
    border-radius: 10px;
    box-shadow: 0 1px 2px rgba(27, 79, 114, 0.04);
  }}
  .cte-badge {{
    display: inline-block;
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.03em;
    text-transform: uppercase;
    padding: 0.15rem 0.45rem;
    border-radius: 6px;
    vertical-align: middle;
  }}
  .cte-badge-in {{ background: #D6EAF8; color: {C_PRIMARY}; }}
  .cte-badge-out {{ background: #D5F5E3; color: {C_OK}; }}
  .cte-badge-warn {{ background: #FCF3CF; color: #7D6608; }}
  .cte-badge-err {{ background: #F5B7B1; color: {C_ERR}; }}
  .cte-badge-muted {{ background: #EBEDEF; color: {C_MUTED}; }}

  .cte-hint {{
    font-size: 0.82rem;
    color: {C_MUTED};
    line-height: 1.4;
    margin: 0 0 0.6rem 0;
    padding: 0.45rem 0.65rem;
    background: {C_BG_SOFT};
    border-left: 3px solid {C_ACCENT};
    border-radius: 0 8px 8px 0;
  }}
  .cte-hint strong {{ color: {C_PRIMARY}; }}

  /* ----- chips / roles ----- */
  .cte-role-card {{
    background: {C_BG_SOFT};
    border: 1px dashed {C_BORDER};
    border-radius: 10px;
    padding: 0.55rem 0.7rem;
    font-size: 0.85rem;
    line-height: 1.5;
  }}
  .cte-role-card b {{ color: {C_PRIMARY}; }}
  .cte-chip-row {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
    margin: 0.35rem 0 0.5rem 0;
  }}
  .cte-chip {{
    font-size: 0.75rem;
    padding: 0.18rem 0.55rem;
    border-radius: 999px;
    border: 1px solid {C_BORDER};
    background: #fff;
    color: {C_MUTED};
  }}
  .cte-chip-ok {{ border-color: #A9DFBF; background: #E8F8F5; color: {C_OK}; }}
  .cte-chip-warn {{ border-color: #F9E79F; background: #FEF9E7; color: #7D6608; }}
  .cte-chip-err {{ border-color: #F5B7B1; background: #FDEDEC; color: {C_ERR}; }}
  .cte-chip-info {{ border-color: #AED6F1; background: #EBF5FB; color: {C_ACCENT}; }}

  /* ----- result band ----- */
  .cte-interval {{
    background: linear-gradient(90deg, #E8F6F3 0%, #EBF5FB 100%);
    border: 1px solid #A3E4D7;
    border-radius: 12px;
    padding: 0.85rem 1rem;
    margin: 0.5rem 0 0.85rem 0;
  }}
  .cte-interval .label {{
    font-size: 0.78rem;
    font-weight: 700;
    color: {C_OK};
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }}
  .cte-interval .value {{
    font-size: 1.35rem;
    font-weight: 700;
    color: {C_PRIMARY};
    margin: 0.2rem 0;
    font-variant-numeric: tabular-nums;
  }}
  .cte-interval .note {{
    font-size: 0.8rem;
    color: {C_MUTED};
  }}

  .cte-empty {{
    border: 1px dashed {C_BORDER};
    border-radius: 12px;
    padding: 1.1rem 1.2rem;
    background: {C_BG_SOFT};
    color: {C_MUTED};
    line-height: 1.55;
  }}
  .cte-empty ol {{
    margin: 0.4rem 0 0 1.1rem;
    padding: 0;
  }}

  /* metric polish */
  div[data-testid="stMetric"] {{
    background: {C_BG_SOFT};
    border: 1px solid {C_BORDER};
    border-radius: 10px;
    padding: 0.55rem 0.75rem;
  }}
  div[data-testid="stMetric"] label {{
    color: {C_MUTED} !important;
  }}

  /* primary compute button emphasis */
  div.stButton > button[kind="primary"] {{
    font-weight: 700;
    border-radius: 10px;
    min-height: 2.6rem;
  }}

  /* sidebar */
  section[data-testid="stSidebar"] {{
    background: #FBFCFD;
  }}
  section[data-testid="stSidebar"] .cte-side-title {{
    font-weight: 700;
    color: {C_PRIMARY};
    font-size: 0.95rem;
    margin: 0.4rem 0 0.3rem 0;
  }}

  /* ----- concept layers (三层 CTE) ----- */
  .cte-layers {{
    display: grid;
    grid-template-columns: 1fr;
    gap: 0.55rem;
    margin: 0.35rem 0 0.6rem 0;
  }}
  @media (min-width: 720px) {{
    .cte-layers {{ grid-template-columns: 1fr 1fr 1fr; }}
  }}
  .cte-layer-card {{
    background: {C_CARD};
    border: 1px solid {C_BORDER};
    border-radius: 12px;
    padding: 0.75rem 0.85rem;
    position: relative;
    overflow: hidden;
  }}
  .cte-layer-card::before {{
    content: "";
    position: absolute;
    left: 0; top: 0; bottom: 0;
    width: 4px;
  }}
  .cte-layer-card.L1::before {{ background: #5DADE2; }}
  .cte-layer-card.L2::before {{ background: #58D68D; }}
  .cte-layer-card.L3::before {{ background: #F5B041; }}
  .cte-layer-card .tag {{
    font-size: 0.68rem;
    font-weight: 800;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: {C_MUTED};
    margin-bottom: 0.25rem;
  }}
  .cte-layer-card .title {{
    font-size: 0.95rem;
    font-weight: 700;
    color: {C_PRIMARY};
    margin-bottom: 0.3rem;
  }}
  .cte-layer-card .body {{
    font-size: 0.8rem;
    color: {C_MUTED};
    line-height: 1.45;
  }}
  .cte-layer-card .not {{
    margin-top: 0.4rem;
    font-size: 0.75rem;
    color: {C_ERR};
    font-weight: 600;
  }}
  .cte-layer-flow {{
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.35rem;
    flex-wrap: wrap;
    margin: 0.5rem 0 0.25rem 0;
    font-size: 0.78rem;
    color: {C_MUTED};
  }}
  .cte-layer-flow .node {{
    background: #fff;
    border: 1px solid {C_BORDER};
    border-radius: 8px;
    padding: 0.25rem 0.55rem;
    font-weight: 600;
    color: {C_PRIMARY};
  }}
  .cte-layer-flow .arrow {{ color: {C_ACCENT}; font-weight: 700; }}

  /* ----- pipeline schematic (empty state) ----- */
  .cte-pipeline {{
    display: flex;
    flex-wrap: wrap;
    align-items: stretch;
    gap: 0.4rem;
    margin: 0.65rem 0 0.5rem 0;
  }}
  .cte-pipe-box {{
    flex: 1 1 120px;
    min-width: 110px;
    background: #fff;
    border: 1px solid {C_BORDER};
    border-radius: 10px;
    padding: 0.55rem 0.6rem;
    text-align: center;
  }}
  .cte-pipe-box .n {{
    font-size: 0.7rem;
    font-weight: 800;
    color: {C_ACCENT};
  }}
  .cte-pipe-box .t {{
    font-size: 0.82rem;
    font-weight: 700;
    color: {C_PRIMARY};
    margin: 0.15rem 0;
  }}
  .cte-pipe-box .d {{
    font-size: 0.72rem;
    color: {C_MUTED};
    line-height: 1.35;
  }}
  .cte-pipe-arrow {{
    display: flex;
    align-items: center;
    color: {C_ACCENT};
    font-weight: 700;
    font-size: 1.1rem;
    padding: 0 0.1rem;
  }}

  /* series / parallel mini schematic */
  .cte-model-schemes {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.55rem;
    margin: 0.4rem 0 0.6rem 0;
  }}
  @media (max-width: 640px) {{
    .cte-model-schemes {{ grid-template-columns: 1fr; }}
  }}
  .cte-scheme {{
    border: 1px solid {C_BORDER};
    border-radius: 10px;
    padding: 0.55rem 0.7rem;
    background: {C_BG_SOFT};
  }}
  .cte-scheme .name {{
    font-weight: 700;
    font-size: 0.85rem;
    margin-bottom: 0.35rem;
  }}
  .cte-scheme .name.rom {{ color: {C_SERIES}; }}
  .cte-scheme .name.par {{ color: {C_PARALLEL}; }}
  .cte-scheme .svg-wrap {{
    display: flex;
    justify-content: center;
    margin: 0.25rem 0;
  }}
  .cte-scheme .cap {{
    font-size: 0.72rem;
    color: {C_MUTED};
    line-height: 1.35;
  }}

  /* legend strip after success */
  .cte-legend {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.55rem 1rem;
    font-size: 0.78rem;
    color: {C_MUTED};
    margin: 0.2rem 0 0.55rem 0;
    padding: 0.45rem 0.65rem;
    background: {C_BG_SOFT};
    border-radius: 8px;
    border: 1px solid {C_BORDER};
  }}
  .cte-legend i {{
    display: inline-block;
    width: 10px;
    height: 10px;
    border-radius: 2px;
    margin-right: 0.3rem;
    vertical-align: middle;
  }}

  /* glossary term chips (native title = hover) */
  .cte-term-row {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
    margin: 0.35rem 0 0.5rem 0;
  }}
  .cte-term {{
    display: inline-block;
    font-size: 0.75rem;
    padding: 0.2rem 0.55rem;
    border-radius: 999px;
    border: 1px solid {C_BORDER};
    background: #fff;
    color: {C_PRIMARY};
    font-weight: 600;
    cursor: help;
    line-height: 1.35;
  }}
  .cte-term:hover {{
    border-color: {C_ACCENT};
    background: #EBF5FB;
  }}
  .cte-term-en {{
    font-weight: 500;
    color: {C_MUTED};
    font-size: 0.7rem;
  }}

  /* jump / scroll helpers */
  .cte-jump-bar {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    align-items: center;
    margin: 0.35rem 0 0.6rem 0;
    padding: 0.45rem 0.7rem;
    background: #EBF5FB;
    border: 1px solid #AED6F1;
    border-radius: 10px;
    font-size: 0.85rem;
    color: {C_PRIMARY};
  }}
  .cte-jump-bar a {{
    color: {C_ACCENT};
    font-weight: 700;
    text-decoration: none;
  }}
  .cte-jump-bar a:hover {{ text-decoration: underline; }}
  #cte-results-anchor {{
    display: block;
    position: relative;
    top: -8px;
    height: 1px;
  }}
</style>
        """,
        unsafe_allow_html=True,
    )


def hero(title: str, subtitle: str, steps: list[str] | None = None) -> None:
    steps_html = ""
    if steps:
        chips = "".join(f'<div class="cte-step"><span>{i+1}</span>{s}</div>' for i, s in enumerate(steps))
        steps_html = f'<div class="cte-steps">{chips}</div>'
    st.markdown(
        f"""
<div class="cte-hero">
  <h1>{title}</h1>
  <p>{subtitle}</p>
  {steps_html}
</div>
        """,
        unsafe_allow_html=True,
    )


def section_open(title: str, badge: str = "输入", badge_class: str = "cte-badge-in") -> None:
    """Section header bar (does not wrap following widgets — Streamlit limitation)."""
    st.markdown(
        f"""
<div class="cte-section-title">
  {title}
  <span class="cte-badge {badge_class}">{badge}</span>
</div>
        """,
        unsafe_allow_html=True,
    )


def section_close() -> None:
    """No-op kept for call-site compatibility."""
    return


def hint(html: str) -> None:
    st.markdown(f'<div class="cte-hint">{html}</div>', unsafe_allow_html=True)


def chips(items: list[tuple[str, str]]) -> None:
    """items: list of (text, class) e.g. ('体积分数', 'cte-chip-info')."""
    parts = "".join(f'<span class="cte-chip {cls}">{text}</span>' for text, cls in items)
    st.markdown(f'<div class="cte-chip-row">{parts}</div>', unsafe_allow_html=True)


def role_card(phase1: str, phase2: str, swapped: bool) -> None:
    if swapped:
        lines = (
            f"<b>相1 · {phase1}</b> → inclusion（夹杂）<br/>"
            f"<b>相2 · {phase2}</b> → matrix（基体）"
        )
    else:
        lines = (
            f"<b>相1 · {phase1}</b> → matrix（基体）<br/>"
            f"<b>相2 · {phase2}</b> → inclusion（夹杂）"
        )
    st.markdown(
        f"""
<div class="cte-role-card">
  <div style="font-size:0.75rem;color:{C_MUTED};margin-bottom:0.2rem;">Kerner 角色</div>
  {lines}
  <div style="font-size:0.75rem;color:{C_MUTED};margin-top:0.35rem;">
    未指定 matrix/inclusion 时 Kerner 不会静默计算 · 可在高级选项交换
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )


def interval_banner(min_disp: str, max_disp: str, unit: str, n: int, note: str) -> None:
    st.markdown(
        f"""
<div class="cte-interval">
  <div class="label">可用模型区间 · 离散范围（非误差棒）</div>
  <div class="value">[{min_disp} … {max_disp}] <span style="font-size:0.85rem;font-weight:600;color:{C_MUTED};">{unit}</span></div>
  <div class="note">{n} 个可用模型 · {note}</div>
</div>
        """,
        unsafe_allow_html=True,
    )


def three_layer_concept() -> None:
    """Three CTE concepts — educational, anti-misread."""
    st.markdown(
        f"""
<div class="cte-layer-flow">
  <span class="node">晶面 α_hkl</span>
  <span class="arrow">→</span>
  <span class="node">相表观 α（XRD 加权）</span>
  <span class="arrow">→</span>
  <span class="node">复合有效 α（多模型）</span>
</div>
<div class="cte-layers">
  <div class="cte-layer-card L1">
    <div class="tag">第 1 层 · 输入</div>
    <div class="title">晶面族 CTE α_hkl</div>
    <div class="body">
      某晶面方向的晶格热膨胀（来自 d-spacing 随温度拟合或文献）。
      表格里每一行的 α 属于这一层。
    </div>
    <div class="not">≠ 材料“唯一 CTE”</div>
  </div>
  <div class="cte-layer-card L2">
    <div class="tag">第 2 层 · 相内加权</div>
    <div class="title">XRD 表观相 CTE</div>
    <div class="body">
      峰面积 + R 定义加权得到的<strong>表观</strong>相 CTE。
      依赖织构、峰拟合、R 口径；可与直接标量路径二选一。
    </div>
    <div class="not">≠ 严格本征宏观 CTE</div>
  </div>
  <div class="cte-layer-card L3">
    <div class="tag">第 3 层 · 复合模型</div>
    <div class="title">两相有效 CTE</div>
    <div class="body">
      ROM / 并联 / Turner / Kerner 等在微结构与力学假设下的解析估计。
      多模型并列成<strong>区间</strong>，不是单一标定真值。
    </div>
    <div class="not">≠ 实验误差棒</div>
  </div>
</div>
<p style="font-size:0.78rem;color:{C_MUTED};margin:0.15rem 0 0.4rem 0;">
  写论文 / 组会时请写清你报告的是哪一层；工具导出也区分相加权与模型结果。
</p>
        """,
        unsafe_allow_html=True,
    )


def model_schematics() -> None:
    """Mini SVG: series vs parallel intuition."""
    st.markdown(
        f"""
<div class="cte-model-schemes">
  <div class="cte-scheme">
    <div class="name rom">串联 · ROM（自由伸长混合）</div>
    <div class="svg-wrap">
      <svg width="200" height="56" viewBox="0 0 200 56" xmlns="http://www.w3.org/2000/svg" aria-label="series schematic">
        <rect x="8" y="18" width="70" height="22" rx="4" fill="#1A5276" opacity="0.9"/>
        <text x="43" y="33" text-anchor="middle" fill="white" font-size="11" font-family="Segoe UI,sans-serif">相1</text>
        <rect x="86" y="18" width="70" height="22" rx="4" fill="#B9770E" opacity="0.9"/>
        <text x="121" y="33" text-anchor="middle" fill="white" font-size="11" font-family="Segoe UI,sans-serif">相2</text>
        <path d="M4 29 H8 M156 29 H196" stroke="#85929E" stroke-width="2" marker-end="url(#a)"/>
        <defs><marker id="a" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
          <path d="M0,0 L6,3 L0,6 Z" fill="#85929E"/></marker></defs>
      </svg>
    </div>
    <div class="cap">α ≈ f₁α₁ + f₂α₂ · 无弹性约束 · 常作筛选参考</div>
  </div>
  <div class="cte-scheme">
    <div class="name par">并联 · 等应变（E 加权）</div>
    <div class="svg-wrap">
      <svg width="200" height="56" viewBox="0 0 200 56" xmlns="http://www.w3.org/2000/svg" aria-label="parallel schematic">
        <rect x="50" y="6" width="100" height="18" rx="3" fill="#1A5276" opacity="0.9"/>
        <text x="100" y="19" text-anchor="middle" fill="white" font-size="10" font-family="Segoe UI,sans-serif">相1</text>
        <rect x="50" y="32" width="100" height="18" rx="3" fill="#B9770E" opacity="0.9"/>
        <text x="100" y="45" text-anchor="middle" fill="white" font-size="10" font-family="Segoe UI,sans-serif">相2</text>
        <path d="M20 28 H50 M150 28 H180" stroke="#85929E" stroke-width="2"/>
        <path d="M20 10 V46 M180 10 V46" stroke="#85929E" stroke-width="2"/>
      </svg>
    </div>
    <div class="cap">α = Σ(f E α) / Σ(f E) · 需要两相 E&gt;0 · 界面协调假设</div>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )


def empty_results_panel() -> None:
    st.markdown(
        f"""
<div class="cte-empty">
  <b style="color:{C_PRIMARY};">尚未计算</b>
  — 按流水线填完输入，再点主按钮 <b>计算 CTE</b>。
</div>
<div class="cte-pipeline">
  <div class="cte-pipe-box">
    <div class="n">STEP 1</div>
    <div class="t">组成</div>
    <div class="d">相名 · 体积分数 f₁<br/>（勿用质量分数）</div>
  </div>
  <div class="cte-pipe-arrow">→</div>
  <div class="cte-pipe-box">
    <div class="n">STEP 2</div>
    <div class="t">CTE 输入</div>
    <div class="d">标量 α 或<br/>晶面 + 峰面积 + R</div>
  </div>
  <div class="cte-pipe-arrow">→</div>
  <div class="cte-pipe-box">
    <div class="n">STEP 3</div>
    <div class="t">弹性</div>
    <div class="d">E、ν<br/>并联 / Kerner 需要</div>
  </div>
  <div class="cte-pipe-arrow">→</div>
  <div class="cte-pipe-box">
    <div class="n">STEP 4</div>
    <div class="t">读结果</div>
    <div class="d">模型区间 → 串并联<br/>→ 明细 / 导出</div>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )
    model_schematics()
    st.caption(
        "侧栏可加载**结构模板**、导入工程 JSON、恢复上次成功输入。"
        " 计算后请先看**模型区间**（离散范围），不要只抄一个推荐数。"
    )


def result_legend() -> None:
    """Compact color legend under successful results."""
    st.markdown(
        f"""
<div class="cte-legend">
  <span><i style="background:{C_SERIES};"></i>串联 ROM</span>
  <span><i style="background:{C_PARALLEL};"></i>并联等应变</span>
  <span><i style="background:#6C3483;"></i>Turner</span>
  <span><i style="background:#117A65;"></i>Kerner</span>
  <span><i style="background:#C0392B;"></i>规则推荐（非唯一真值）</span>
  <span>绿带 = 可用模型区间（≠ 误差棒）</span>
</div>
        """,
        unsafe_allow_html=True,
    )


def concept_expandable() -> None:
    """Collapsible scientific concepts under the hero."""
    with st.expander("📘 读数必读：三层 CTE 概念 · 串并联含义 · 常见误读", expanded=False):
        st.markdown("##### 三层 CTE（请勿混为一谈）")
        three_layer_concept()
        st.markdown("##### 串联 vs 并联（默认对照）")
        model_schematics()
        st.markdown(
            f"""
| 易误读 | 正确理解 |
|--------|----------|
| 推荐模型 = 真值 | 规则建议，需结合微结构与假设 |
| 模型区间 = 实验误差 | **模型离散**，不是测量不确定度 |
| XRD 加权 α = 本征 CTE | 仅为**表观**相 CTE |
| f 可填质量分数 | 必须是**体积分数** |
| 未匹配 R=1 没关系 | 会扭曲权重；默认可阻止计算 |

详细假设见 `docs/model_assumptions.md`。
            """
        )


def glossary_quick_chips(max_terms: int = 10) -> None:
    """Hoverable term chips (native HTML title tooltips)."""
    from cte_app.glossary import GLOSSARY, term_tooltip_html

    parts = []
    for t in GLOSSARY[:max_terms]:
        tip = f"{t['def_zh']} | {t['note']}"
        parts.append(term_tooltip_html(t["abbr"], t["zh"], tip))
    st.markdown(
        f'<div class="cte-term-row">{"".join(parts)}</div>'
        f'<p style="font-size:0.72rem;color:{C_MUTED};margin:0;">'
        f"鼠标悬停词条可看定义 · 完整表见下方「术语词典」</p>",
        unsafe_allow_html=True,
    )


def glossary_panel() -> None:
    """Full bilingual glossary table."""
    import pandas as pd

    from cte_app.glossary import glossary_as_rows

    with st.expander("📖 术语词典（中英对照 · 悬停芯片见上方）", expanded=False):
        st.caption("面向组会/论文 Methods 的速查；符号与内部实现一致。")
        df = pd.DataFrame(glossary_as_rows())
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            height=min(420, 48 + 36 * len(df)),
            column_config={
                "中文": st.column_config.TextColumn("中文", width="medium"),
                "English": st.column_config.TextColumn("English", width="medium"),
                "符号": st.column_config.TextColumn("符号", width="small"),
                "类别": st.column_config.TextColumn("类别", width="small"),
                "定义": st.column_config.TextColumn("定义", width="large"),
                "注意": st.column_config.TextColumn("注意", width="large"),
            },
        )


def results_anchor() -> None:
    """Invisible scroll target above results section."""
    st.markdown('<div id="cte-results-anchor"></div>', unsafe_allow_html=True)


def jump_to_results_bar(*, has_result: bool) -> None:
    """Link bar: jump to results after compute (and always when result exists)."""
    if has_result:
        st.markdown(
            """
<div class="cte-jump-bar">
  <span>✅ 已有计算结果</span>
  <a href="#cte-results-anchor">↓ 跳到结果区</a>
  <span style="color:#5D6D7E;font-size:0.78rem;">先看模型区间，再看串并联</span>
</div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
<div class="cte-jump-bar" style="background:#F4F7FA;border-color:#D5DDE5;">
  <span>结果区在页面下方</span>
  <a href="#cte-results-anchor">↓ 预览结果占位</a>
  <span style="color:#5D6D7E;font-size:0.78rem;">计算成功后将自动滚到结果</span>
</div>
            """,
            unsafe_allow_html=True,
        )


def maybe_scroll_to_results() -> None:
    """
    After a successful (or failed) calculation rerun, smooth-scroll to results.
    Uses components.html → parent document (Streamlit main frame).
    """
    if not st.session_state.get("scroll_to_results"):
        return
    try:
        import streamlit.components.v1 as components

        components.html(
            """
            <script>
            (function () {
              const doc = window.parent.document;
              const el = doc.getElementById("cte-results-anchor");
              if (el) {
                el.scrollIntoView({ behavior: "smooth", block: "start" });
              } else {
                // fallback: scroll main app block
                const main = doc.querySelector('section.main');
                if (main) main.scrollTo({ top: main.scrollHeight * 0.35, behavior: "smooth" });
              }
            })();
            </script>
            """,
            height=0,
            width=0,
        )
    except Exception:
        pass
    st.session_state["scroll_to_results"] = False



def vf_bar(f1: float, name1: str, name2: str) -> None:
    """Simple HTML volume-fraction bar."""
    f1 = max(0.0, min(1.0, float(f1)))
    f2 = 1.0 - f1
    p1 = f1 * 100
    p2 = f2 * 100
    st.markdown(
        f"""
<div style="margin:0.25rem 0 0.55rem 0;">
  <div style="display:flex;justify-content:space-between;font-size:0.78rem;color:{C_MUTED};margin-bottom:0.2rem;">
    <span><b style="color:{C_SERIES};">{name1}</b> f₁={f1:.2f}</span>
    <span><b style="color:{C_PARALLEL};">{name2}</b> f₂={f2:.2f}</span>
  </div>
  <div style="display:flex;height:12px;border-radius:999px;overflow:hidden;border:1px solid {C_BORDER};">
    <div style="width:{p1}%;background:{C_SERIES};" title="f1={f1:.3f}"></div>
    <div style="width:{p2}%;background:{C_PARALLEL};" title="f2={f2:.3f}"></div>
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )
