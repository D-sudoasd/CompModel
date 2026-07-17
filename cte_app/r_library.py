"""Built-in R-factor libraries (hkl -> R_hkl_no_LP) with fuzzy plane-label matching."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent / "data" / "r_libraries"
CATALOG_PATH = DATA_DIR / "catalog.json"

# Strip phase tags and whitespace from plane labels
_PHASE_TAG_RE = re.compile(
    r"(β|β-|beta|α\"|α″|α'|α|alpha|″|\"|'|″)",
    re.IGNORECASE,
)
_NON_NUM_RE = re.compile(r"[^\d\-]")


def _catalog_raw() -> dict[str, Any]:
    if not CATALOG_PATH.exists():
        return {}
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def list_r_libraries() -> list[dict[str, str]]:
    """Return [{id, label, phase_hint, description}, ...]."""
    cat = _catalog_raw()
    out = []
    for lib_id, meta in cat.items():
        out.append(
            {
                "id": lib_id,
                "label": str(meta.get("label", lib_id)),
                "phase_hint": str(meta.get("phase_hint", "")),
                "description": str(meta.get("description", "")),
                "file": str(meta.get("file", "")),
                "r_column": str(meta.get("r_column", "R_hkl_no_LP")),
            }
        )
    return out


def suggest_library_for_phase(phase_index: int) -> str:
    """phase_index 1 -> beta default; 2 -> alpha shuffle_73."""
    if phase_index == 1:
        return "beta_ti_no_lp"
    return "alpha_shuffle_73"


@lru_cache(maxsize=16)
def load_r_table(lib_id: str) -> pd.DataFrame:
    cat = _catalog_raw()
    if lib_id not in cat:
        raise KeyError(f"Unknown R library id: {lib_id}")
    meta = cat[lib_id]
    path = DATA_DIR / meta["file"]
    if not path.exists():
        raise FileNotFoundError(path)
    df = pd.read_csv(path)
    r_col = meta.get("r_column", "R_hkl_no_LP")
    if r_col not in df.columns:
        raise KeyError(f"Column {r_col} missing in {path}")
    # ensure standard name
    if r_col != "R_hkl_no_LP":
        df = df.rename(columns={r_col: "R_hkl_no_LP"})
    return df


def normalize_hkl_label(label: str) -> str:
    """
    Normalize plane labels for matching.
    '(1 1 0)β', '(110)', '(1 1 0)α\"' -> '1 1 0' or compact digits key.
    Returns a canonical key like '1,1,0'.
    """
    if label is None or (isinstance(label, float) and pd.isna(label)):
        return ""
    s = str(label).strip()
    s = _PHASE_TAG_RE.sub("", s)
    s = s.replace("（", "(").replace("）", ")")
    # extract integers (allow negative)
    nums = re.findall(r"-?\d+", s)
    if len(nums) >= 3:
        # take first 3 as h k l (ignore hexagonal i if 4 numbers? take h,k,l last three if 4)
        if len(nums) >= 4:
            # Miller-Bravais h k i l -> use h, k, l
            h, k, _i, l = nums[0], nums[1], nums[2], nums[3]
            return f"{int(h)},{int(k)},{int(l)}"
        h, k, l = nums[0], nums[1], nums[2]
        return f"{int(h)},{int(k)},{int(l)}"
    # compact like 110 without separators
    digits = _NON_NUM_RE.sub("", s)
    if len(digits) == 3 and digits.isdigit():
        return f"{digits[0]},{digits[1]},{digits[2]}"
    return s.lower().strip()


def _build_lookup(df: pd.DataFrame) -> dict[str, float]:
    lookup: dict[str, float] = {}
    for _, row in df.iterrows():
        r = float(row["R_hkl_no_LP"])
        keys = set()
        if "hkl" in row and pd.notna(row["hkl"]):
            keys.add(normalize_hkl_label(str(row["hkl"])))
        if all(c in row.index and pd.notna(row[c]) for c in ("h", "k", "l")):
            keys.add(f"{int(row['h'])},{int(row['k'])},{int(row['l'])}")
        for k in keys:
            if k:
                lookup[k] = r
    return lookup


@lru_cache(maxsize=16)
def _lookup_map(lib_id: str) -> dict[str, float]:
    return _build_lookup(load_r_table(lib_id))


def lookup_R(lib_id: str, label: str) -> float | None:
    key = normalize_hkl_label(label)
    if not key:
        return None
    return _lookup_map(lib_id).get(key)


def apply_r_to_plane_df(
    df: pd.DataFrame,
    lib_id: str,
    label_col: str = "晶面",
    r_col: str = "R因子",
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """
    Fill R column from library. Returns (new_df, report).

    report keys:
      lib_id, total, matched, unmatched (labels),
      row_status: list[{label, key, matched, R, R_source}],
      unmatched_count, all_matched, has_unmatched
    Unmatched rows keep prior R (often 1.0) — callers should run r_integrity gate.
    """
    out = df.copy()
    if label_col not in out.columns:
        raise KeyError(f"Missing label column: {label_col}")
    if r_col not in out.columns:
        out[r_col] = 1.0

    matched = 0
    unmatched: list[str] = []
    row_status: list[dict[str, Any]] = []
    for i, rec in out.iterrows():
        lab = rec.get(label_col, "")
        lab_s = str(lab) if lab is not None else ""
        key = normalize_hkl_label(lab_s)
        val = lookup_R(lib_id, lab_s)
        if val is None:
            unmatched.append(lab_s)
            prior = rec.get(r_col, 1.0)
            try:
                prior_f = float(prior) if prior is not None and not pd.isna(prior) else 1.0
            except (TypeError, ValueError):
                prior_f = 1.0
            row_status.append(
                {
                    "label": lab_s,
                    "key": key,
                    "matched": False,
                    "R": prior_f,
                    "R_source": "default_unmatched",
                }
            )
            continue
        out.at[i, r_col] = val
        matched += 1
        row_status.append(
            {
                "label": lab_s,
                "key": key,
                "matched": True,
                "R": float(val),
                "R_source": "library",
            }
        )

    report = {
        "lib_id": lib_id,
        "total": len(out),
        "matched": matched,
        "unmatched": unmatched,
        "row_status": row_status,
        "unmatched_count": len(unmatched),
        "all_matched": len(out) > 0 and matched == len(out) and len(unmatched) == 0,
        "has_unmatched": len(unmatched) > 0,
    }
    return out, report
