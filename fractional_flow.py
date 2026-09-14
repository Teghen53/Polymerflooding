"""
Fractional-flow and Buckley-Leverett / Welge displacement-efficiency
calculations for waterflood and polymer-flood screening.

Assumptions
-----------
- 1-D, horizontal, incompressible, immiscible two-phase flow.
- Gravity and capillary-pressure effects are neglected.
- Relative permeability data are supplied as a function of water
  saturation (Sw) with columns: Sw, Krw, Kro.
"""

import numpy as np
import pandas as pd
from scipy.interpolate import PchipInterpolator


REQUIRED_KR_COLUMNS = ["Sw", "Krw", "Kro"]


def read_relative_permeability_excel(uploaded_file) -> pd.DataFrame:
    """Read and validate a relative-permeability Excel/CSV file.

    Expected columns (case-insensitive, order-insensitive):
        Sw, Krw, Kro
    """
    if hasattr(uploaded_file, "name") and str(uploaded_file.name).lower().endswith(".csv"):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)

    # Normalise column names
    rename_map = {}
    for col in df.columns:
        key = str(col).strip().lower()
        if key in ("sw", "s_w", "water saturation"):
            rename_map[col] = "Sw"
        elif key in ("krw", "kr_w", "water rel perm"):
            rename_map[col] = "Krw"
        elif key in ("kro", "kr_o", "oil rel perm"):
            rename_map[col] = "Kro"
    df = df.rename(columns=rename_map)

    missing = [c for c in REQUIRED_KR_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"The uploaded file is missing required column(s): {missing}. "
            f"Expected columns: {REQUIRED_KR_COLUMNS}"
        )

    df = df[REQUIRED_KR_COLUMNS].apply(pd.to_numeric, errors="coerce")
    df = df.dropna().sort_values("Sw").drop_duplicates(subset="Sw").reset_index(drop=True)

    if len(df) < 4:
        raise ValueError("At least four valid (Sw, Krw, Kro) rows are required.")

    if df["Sw"].min() < 0 or df["Sw"].max() > 1:
        raise ValueError("Sw values must lie between 0 and 1.")

    if (df["Krw"] < 0).any() or (df["Kro"] < 0).any():
        raise ValueError("Krw and Kro values cannot be negative.")

    return df


def build_kr_interpolators(kr_df: pd.DataFrame):
    """Return shape-preserving (PCHIP) interpolators for Krw(Sw) and Kro(Sw)."""
    krw_interp = PchipInterpolator(kr_df["Sw"].to_numpy(), kr_df["Krw"].to_numpy())
    kro_interp = PchipInterpolator(kr_df["Sw"].to_numpy(), kr_df["Kro"].to_numpy())
    return krw_interp, kro_interp


def fractional_flow_curve(
    kr_df: pd.DataFrame,
    displacing_fluid_viscosity: float,
    oil_viscosity: float,
    swirr: float = None,
    n_points: int = 400,
):
    """Compute a dense fractional-flow curve fw(Sw) for a given displacing
    fluid (water or polymer solution) and oil viscosity.

    Returns a dict with dense Sw grid, fw, and dfw/dSw (analytical PCHIP
    derivative of the resulting fw(Sw) function).
    """
    if displacing_fluid_viscosity <= 0 or oil_viscosity <= 0:
        raise ValueError("Viscosities must be strictly positive.")

    sw_min = kr_df["Sw"].min()
    sw_max = kr_df["Sw"].max()

    if swirr is None:
        swirr = sw_min

    krw_interp, kro_interp = build_kr_interpolators(kr_df)

    sw_grid = np.linspace(sw_min, sw_max, n_points)
    krw_grid = np.clip(krw_interp(sw_grid), 0, None)
    kro_grid = np.clip(kro_interp(sw_grid), 0, None)

    water_mobility = krw_grid / displacing_fluid_viscosity
    oil_mobility = kro_grid / oil_viscosity
    total_mobility = water_mobility + oil_mobility

    # Avoid division by zero where both mobilities are zero (e.g. Sw < Swirr)
    with np.errstate(divide="ignore", invalid="ignore"):
        fw_grid = np.where(total_mobility > 0, water_mobility / total_mobility, 0.0)

    fw_interp = PchipInterpolator(sw_grid, fw_grid)
    dfw_dsw_grid = fw_interp.derivative()(sw_grid)

    return {
        "Sw": sw_grid,
        "Krw": krw_grid,
        "Kro": kro_grid,
        "Fw": fw_grid,
        "dFw_dSw": dfw_dsw_grid,
        "swirr": swirr,
        "sw_max": sw_max,
        "fw_interp": fw_interp,
    }


def welge_construction(curve: dict):
    """Determine the Welge tangent (shock-front) construction from a
    fractional-flow curve produced by `fractional_flow_curve`.

    Method
    ------
    The correct Welge tangent point Sw_f satisfies:

        dFw/dSw |_Swf  =  Fw(Swf) / (Swf - Swirr)

    which is mathematically identical to finding the saturation that
    MAXIMIZES the secant slope drawn from (Swirr, 0) to the fractional-flow
    curve. We use the maximum-secant-slope approach because it is
    numerically robust and does not require root finding.
    """
    sw = curve["Sw"]
    fw = curve["Fw"]
    swirr = curve["swirr"]

    valid = sw > (swirr + 1e-9)
    sw_valid = sw[valid]
    fw_valid = fw[valid]

    secant_slope = fw_valid / (sw_valid - swirr)

    idx = int(np.argmax(secant_slope))
    sw_front = float(sw_valid[idx])
    fw_front = float(fw_valid[idx])
    tangent_slope = float(secant_slope[idx])

    if tangent_slope <= 0:
        raise ValueError(
            "Unable to determine a valid Welge tangent. Check that Krw "
            "increases with Sw and that viscosities are realistic."
        )

    # Extend tangent to Fw = 1 to obtain average Sw behind the front
    sw_average_behind_front = swirr + 1.0 / tangent_slope

    tangent_line = np.clip(tangent_slope * (sw - swirr), 0, 1.08)

    return {
        "swirr": swirr,
        "sw_front": sw_front,
        "fw_front": fw_front,
        "tangent_slope": tangent_slope,
        "sw_average_behind_front": sw_average_behind_front,
        "tangent_line": tangent_line,
    }


def displacement_efficiency(sw_average_behind_front: float, swirr: float, sor: float = None):
    """Calculate displacement efficiency (pore-volume basis).

    If `sor` (residual oil saturation) is provided, also returns the
    efficiency relative to technically movable oil.
    """
    if swirr >= 1:
        raise ValueError("Swirr must be lower than 1.")

    ed_ooip = (sw_average_behind_front - swirr) / (1.0 - swirr)
    ed_ooip = float(np.clip(ed_ooip, 0.0, 1.0))

    result = {"Ed_OOIP_basis": ed_ooip}

    if sor is not None and (1 - swirr - sor) > 0:
        ed_movable = (sw_average_behind_front - swirr) / (1.0 - swirr - sor)
        result["Ed_movable_oil_basis"] = float(np.clip(ed_movable, 0.0, 1.0))

    return result
