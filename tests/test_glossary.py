"""Glossary content sanity checks."""

from cte_app.glossary import GLOSSARY, LAYER_LABEL, glossary_as_rows


def test_glossary_nonempty_and_fields():
    assert len(GLOSSARY) >= 10
    for t in GLOSSARY:
        assert t["zh"] and t["en"] and t["abbr"]
        assert t["def_zh"]
        assert t["layer"] in LAYER_LABEL


def test_glossary_rows_shape():
    rows = glossary_as_rows()
    assert len(rows) == len(GLOSSARY)
    assert set(rows[0].keys()) == {"中文", "English", "符号", "类别", "定义", "注意"}
    symbols = {r["符号"] for r in rows}
    assert "ROM" in symbols
    assert any("α_hkl" in s for s in symbols)
    assert "Kerner" in symbols
