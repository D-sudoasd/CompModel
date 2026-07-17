"""Data models for two-phase composite CTE calculation."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class CrystalSystem(str, Enum):
    CUBIC = "cubic"
    HEXAGONAL = "hexagonal"
    TETRAGONAL = "tetragonal"
    ORTHORHOMBIC = "orthorhombic"
    MONOCLINIC = "monoclinic"
    TRICLINIC = "triclinic"
    UNKNOWN = "unknown"


class PhaseRole(str, Enum):
    MATRIX = "matrix"
    INCLUSION = "inclusion"
    CO_CONTINUOUS = "co_continuous"
    UNSPECIFIED = "unspecified"


class RFactorDefinition(str, Enum):
    THEORETICAL_RELATIVE_INTENSITY = "theoretical_relative_intensity"
    MULTIPLICATIVE_CORRECTION = "multiplicative_correction"
    ALREADY_CORRECTED_WEIGHT = "already_corrected_weight"
    CUSTOM_WEIGHT = "custom_weight"


class MicrostructureType(str, Enum):
    LAYERED = "layered"
    ALIGNED_FIBER = "aligned_fiber"
    SPHERICAL_PARTICLES = "spherical_particles"
    ELLIPSOIDAL_PARTICLES = "ellipsoidal_particles"
    RANDOM_PARTICLES = "random_particles"
    CO_CONTINUOUS = "co_continuous"
    INTERPENETRATING = "interpenetrating"
    UNKNOWN = "unknown"


class MeasurementDirection(str, Enum):
    IN_PLANE = "in_plane"
    THROUGH_THICKNESS = "through_thickness"
    LONGITUDINAL = "longitudinal"
    TRANSVERSE = "transverse"
    ISOTROPIC_AVERAGE = "isotropic_average"
    USER_DEFINED = "user_defined"


class TemperatureMode(str, Enum):
    CONSTANT = "constant"
    TABULAR = "tabular"


class InterfaceState(str, Enum):
    PERFECT_BONDING = "perfect_bonding"
    WEAK_INTERFACE = "weak_interface"
    UNKNOWN = "unknown"


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    SCREENING = "screening"


class ModelName(str, Enum):
    ROM = "rom"
    PARALLEL = "parallel"
    TURNER = "turner"
    KERNER = "kerner"


R_FACTOR_FORMULAS: dict[RFactorDefinition, str] = {
    RFactorDefinition.THEORETICAL_RELATIVE_INTENSITY: "corrected_intensity = peak_area / R_factor",
    RFactorDefinition.MULTIPLICATIVE_CORRECTION: "corrected_intensity = peak_area * R_factor",
    RFactorDefinition.ALREADY_CORRECTED_WEIGHT: "corrected_intensity = peak_area",
    RFactorDefinition.CUSTOM_WEIGHT: "corrected_intensity = custom_weight (user-provided)",
}


class PlaneFamilyRow(BaseModel):
    """One crystallographic plane-family row for XRD weighting."""

    h: int = 0
    k: int = 0
    l: int = 0  # noqa: E741  # Miller index l
    plane_family_label: str = ""
    alpha_hkl: float
    alpha_unit: str = "1e-6/K"
    alpha_standard_deviation: Optional[float] = None
    peak_area: float = 0.0
    peak_area_standard_deviation: Optional[float] = None
    R_factor: float = 1.0
    R_factor_standard_deviation: Optional[float] = None
    custom_weight: Optional[float] = None
    enabled: bool = True
    notes: str = ""

    @field_validator("plane_family_label", mode="before")
    @classmethod
    def default_label(cls, v: Any, info: Any) -> str:
        if v:
            return str(v)
        data = info.data if hasattr(info, "data") else {}
        hh, kk, ll = data.get("h", 0), data.get("k", 0), data.get("l", 0)
        return f"({hh}{kk}{ll})"


class TemperaturePoint(BaseModel):
    temperature_C: float
    alpha: float
    alpha_unit: str = "1e-6/K"


class PhaseInput(BaseModel):
    phase_name: str
    crystal_system: CrystalSystem = CrystalSystem.UNKNOWN
    role: PhaseRole = PhaseRole.UNSPECIFIED
    volume_fraction: float = Field(ge=0.0, le=1.0)
    density: Optional[float] = None
    Young_modulus_E: Optional[float] = None
    Poisson_ratio_nu: Optional[float] = None
    bulk_modulus_K: Optional[float] = None
    shear_modulus_G: Optional[float] = None
    modulus_unit: str = "GPa"
    temperature_min: float = 20.0
    temperature_max: float = 100.0
    r_factor_definition: RFactorDefinition = RFactorDefinition.THEORETICAL_RELATIVE_INTENSITY
    plane_rows: list[PlaneFamilyRow] = Field(default_factory=list)
    use_direct_scalar_cte: bool = False
    direct_alpha: Optional[float] = None
    direct_alpha_unit: str = "1e-6/K"
    alpha_table: list[TemperaturePoint] = Field(default_factory=list)
    # Optional per-phase standard deviations for MC
    volume_fraction_sd: Optional[float] = None
    E_sd: Optional[float] = None
    nu_sd: Optional[float] = None
    K_sd: Optional[float] = None
    G_sd: Optional[float] = None


class ProjectSettings(BaseModel):
    project_name: str = "Untitled Project"
    temperature_mode: TemperatureMode = TemperatureMode.CONSTANT
    microstructure: MicrostructureType = MicrostructureType.UNKNOWN
    measurement_direction: MeasurementDirection = MeasurementDirection.ISOTROPIC_AVERAGE
    interface_state: InterfaceState = InterfaceState.PERFECT_BONDING
    porosity: float = Field(default=0.0, ge=0.0, le=1.0)
    renormalize_solid_fractions: bool = False
    alpha_display_unit: str = "1e-6/K"
    modulus_display_unit: str = "GPa"
    display_sig_figs: int = 3
    cubic_cte_tolerance_relative: float = 0.05
    elastic_consistency_tolerance_relative: float = 0.05
    volume_fraction_tolerance: float = 1e-6
    allow_temperature_extrapolation: bool = False
    uncertainty_enabled: bool = False
    mc_n_samples: int = 5000
    mc_seed: Optional[int] = 42
    mc_distribution: str = "truncated_normal"  # normal | truncated_normal
    language: str = "zh"


class ModelResult(BaseModel):
    model_name: ModelName
    display_name: str
    alpha_SI: float  # 1/K
    formula: str
    substituted: str
    required_inputs: list[str]
    assumptions: list[str]
    assumptions_satisfied: bool
    available: bool
    unavailable_reason: Optional[str] = None
    recommended: bool = False
    confidence: ConfidenceLevel = ConfidenceLevel.SCREENING
    risks: list[str] = Field(default_factory=list)


class Recommendation(BaseModel):
    recommended_model: Optional[ModelName]
    reason: str
    assumptions: list[str]
    assumptions_satisfied: bool
    confidence: ConfidenceLevel
    risks: list[str]
    show_models: list[ModelName]
    notes: list[str] = Field(default_factory=list)


class PhaseWeightingResult(BaseModel):
    phase_name: str
    alpha_phase_xrd_SI: float  # 1/K
    corrected_intensities: list[float]
    weights: list[float]
    contributions: list[float]
    labels: list[str]
    weighted_std: float
    cv: float  # coefficient of variation of alpha_hkl (unweighted among enabled)
    n_eff: float
    warnings: list[str] = Field(default_factory=list)
    used_direct_scalar: bool = False
