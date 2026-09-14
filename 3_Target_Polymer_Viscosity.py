import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

from utils.polymer_viscosity import (
    calculate_unity_mobility_viscosity,
    calculate_heterogeneity_factor,
    calculate_heterogeneity_adjusted_viscosity,
)
from utils.fractional_flow import build_kr_interpolators

st.set_page_config(page_title="Target Polymer Viscosity", page_icon="🧪", layout="wide")
st.title("🧪 Target Polymer-Solution Viscosity")

st.markdown(
    """
Calculates the polymer-solution viscosity required to reach a target
mobility ratio, then applies an optional heterogeneity multiplier
(Kmax/Kmin) as a screening adjustment.
"""
)

# ----------------------------------------------------------------------
# 1. Reservoir selection
# ----------------------------------------------------------------------
st.header("1. Reservoir(s)")

dp_results = st.session_state.get("reservoir_kmax_kmin", None)

if dp_results:
    st.success(
        f"Found Kmax/Kmin for {len(dp_results)} reservoir(s) from the "
        "Dykstra-Parsons module. You can reuse them below or override manually."
    )
    reservoir_names = list(dp_results.keys())
else:
    st.info(
        "No Dykstra-Parsons results found in this session yet. "
        "You can still enter Kmax/Kmin manually below, or run Module 2 first."
    )
    reservoir_names = []

n_reservoirs = st.number_input(
    "Number of reservoirs to evaluate",
    min_value=1, max_value=20,
    value=max(1, len(reservoir_names)),
    step=1,
)

# ----------------------------------------------------------------------
# 2. Kro / Krw source
# ----------------------------------------------------------------------
st.header("2. Relative permeability endpoints (Kro, Krw)")

kr_df = st.session_state.get("kr_df", None)
mu_oil_default = st.session_state.get("mu_oil", 5.0)

kr_source = st.radio(
    "How do you want to provide Kro / Krw?",
    options=["Enter manually for each reservoir", "Read from uploaded relative-permeability curve (Module 1)"],
    horizontal=False,
)

sw_eval = None
krw_interp = kro_interp = None

if kr_source.startswith("Read"):
    if kr_df is None:
        st.warning("No relative-permeability data found. Please run Module 1 first, or switch to manual entry.")
    else:
        krw_interp, kro_interp = build_kr_interpolators(kr_df)
        default_sw = st.session_state.get("polymer_welge", {}).get("sw_average_behind_front", float(kr_df["Sw"].mean()))
        sw_eval = st.number_input(
            "Water saturation at which to evaluate Kro/Krw",
            min_value=float(kr_df["Sw"].min()),
            max_value=float(kr_df["Sw"].max()),
            value=float(np.clip(default_sw, kr_df["Sw"].min(), kr_df["Sw"].max())),
            step=0.01,
            help="Defaults to the average Sw behind the front calculated in Module 1, if available.",
        )
        st.info(f"Krw = {float(krw_interp(sw_eval)):.4f}   |   Kro = {float(kro_interp(sw_eval)):.4f}  at Sw = {sw_eval:.3f}")

st.header("3. Target mobility ratio & oil viscosity")

c1, c2 = st.columns(2)
with c1:
    target_M = st.number_input("Target mobility ratio, M (1.0 = unity mobility)", min_value=0.01, value=1.0, step=0.1)
with c2:
    mu_oil = st.number_input("Oil viscosity (cP)", min_value=0.01, value=float(mu_oil_default), step=0.5)

apply_heterogeneity = st.checkbox("Apply heterogeneity multiplier (Kmax/Kmin) to target viscosity", value=True)

st.divider()
st.header("4. Reservoir inputs & results")

rows = []
for i in range(int(n_reservoirs)):
    st.markdown(f"**Reservoir {i + 1}**")
    default_name = reservoir_names[i] if i < len(reservoir_names) else f"Reservoir {i + 1}"

    cols = st.columns(6 if kr_source.startswith("Enter") else 4)

    name = cols[0].text_input("Name", value=default_name, key=f"visc_name_{i}")

    if dp_results and default_name in dp_results:
        default_kmax = dp_results[default_name]["k_max"]
        default_kmin = dp_results[default_name]["k_min"]
    else:
        default_kmax, default_kmin = 500.0, 50.0

    kmax = cols[1].number_input("Kmax (mD)", min_value=0.01, value=float(default_kmax), key=f"kmax_{i}")
    kmin = cols[2].number_input("Kmin (mD)", min_value=0.01, value=float(default_kmin), key=f"kmin_{i}")

    if kr_source.startswith("Enter"):
        krw_i = cols[3].number_input("Krw", min_value=0.0, value=0.30, step=0.01, key=f"krw_{i}")
        kro_i = cols[4].number_input("Kro", min_value=0.001, value=0.60, step=0.01, key=f"kro_{i}")
    else:
        krw_i = float(krw_interp(sw_eval)) if krw_interp is not None else None
        kro_i = float(kro_interp(sw_eval)) if kro_interp is not None else None
        cols[3].metric("Krw (from curve)", f"{krw_i:.4f}" if krw_i is not None else "N/A")

    try:
        if kmax < kmin:
            raise ValueError("Kmax must be greater than or equal to Kmin.")
        if krw_i is None or kro_i is None:
            raise ValueError("Kro/Krw not available — upload relative-permeability data in Module 1.")

        unity_visc = calculate_unity_mobility_viscosity(mu_oil, krw_i, kro_i, target_M)
        het_factor = calculate_heterogeneity_factor(kmax, kmin)
        adjusted_visc = calculate_heterogeneity_adjusted_viscosity(unity_visc, het_factor) if apply_heterogeneity else None

        rows.append({
            "Reservoir": name,
            "Kmax (mD)": kmax,
            "Kmin (mD)": kmin,
            "Kmax/Kmin": round(het_factor, 2),
            "Krw": round(krw_i, 4),
            "Kro": round(kro_i, 4),
            "Mobility-ratio viscosity (cP)": round(unity_visc, 2),
            "Heterogeneity-adjusted target (cP)": round(adjusted_visc, 2) if adjusted_visc is not None else "—",
        })
    except Exception as e:
        st.error(f"{name}: {e}")

if rows:
    st.subheader("Summary")
    results_df = pd.DataFrame(rows)
    st.dataframe(results_df, use_container_width=True)

    fig = go.Figure()
    fig.add_trace(go.Bar(x=results_df["Reservoir"], y=results_df["Mobility-ratio viscosity (cP)"], name="Mobility-ratio viscosity"))
    if apply_heterogeneity:
        fig.add_trace(go.Bar(x=results_df["Reservoir"], y=results_df["Heterogeneity-adjusted target (cP)"], name="Heterogeneity-adjusted target"))
    fig.update_layout(barmode="group", yaxis_title="Viscosity (cP)", height=420)
    st.plotly_chart(fig, use_container_width=True)

    csv = results_df.to_csv(index=False).encode("utf-8")
    st.download_button("Download results as CSV", data=csv, file_name="target_polymer_viscosity.csv", mime="text/csv")

    st.warning(
        "⚠️ **Engineering note:** multiplying the mobility-ratio viscosity by "
        "Kmax/Kmin is a common empirical screening heuristic, not part of the "
        "classical mobility-ratio equation. It can be very sensitive to a "
        "single permeability outlier — consider cross-checking with a "
        "percentile-based ratio (e.g. K90/K10) computed directly from the log."
    )
