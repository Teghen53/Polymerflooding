import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

from utils.fractional_flow import (
    read_relative_permeability_excel,
    fractional_flow_curve,
    welge_construction,
    displacement_efficiency,
)

st.set_page_config(page_title="Displacement Efficiency", page_icon="📉", layout="wide")
st.title("📉 Displacement Efficiency (Fractional-Flow / Welge Analysis)")

st.markdown(
    """
Upload a relative-permeability table and enter the fluid viscosities.
The app calculates and plots the water and polymer fractional-flow
curves, performs the Welge tangent construction, and estimates the
displacement efficiency for each flood.
"""
)

# ----------------------------------------------------------------------
# 1. Input: relative permeability file
# ----------------------------------------------------------------------
st.header("1. Relative permeability data")

use_sample = st.checkbox("Use built-in sample data (for demonstration)", value=False)

kr_df = None

if use_sample:
    kr_df = pd.DataFrame({
        "Sw": [0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70],
        "Krw": [0.000, 0.010, 0.025, 0.050, 0.085, 0.130, 0.185, 0.250, 0.320, 0.400, 0.480],
        "Kro": [0.850, 0.670, 0.510, 0.380, 0.270, 0.180, 0.110, 0.060, 0.025, 0.005, 0.000],
    })
    st.success("Using built-in sample relative-permeability data.")
else:
    uploaded_kr = st.file_uploader(
        "Upload Excel/CSV file with columns: Sw, Krw, Kro",
        type=["xlsx", "xls", "csv"],
        key="kr_upload",
    )
    if uploaded_kr is not None:
        try:
            kr_df = read_relative_permeability_excel(uploaded_kr)
            st.success(f"Loaded {len(kr_df)} valid rows.")
        except Exception as e:
            st.error(f"Could not read file: {e}")

