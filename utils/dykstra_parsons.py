"""
Dykstra-Parsons permeability-variation coefficient calculation from
well-log depth/permeability data, for one or several reservoir
intervals.

V_DP = (k50 - k84.1) / k50

where k50 and k84.1 are permeabilities read from the cumulative
log-probability distribution of the samples (thickness-weighted),
at 50% and 84.1% probability of exceedance respectively.
"""

import numpy as np
import pandas as pd

DEFAULT_NULL_VALUES = [-999.25, -999, -9999, -9999.25]


def read_log_file(uploaded_file, null_values=None) -> pd.DataFrame:
    """Read a well-log file (Excel, CSV) with header row + units row,
    as commonly exported from petrophysical software.

    Returns a raw DataFrame; column selection and null handling is done
    by `prepare_log_dataframe`.
    """
    name = str(getattr(uploaded_file, "name", "")).lower()
    if name.endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)
    return df


def prepare_log_dataframe(
    df: pd.DataFrame,
    depth_column: str,
    permeability_column: str,
    null_values=None,
    skip_units_row: bool = False,
) -> pd.DataFrame:
    """Clean a raw log DataFrame down to Depth / Permeability columns."""
    null_values = null_values if null_values is not None else DEFAULT_NULL_VALUES

    work = df.copy()
    if skip_units_row:
        work = work.iloc[1:].reset_index(drop=True)

    work = work[[depth_column, permeability_column]].copy()
    work.columns = ["Depth", "Permeability"]

    work["Depth"] = pd.to_numeric(work["Depth"], errors="coerce")
    work["Permeability"] = pd.to_numeric(work["Permeability"], errors="coerce")

    for nv in null_values:
        work.loc[np.isclose(work["Permeability"], nv, equal_nan=False), "Permeability"] = np.nan
        work.loc[np.isclose(work["Depth"], nv, equal_nan=False), "Depth"] = np.nan

    work = work.dropna().sort_values("Depth").reset_index(drop=True)
    return work


def _thickness_weights(depths: np.ndarray) -> np.ndarray:
    """Approximate sample thickness for (possibly) irregularly sampled
    depth data using the midpoint-difference method."""
    if len(depths) == 1:
        return np.array([1.0])
    diffs = np.diff(depths)
    median_step = np.median(diffs)
    thickness = np.empty_like(depths, dtype=float)
    thickness[0] = diffs[0] if len(diffs) > 0 else median_step
    thickness[-1] = diffs[-1] if len(diffs) > 0 else median_step
    if len(depths) > 2:
        thickness[1:-1] = (diffs[:-1] + diffs[1:]) / 2.0
    return np.clip(thickness, 1e-6, None)


def _log_probability_value(permeability: np.ndarray, weights: np.ndarray, target_prob: float) -> float:
    """Interpolate permeability at a given cumulative probability
    (of exceedance, sorted from highest to lowest permeability), using
    thickness weighting and log-linear interpolation."""
    order = np.argsort(-permeability)  # descending permeability
    k_sorted = permeability[order]
    w_sorted = weights[order]

    cum_weight = np.cumsum(w_sorted)
    total_weight = cum_weight[-1]
    cum_fraction = cum_weight / total_weight

    log_k = np.log10(k_sorted)
    return float(10 ** np.interp(target_prob, cum_fraction, log_k))


def calculate_dykstra_parsons_for_interval(
    log_df: pd.DataFrame,
    top: float,
    bottom: float,
    reservoir_name: str = "",
) -> dict:
    """Calculate Dykstra-Parsons statistics for a single depth interval.

    `log_df` must have columns Depth, Permeability (see
    `prepare_log_dataframe`).
    """
    lo, hi = (top, bottom) if top <= bottom else (bottom, top)

    interval = log_df[(log_df["Depth"] >= lo) & (log_df["Depth"] <= hi)]
    interval = interval[interval["Permeability"] > 0].reset_index(drop=True)

    if len(interval) < 5:
        return {
            "reservoir": reservoir_name,
            "top": top,
            "bottom": bottom,
            "n_samples": len(interval),
            "error": "Fewer than 5 valid positive-permeability samples in this interval.",
        }

    depths = interval["Depth"].to_numpy()
    perms = interval["Permeability"].to_numpy()
    weights = _thickness_weights(depths)

    k50 = _log_probability_value(perms, weights, 0.50)
    k841 = _log_probability_value(perms, weights, 0.841)

    vdp = (k50 - k841) / k50
    vdp = float(np.clip(vdp, 0.0, 0.999))

    if vdp < 0.25:
        classification = "Low heterogeneity"
    elif vdp < 0.50:
        classification = "Moderate heterogeneity"
    elif vdp < 0.75:
        classification = "High heterogeneity"
    else:
        classification = "Very high heterogeneity"

    k_geometric = float(10 ** np.average(np.log10(perms), weights=weights))
    k_arithmetic = float(np.average(perms, weights=weights))

    return {
        "reservoir": reservoir_name,
        "top": lo,
        "bottom": hi,
        "gross_thickness": float(hi - lo),
        "n_samples": int(len(interval)),
        "k_min": float(perms.min()),
        "k_max": float(perms.max()),
        "k_arithmetic": k_arithmetic,
        "k_geometric": k_geometric,
        "k50": k50,
        "k84.1": k841,
        "V_DP": vdp,
        "classification": classification,
        "sorted_depths": depths,
        "sorted_perms": perms,
    }
