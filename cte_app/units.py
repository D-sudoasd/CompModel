"""Unit conversion helpers. Internal SI: CTE in 1/K, modulus in Pa."""

from __future__ import annotations

ALPHA_TO_SI: dict[str, float] = {
    "1/K": 1.0,
    "1/C": 1.0,
    "1e-6/K": 1e-6,
    "1e-6/C": 1e-6,
    "10^-6/K": 1e-6,
    "10^-6/C": 1e-6,
    "ppm/K": 1e-6,
    "ppm/C": 1e-6,
    "1e-5/K": 1e-5,
    "1/°C": 1.0,
    "1e-6/°C": 1e-6,
}

MODULUS_TO_SI: dict[str, float] = {
    "Pa": 1.0,
    "kPa": 1e3,
    "MPa": 1e6,
    "GPa": 1e9,
}


def normalize_alpha_unit(unit: str) -> str:
    u = unit.strip().replace("μ", "u").replace("µ", "u")
    aliases = {
        "e-6/K": "1e-6/K",
        "10-6/K": "1e-6/K",
        "1/°K": "1/K",
        "K^-1": "1/K",
        "C^-1": "1/C",
    }
    return aliases.get(u, u)


def alpha_to_si(value: float, unit: str = "1e-6/K") -> float:
    key = normalize_alpha_unit(unit)
    if key not in ALPHA_TO_SI:
        raise ValueError(f"Unsupported CTE unit: {unit}")
    return float(value) * ALPHA_TO_SI[key]


def alpha_from_si(value_si: float, unit: str = "1e-6/K") -> float:
    key = normalize_alpha_unit(unit)
    if key not in ALPHA_TO_SI:
        raise ValueError(f"Unsupported CTE unit: {unit}")
    return float(value_si) / ALPHA_TO_SI[key]


def modulus_to_si(value: float, unit: str = "GPa") -> float:
    if unit not in MODULUS_TO_SI:
        raise ValueError(f"Unsupported modulus unit: {unit}")
    return float(value) * MODULUS_TO_SI[unit]


def modulus_from_si(value_si: float, unit: str = "GPa") -> float:
    if unit not in MODULUS_TO_SI:
        raise ValueError(f"Unsupported modulus unit: {unit}")
    return float(value_si) / MODULUS_TO_SI[unit]


def format_alpha(value_si: float, unit: str = "1e-6/K", sig_figs: int = 3) -> str:
    v = alpha_from_si(value_si, unit)
    return f"{v:.{sig_figs}g}"
