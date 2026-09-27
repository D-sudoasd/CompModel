"""Exercise the actual Streamlit app including legacy page and stale results."""
from pathlib import Path

from streamlit.testing.v1 import AppTest


APP = str(Path(__file__).resolve().parents[1] / "app.py")


def click(at, label):
    next(b for b in at.button if b.label == label).click().run()
    assert not at.exception


def test_workbench_families_sweep_hierarchy_and_legacy():
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    for family in ("elastic", "alpha", "k", "sigma", "thermal", "custom"):
        at.selectbox(key="hm_family").set_value(family).run()
        click(at, "计算有效性能")
        assert len(at.dataframe) >= 2
        assert any(r["values"] for r in at.session_state.hm_report[1]["results"])
    at.selectbox(key="hm_family").set_value("elastic").run()
    click(at, "计算有效性能")
    click(at, "运行组成扫描")
    assert len(at.session_state.hm_sweep[1]) > 100
    click(at, "保存有效相")
    assert len(at.session_state.hm_library) == 1
    click(at, "以此相建立下一层")
    assert at.session_state.hm_base.phases[0].provenance
    assert "hm_report" not in at.session_state
    at.radio(key="workspace").set_value("CTE / XRD 专用").run()
    assert not at.exception
    assert any("计算 CTE" in b.label for b in at.button)


def test_edited_inputs_hide_previous_results():
    at = AppTest.from_file(APP, default_timeout=30).run()
    click(at, "计算有效性能")
    at.number_input(key="hm_xi").set_value(3.).run()
    assert not at.exception
    assert any("请重新计算" in info.value for info in at.info)
    assert not any(b.label == "保存有效相" for b in at.button)


def test_analysis_choices_survive_family_switch():
    at = AppTest.from_file(APP, default_timeout=30).run()
    at.number_input(key="hm_xi").set_value(3.).run()
    at.selectbox(key="hm_family").set_value("custom").run()
    at.text_input(key="hm_custom_name_0").set_value("扩散系数").run()
    at.text_input(key="hm_custom_unit_0").set_value("m²/s").run()
    at.selectbox(key="hm_family").set_value("elastic").run()
    assert at.number_input(key="hm_xi").value == 3.
    at.selectbox(key="hm_family").set_value("custom").run()
    assert at.text_input(key="hm_custom_name_0").value == "扩散系数"
    assert at.text_input(key="hm_custom_unit_0").value == "m²/s"
    assert not at.exception
