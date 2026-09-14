"""
Target polymer-solution viscosity estimation.

Two quantities are calculated and reported SEPARATELY:

1. Unity (or user target) mobility-ratio viscosity:

       mu_p = (Krw * mu_o) / (M_target * Kro)

   This comes directly from the mobility-ratio definition
   M = (Krw/mu_p) / (Kro/mu_o).

2. A heterogeneity-adjusted "screening" target viscosity:

       mu_target = mu_p * (Kmax / Kmin)

   This is an empirical screening heuristic used by some operators to
   bias the target viscosity upward in heterogeneous reservoirs so
   that the polymer bank also improves vertical sweep. It is NOT part
   of the classical mobility-ratio equation and should be reported as
   a separate, clearly labelled number.
"""

import numpy as np


def calculate_unity_mobility_viscosity(
    oil_viscosity: float,
    krw: float,
    kro: float,
    target_mobility_ratio: float = 1.0,
) -> float:
    if oil_viscosity <= 0:
        raise ValueError("Oil viscosity must be positive.")
    if krw < 0:
        raise ValueError("Krw cannot be negative.")
    if kro <= 0:
        raise ValueError("Kro must be positive.")
    if target_mobility_ratio <= 0:
        raise ValueError("Target mobility ratio must be positive.")

    return (krw * oil_viscosity) / (target_mobility_ratio * kro)


def calculate_heterogeneity_factor(kmax: float, kmin: float) -> float:
    if kmin <= 0 or kmax <= 0:
        raise ValueError("Kmax and Kmin must be positive.")
    if kmax < kmin:
        raise ValueError("Kmax cannot be lower than Kmin.")
    return kmax / kmin


def calculate_heterogeneity_adjusted_viscosity(unity_viscosity: float, heterogeneity_factor: float) -> float:
    return unity_viscosity * heterogeneity_factor


def percentile_permeability_ratio(perms: np.ndarray, low_pct: float = 10, high_pct: float = 90) -> float:
    """A more robust, outlier-resistant alternative to Kmax/Kmin,
    e.g. K90/K10 computed directly from log samples."""
    perms = np.asarray(perms)
    perms = perms[perms > 0]
    if len(perms) < 5:
        raise ValueError("Need at least 5 positive permeability samples.")
    k_high = np.percentile(perms, high_pct)
    k_low = np.percentile(perms, low_pct)
    if k_low <= 0:
        raise ValueError("Low-percentile permeability is non-positive.")
    return float(k_high / k_low)