if kr_df is not None:
    with st.expander("View relative-permeability data"):
        st.dataframe(kr_df, use_container_width=True)

    # ------------------------------------------------------------------
    # 2. Fluid properties
    # ------------------------------------------------------------------
    st.header("2. Fluid properties")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        mu_water = st.number_input("Injected water viscosity (cP)", min_value=0.01, value=0.60, step=0.05, format="%.3f")
    with c2:
        mu_polymer = st.number_input("Polymer solution viscosity (cP)", min_value=0.01, value=18.0, step=0.5, format="%.3f")
    with c3:
        mu_oil = st.number_input("Oil viscosity (cP)", min_value=0.01, value=5.0, step=0.5, format="%.3f")
    with c4:
        sor_input = st.number_input(
            "Residual oil saturation, Sor (optional, 0 = ignore)",
            min_value=0.0, max_value=0.9, value=0.0, step=0.01,
        )

    swirr_override = st.number_input(
        "Irreducible water saturation, Swirr (defaults to minimum Sw in table)",
        min_value=float(kr_df["Sw"].min()),
        max_value=float(kr_df["Sw"].max()),
        value=float(kr_df["Sw"].min()),
        step=0.01,
    )

    # ------------------------------------------------------------------
    # 3. Calculations
    # ------------------------------------------------------------------
    try:
        water_curve = fractional_flow_curve(kr_df, mu_water, mu_oil, swirr=swirr_override)
        polymer_curve = fractional_flow_curve(kr_df, mu_polymer, mu_oil, swirr=swirr_override)

        water_welge = welge_construction(water_curve)
        polymer_welge = welge_construction(polymer_curve)

        sor_arg = sor_input if sor_input > 0 else None
        water_ed = displacement_efficiency(water_welge["sw_average_behind_front"], water_welge["swirr"], sor_arg)
        polymer_ed = displacement_efficiency(polymer_welge["sw_average_behind_front"], polymer_welge["swirr"], sor_arg)

        # Store for use in the target-viscosity module
        st.session_state["kr_df"] = kr_df
        st.session_state["mu_oil"] = mu_oil
        st.session_state["water_welge"] = water_welge
        st.session_state["polymer_welge"] = polymer_welge

        # ------------------------------------------------------------------
        # 4. Plots
        # ------------------------------------------------------------------
        st.header("3. Results")

        col_a, col_b = st.columns(2)

        with col_a:
            st.subheader("Relative permeability curves")
            fig_kr = go.Figure()
            fig_kr.add_trace(go.Scatter(x=water_curve["Sw"], y=water_curve["Krw"], name="Krw", line=dict(color="royalblue", width=3)))
            fig_kr.add_trace(go.Scatter(x=water_curve["Sw"], y=water_curve["Kro"], name="Kro", line=dict(color="darkorange", width=3)))
            fig_kr.update_layout(xaxis_title="Sw", yaxis_title="Relative permeability", yaxis_range=[0, 1], height=420)
            st.plotly_chart(fig_kr, use_container_width=True)

        with col_b:
            st.subheader("Fractional-flow curves & Welge tangents")
            fig_fw = go.Figure()
            fig_fw.add_trace(go.Scatter(x=water_curve["Sw"], y=water_curve["Fw"], name="Fw – water", line=dict(color="royalblue", width=3)))
            fig_fw.add_trace(go.Scatter(x=polymer_curve["Sw"], y=polymer_curve["Fw"], name="Fw – polymer", line=dict(color="seagreen", width=3)))
            fig_fw.add_trace(go.Scatter(x=water_curve["Sw"], y=water_welge["tangent_line"], name="Water tangent", line=dict(color="royalblue", dash="dash")))
            fig_fw.add_trace(go.Scatter(x=polymer_curve["Sw"], y=polymer_welge["tangent_line"], name="Polymer tangent", line=dict(color="seagreen", dash="dash")))
            fig_fw.add_trace(go.Scatter(
                x=[water_welge["sw_front"], polymer_welge["sw_front"]],
                y=[water_welge["fw_front"], polymer_welge["fw_front"]],
                mode="markers", marker=dict(size=11, color=["royalblue", "seagreen"], symbol="x"),
                name="Shock-front point",
            ))
            fig_fw.update_layout(xaxis_title="Sw", yaxis_title="Fw", yaxis_range=[0, 1.05], height=420)
            st.plotly_chart(fig_fw, use_container_width=True)

        st.subheader("Fractional-flow derivative (dFw/dSw)")
        fig_d = go.Figure()
        fig_d.add_trace(go.Scatter(x=water_curve["Sw"], y=water_curve["dFw_dSw"], name="dFw/dSw – water", line=dict(color="royalblue")))
        fig_d.add_trace(go.Scatter(x=polymer_curve["Sw"], y=polymer_curve["dFw_dSw"], name="dFw/dSw – polymer", line=dict(color="seagreen")))
        fig_d.add_vline(x=water_welge["sw_front"], line_dash="dot", line_color="royalblue")
        fig_d.add_vline(x=polymer_welge["sw_front"], line_dash="dot", line_color="seagreen")
        fig_d.update_layout(xaxis_title="Sw", yaxis_title="dFw/dSw", height=350)
        st.plotly_chart(fig_d, use_container_width=True)

        st.subheader("Summary")

        summary_df = pd.DataFrame({
            "Quantity": [
                "Swirr",
                "Shock-front saturation, Swf",
                "Fw at shock front",
                "Average Sw behind front",
                "Displacement efficiency (OOIP basis)",
            ] + (["Displacement efficiency (movable-oil basis)"] if sor_arg else []),
            "Water flood": [
                f"{water_welge['swirr']:.3f}",
                f"{water_welge['sw_front']:.3f}",
                f"{water_welge['fw_front']:.3f}",
                f"{water_welge['sw_average_behind_front']:.3f}",
                f"{water_ed['Ed_OOIP_basis']*100:.1f}%",
            ] + ([f"{water_ed.get('Ed_movable_oil_basis', float('nan'))*100:.1f}%"] if sor_arg else []),
            "Polymer flood": [
                f"{polymer_welge['swirr']:.3f}",
                f"{polymer_welge['sw_front']:.3f}",
                f"{polymer_welge['fw_front']:.3f}",
                f"{polymer_welge['sw_average_behind_front']:.3f}",
                f"{polymer_ed['Ed_OOIP_basis']*100:.1f}%",
            ] + ([f"{polymer_ed.get('Ed_movable_oil_basis', float('nan'))*100:.1f}%"] if sor_arg else []),
        })
        st.table(summary_df)

        incremental = (polymer_ed["Ed_OOIP_basis"] - water_ed["Ed_OOIP_basis"]) * 100
        st.metric("Incremental displacement efficiency from polymer", f"{incremental:.1f} percentage points")

        csv = summary_df.to_csv(index=False).encode("utf-8")
        st.download_button("Download summary as CSV", data=csv, file_name="displacement_efficiency_summary.csv", mime="text/csv")

    except Exception as e:
        st.error(f"Calculation error: {e}")

else:
    st.info("Upload a relative-permeability file or check the sample-data box above to begin.")
