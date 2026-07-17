"""R unmatched integrity gate."""

import pandas as pd
import pytest

from cte_app.r_integrity import UnmatchedRPolicy, evaluate_r_gate, model_interval_summary
from cte_app.r_library import apply_r_to_plane_df
from cte_app.schemas import ConfidenceLevel, ModelName, ModelResult


def test_apply_report_has_row_status():
    df = pd.DataFrame(
        {
            "晶面": ["(1 1 0)β", "(9 9 9)β"],
            "α (10⁻⁶/K)": [4.0, 1.0],
            "峰面积": [10.0, 1.0],
            "R因子": [1.0, 1.0],
        }
    )
    _, report = apply_r_to_plane_df(df, "beta_ti_no_lp")
    assert report["has_unmatched"] is True
    assert report["unmatched_count"] == 1
    assert report["matched"] == 1
    assert len(report["row_status"]) == 2
    assert report["row_status"][1]["R_source"] == "default_unmatched"


def test_gate_fail_blocks_without_accept():
    rep = {
        "lib_id": "beta_ti_no_lp",
        "total": 2,
        "matched": 1,
        "unmatched": ["(999)"],
        "has_unmatched": True,
        "unmatched_count": 1,
    }
    out = evaluate_r_gate(
        use_xrd=True,
        policy=UnmatchedRPolicy.FAIL,
        fill_reports={"phase1": rep},
        accept_unmatched=False,
    )
    assert out["ok"] is False
    assert out["blocked_by_unmatched"] is True
    assert out["errors"]


def test_gate_fail_allows_with_accept():
    rep = {
        "lib_id": "beta_ti_no_lp",
        "total": 2,
        "matched": 1,
        "unmatched": ["(999)"],
    }
    out = evaluate_r_gate(
        use_xrd=True,
        policy="fail",
        fill_reports={"phase1": rep},
        accept_unmatched=True,
    )
    assert out["ok"] is True
    assert any("用户已确认" in w for w in out["warnings"])


def test_gate_warn_allows():
    rep = {"lib_id": "x", "total": 1, "matched": 0, "unmatched": ["bad"]}
    out = evaluate_r_gate(
        use_xrd=True,
        policy=UnmatchedRPolicy.WARN,
        fill_reports={"phase1": rep},
    )
    assert out["ok"] is True
    assert out["warnings"]


def test_gate_scalar_skips():
    out = evaluate_r_gate(
        use_xrd=False,
        policy=UnmatchedRPolicy.FAIL,
        fill_reports={"phase1": {"unmatched": ["x"], "total": 1, "matched": 0}},
    )
    assert out["ok"] is True
    assert out["reports"] == {}


def test_model_interval():
    results = [
        ModelResult(
            model_name=ModelName.ROM,
            display_name="ROM",
            alpha_SI=10e-6,
            formula="a",
            substituted="a",
            required_inputs=[],
            assumptions=[],
            assumptions_satisfied=True,
            available=True,
            confidence=ConfidenceLevel.SCREENING,
        ),
        ModelResult(
            model_name=ModelName.PARALLEL,
            display_name="Parallel",
            alpha_SI=12e-6,
            formula="b",
            substituted="b",
            required_inputs=[],
            assumptions=[],
            assumptions_satisfied=True,
            available=True,
            confidence=ConfidenceLevel.SCREENING,
        ),
        ModelResult(
            model_name=ModelName.KERNER,
            display_name="Kerner",
            alpha_SI=0.0,
            formula="c",
            substituted="",
            required_inputs=[],
            assumptions=[],
            assumptions_satisfied=False,
            available=False,
            unavailable_reason="no roles",
            confidence=ConfidenceLevel.SCREENING,
        ),
    ]
    iv = model_interval_summary(results, unit="1e-6/K", sig=3)
    assert iv["n_available"] == 2
    assert iv["alpha_min_SI"] == pytest.approx(10e-6)
    assert iv["alpha_max_SI"] == pytest.approx(12e-6)
    assert "非实验误差棒" in iv["note"]
