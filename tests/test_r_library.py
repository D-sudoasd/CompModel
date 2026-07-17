"""Tests for built-in R-factor libraries."""

import pytest

from cte_app.r_library import (
    apply_r_to_plane_df,
    list_r_libraries,
    load_r_table,
    lookup_R,
    normalize_hkl_label,
    suggest_library_for_phase,
)
import pandas as pd


def test_list_libraries_has_three():
    libs = list_r_libraries()
    ids = {x["id"] for x in libs}
    assert "beta_ti_no_lp" in ids
    assert "alpha_shuffle_58" in ids
    assert "alpha_shuffle_73" in ids


def test_normalize_hkl_variants():
    assert normalize_hkl_label("(1 1 0)") == "1,1,0"
    assert normalize_hkl_label("(110)") == "1,1,0"
    assert normalize_hkl_label("(1 1 0)β") == "1,1,0"
    assert normalize_hkl_label('(0 2 0)α"') == "0,2,0"
    assert normalize_hkl_label("(2 1 1)β") == "2,1,1"


def test_beta_lookup():
    r = lookup_R("beta_ti_no_lp", "(1 1 0)β")
    assert r == pytest.approx(8.950358, rel=1e-5)
    r2 = lookup_R("beta_ti_no_lp", "(200)")
    assert r2 == pytest.approx(3.159041, rel=1e-5)
    r3 = lookup_R("beta_ti_no_lp", "(2 1 1)")
    assert r3 == pytest.approx(9.815147, rel=1e-5)


def test_alpha_two_libraries_differ_on_110():
    r58 = lookup_R("alpha_shuffle_58", "(1 1 0)")
    r73 = lookup_R("alpha_shuffle_73", "(1 1 0)")
    assert r58 == pytest.approx(0.217782, rel=1e-4)
    assert r73 == pytest.approx(0.341756, rel=1e-4)
    assert r58 != pytest.approx(r73, rel=1e-3)


def test_load_row_counts():
    assert len(load_r_table("beta_ti_no_lp")) == 8
    assert len(load_r_table("alpha_shuffle_58")) == 46
    assert len(load_r_table("alpha_shuffle_73")) == 46


def test_apply_to_df():
    df = pd.DataFrame(
        {
            "晶面": ["(1 1 0)β", "(2 0 0)β", "(9 9 9)β"],
            "α (10⁻⁶/K)": [4.0, 0.0, 1.0],
            "峰面积": [10.0, 5.0, 1.0],
            "R因子": [1.0, 1.0, 1.0],
        }
    )
    filled, report = apply_r_to_plane_df(df, "beta_ti_no_lp")
    assert report["matched"] == 2
    assert report["unmatched"] == ["(9 9 9)β"]
    assert filled.loc[0, "R因子"] == pytest.approx(8.950358, rel=1e-5)
    assert filled.loc[1, "R因子"] == pytest.approx(3.159041, rel=1e-5)
    assert filled.loc[2, "R因子"] == 1.0  # unchanged


def test_suggest_phase():
    assert suggest_library_for_phase(1) == "beta_ti_no_lp"
    assert suggest_library_for_phase(2) == "alpha_shuffle_73"
