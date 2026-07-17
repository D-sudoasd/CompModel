"""Monte Carlo uncertainty propagation."""

from __future__ import annotations

from dataclasses import dataclass, field
import numpy as np
from scipy import stats

from cte_app.composite_models import (
    model_kerner,
    model_parallel,
    model_rom,
    model_turner,
    resolve_elastic_properties,
)
from cte_app.phase_weighting import compute_phase_xrd_cte
from cte_app.schemas import ModelName, PhaseInput, PhaseRole, ProjectSettings


@dataclass
class MCResult:
    samples: np.ndarray
    mean: float
    median: float
    std: float
    p2_5: float
    p97_5: float
    rejected_fraction: float
    n_accepted: int
    sensitivity: list[tuple[str, float]] = field(default_factory=list)  # name, |spearman|
    model_name: ModelName = ModelName.ROM


def _sample_value(
    rng: np.random.Generator,
    mean: float,
    sd: float | None,
    dist: str,
    lower: float | None = None,
    upper: float | None = None,
) -> float:
    if sd is None or sd <= 0:
        return mean
    if dist == "normal":
        return float(rng.normal(mean, sd))
    # truncated normal
    a = -np.inf if lower is None else (lower - mean) / sd
    b = np.inf if upper is None else (upper - mean) / sd
    return float(stats.truncnorm.rvs(a, b, loc=mean, scale=sd, random_state=rng))


def run_monte_carlo(
    phase1: PhaseInput,
    phase2: PhaseInput,
    settings: ProjectSettings,
    model: ModelName = ModelName.ROM,
    n_samples: int | None = None,
    seed: int | None = None,
) -> MCResult:
    """
    Monte Carlo on inputs. Volume fractions renormalized each draw.
    Rejects negative moduli, negative peak areas, non-physical Poisson ratios.
    """
    n = n_samples if n_samples is not None else settings.mc_n_samples
    seed = settings.mc_seed if seed is None else seed
    rng = np.random.default_rng(seed)
    dist = settings.mc_distribution

    accepted: list[float] = []
    # For sensitivity: store parameter vectors vs output
    param_names = [
        "alpha1",
        "alpha2",
        "f1",
        "E1",
        "E2",
        "nu1",
        "nu2",
        "K1",
        "K2",
        "G1",
        "G2",
    ]
    param_rows: list[list[float]] = []
    rejected = 0

    for _ in range(n):
        try:
            p1 = phase1.model_copy(deep=True)
            p2 = phase2.model_copy(deep=True)

            # volume fractions
            f1 = _sample_value(
                rng,
                phase1.volume_fraction,
                phase1.volume_fraction_sd,
                dist,
                lower=0.0,
                upper=1.0,
            )
            f2 = _sample_value(
                rng,
                phase2.volume_fraction,
                phase2.volume_fraction_sd,
                dist,
                lower=0.0,
                upper=1.0,
            )
            s = f1 + f2
            if s <= 0:
                rejected += 1
                continue
            f1, f2 = f1 / s, f2 / s
            p1.volume_fraction = f1
            p2.volume_fraction = f2

            # plane-level sampling if not direct scalar
            if not p1.use_direct_scalar_cte:
                for row in p1.plane_rows:
                    if row.alpha_standard_deviation:
                        row.alpha_hkl = _sample_value(
                            rng, row.alpha_hkl, row.alpha_standard_deviation, dist
                        )
                    if row.peak_area_standard_deviation:
                        row.peak_area = _sample_value(
                            rng,
                            row.peak_area,
                            row.peak_area_standard_deviation,
                            dist,
                            lower=0.0,
                        )
                    if row.R_factor_standard_deviation:
                        row.R_factor = _sample_value(
                            rng,
                            row.R_factor,
                            row.R_factor_standard_deviation,
                            dist,
                            lower=1e-12,
                        )
            else:
                if p1.direct_alpha is not None:
                    # no per-field sd on direct unless we add one; skip
                    pass

            if not p2.use_direct_scalar_cte:
                for row in p2.plane_rows:
                    if row.alpha_standard_deviation:
                        row.alpha_hkl = _sample_value(
                            rng, row.alpha_hkl, row.alpha_standard_deviation, dist
                        )
                    if row.peak_area_standard_deviation:
                        row.peak_area = _sample_value(
                            rng,
                            row.peak_area,
                            row.peak_area_standard_deviation,
                            dist,
                            lower=0.0,
                        )
                    if row.R_factor_standard_deviation:
                        row.R_factor = _sample_value(
                            rng,
                            row.R_factor,
                            row.R_factor_standard_deviation,
                            dist,
                            lower=1e-12,
                        )

            # elastic sampling
            if p1.Young_modulus_E is not None and p1.E_sd:
                p1.Young_modulus_E = _sample_value(
                    rng, phase1.Young_modulus_E, p1.E_sd, dist, lower=1e-12
                )
            if p2.Young_modulus_E is not None and p2.E_sd:
                p2.Young_modulus_E = _sample_value(
                    rng, phase2.Young_modulus_E, p2.E_sd, dist, lower=1e-12
                )
            if p1.Poisson_ratio_nu is not None and p1.nu_sd:
                p1.Poisson_ratio_nu = _sample_value(
                    rng, phase1.Poisson_ratio_nu, p1.nu_sd, dist, lower=-0.999, upper=0.499
                )
            if p2.Poisson_ratio_nu is not None and p2.nu_sd:
                p2.Poisson_ratio_nu = _sample_value(
                    rng, phase2.Poisson_ratio_nu, p2.nu_sd, dist, lower=-0.999, upper=0.499
                )
            if p1.bulk_modulus_K is not None and p1.K_sd:
                p1.bulk_modulus_K = _sample_value(
                    rng, phase1.bulk_modulus_K, p1.K_sd, dist, lower=1e-12
                )
            if p2.bulk_modulus_K is not None and p2.K_sd:
                p2.bulk_modulus_K = _sample_value(
                    rng, phase2.bulk_modulus_K, p2.K_sd, dist, lower=1e-12
                )
            if p1.shear_modulus_G is not None and p1.G_sd:
                p1.shear_modulus_G = _sample_value(
                    rng, phase1.shear_modulus_G, p1.G_sd, dist, lower=1e-12
                )
            if p2.shear_modulus_G is not None and p2.G_sd:
                p2.shear_modulus_G = _sample_value(
                    rng, phase2.shear_modulus_G, p2.G_sd, dist, lower=1e-12
                )

            # hard rejects
            for p in (p1, p2):
                if p.Poisson_ratio_nu is not None and not (-1 < p.Poisson_ratio_nu < 0.5):
                    raise ValueError("bad nu")
                for name, v in [
                    ("E", p.Young_modulus_E),
                    ("K", p.bulk_modulus_K),
                    ("G", p.shear_modulus_G),
                ]:
                    if v is not None and v <= 0:
                        raise ValueError(f"bad {name}")
                for row in p.plane_rows:
                    if row.enabled and row.peak_area < 0:
                        raise ValueError("neg peak")

            w1 = compute_phase_xrd_cte(p1, settings.cubic_cte_tolerance_relative)
            w2 = compute_phase_xrd_cte(p2, settings.cubic_cte_tolerance_relative)
            a1, a2 = w1.alpha_phase_xrd_SI, w2.alpha_phase_xrd_SI
            e1 = resolve_elastic_properties(p1, settings.elastic_consistency_tolerance_relative)
            e2 = resolve_elastic_properties(p2, settings.elastic_consistency_tolerance_relative)

            if model == ModelName.ROM:
                alpha = model_rom(a1, a2, f1, f2)
            elif model == ModelName.PARALLEL:
                if e1.E is None or e2.E is None:
                    raise ValueError("no E")
                alpha = model_parallel(a1, a2, f1, f2, e1.E, e2.E)
            elif model == ModelName.TURNER:
                if e1.K is None or e2.K is None:
                    raise ValueError("no K")
                alpha = model_turner(a1, a2, f1, f2, e1.K, e2.K)
            elif model == ModelName.KERNER:
                if p1.role == PhaseRole.MATRIX and p2.role == PhaseRole.INCLUSION:
                    am, ai, fm, fi = a1, a2, f1, f2
                    Km, Ki, Gm = e1.K, e2.K, e1.G
                elif p2.role == PhaseRole.MATRIX and p1.role == PhaseRole.INCLUSION:
                    am, ai, fm, fi = a2, a1, f2, f1
                    Km, Ki, Gm = e2.K, e1.K, e2.G
                else:
                    raise ValueError("no matrix")
                if Km is None or Ki is None or Gm is None:
                    raise ValueError("no kerner props")
                alpha = model_kerner(am, ai, fm, fi, Km, Ki, Gm)
            else:
                raise ValueError("unknown model")

            accepted.append(alpha)
            param_rows.append(
                [
                    a1,
                    a2,
                    f1,
                    e1.E or np.nan,
                    e2.E or np.nan,
                    e1.nu if e1.nu is not None else np.nan,
                    e2.nu if e2.nu is not None else np.nan,
                    e1.K or np.nan,
                    e2.K or np.nan,
                    e1.G or np.nan,
                    e2.G or np.nan,
                ]
            )
        except Exception:
            rejected += 1
            continue

    if not accepted:
        return MCResult(
            samples=np.array([]),
            mean=float("nan"),
            median=float("nan"),
            std=float("nan"),
            p2_5=float("nan"),
            p97_5=float("nan"),
            rejected_fraction=1.0,
            n_accepted=0,
            sensitivity=[],
            model_name=model,
        )

    arr = np.array(accepted, dtype=float)
    sensitivity: list[tuple[str, float]] = []
    if len(param_rows) >= 3:
        P = np.array(param_rows, dtype=float)
        for j, name in enumerate(param_names):
            col = P[:, j]
            if np.all(np.isnan(col)) or np.nanstd(col) == 0:
                continue
            mask = ~np.isnan(col)
            if mask.sum() < 3:
                continue
            if np.unique(col[mask]).size < 2 or np.unique(arr[mask]).size < 2:
                continue
            rho, _ = stats.spearmanr(col[mask], arr[mask])
            if np.isnan(rho):
                continue
            sensitivity.append((name, float(abs(rho))))
        sensitivity.sort(key=lambda x: x[1], reverse=True)

    return MCResult(
        samples=arr,
        mean=float(np.mean(arr)),
        median=float(np.median(arr)),
        std=float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0,
        p2_5=float(np.percentile(arr, 2.5)),
        p97_5=float(np.percentile(arr, 97.5)),
        rejected_fraction=rejected / n,
        n_accepted=len(arr),
        sensitivity=sensitivity,
        model_name=model,
    )


def zero_uncertainty_matches_deterministic(
    phase1: PhaseInput,
    phase2: PhaseInput,
    settings: ProjectSettings,
    model: ModelName,
    deterministic_alpha: float,
    tol: float = 1e-12,
) -> bool:
    """Helper for tests: MC with zero SDs collapses to deterministic."""
    # Force zero SDs
    p1 = phase1.model_copy(deep=True)
    p2 = phase2.model_copy(deep=True)
    p1.volume_fraction_sd = None
    p2.volume_fraction_sd = None
    for p in (p1, p2):
        p.E_sd = p.nu_sd = p.K_sd = p.G_sd = None
        for row in p.plane_rows:
            row.alpha_standard_deviation = None
            row.peak_area_standard_deviation = None
            row.R_factor_standard_deviation = None
    mc = run_monte_carlo(p1, p2, settings, model=model, n_samples=20, seed=0)
    if mc.n_accepted == 0:
        return False
    return bool(np.allclose(mc.samples, deterministic_alpha, rtol=0, atol=tol))
