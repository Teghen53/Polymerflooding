import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

from utils.dykstra_parsons import (
    read_log_file,
    prepare_log_dataframe,
    calculate_dykstra_parsons_for_interval,
    DEFAULT_NULL_VALUES,
)

st.set_page_config(page_title="Dykstra-Parsons", page_icon="📊", layout="wide")
st.title("📊 Dykstra-Parsons Permeability-Variation Coefficient")

st.markdown(
    """
Upload a permeability log (depth + permeability), define one or more
reservoir intervals, and the app will calculate the Dykstra-Parsons
coefficient (V_DP) for each interval using thickness-weighted,
log-probability statistics.
"""
)

# ----------------------------------------------------------------------
# 1. Upload log file
# ----------------------------------------------------------------------
st.header("1. Upload permeability log")

use_sample = st.checkbox("Use built-in sample log data (for demonstration)", value=False)

raw_df = None
if use_sample:
    rng = np.random.default_rng(42)
    depths = np.arange(2000, 2100, 0.5)
    perms = np.clip(400 * np.exp(-(depths - 2000) / 60) * rng.lognormal(0, 0.35, len(depths)), 0.5, None)
    raw_df = pd.DataFrame({"DEPTH": depths, "PERM": perms})
    st.success("Using built-in sample log data.")
else:
    uploaded_log = st.file_uploader(
        "Upload Excel/CSV well log file",
        type=["xlsx", "xls", "csv"],
        key="log_upload",
    )
    if uploaded_log is not None:
        try:
            raw_df = read_log_file(uploaded_log)
            st.success(f"Loaded file with {len(raw_df)} rows and columns: {list(raw_df.columns)}")
        except Exception as e:
            st.error(f"Could not read file: {e}")

if raw_df is not None:
    with st.expander("Preview raw file"):
        st.dataframe(raw_df.head(20), use_container_width=True)

    st.header("2. Map columns and handle null values")

    col1, col2, col3 = st.columns(3)
    with col1:
        depth_col = st.selectbox("Depth column", options=list(raw_df.columns), index=0)
    with col2:
        perm_col = st.selectbox("Permeability column", options=list(raw_df.columns), index=min(1, len(raw_df.columns) - 1))
    with col3:
        skip_units_row = st.checkbox("File has a units row below the header (skip it)", value=False)

    extra_nulls_str = st.text_input(
        "Additional null-value codes (comma separated)",
        value=", ".join(str(v) for v in DEFAULT_NULL_VALUES),
    )
    try:
        null_values = [float(v.strip()) for v in extra_nulls_str.split(",") if v.strip() != ""]
    except ValueError:
        st.warning("Could not parse null-value list; using defaults.")
        null_values = DEFAULT_NULL_VALUES

    try:
        log_df = prepare_log_dataframe(
            raw_df, depth_col, perm_col, null_values=null_values, skip_units_row=skip_units_row
        )
        st.success(f"{len(log_df)} valid (Depth, Permeability) samples after cleaning.")
    except Exception as e:
        st.error(f"Error preparing log data: {e}")
        log_df = None

    if log_df is not None and len(log_df) > 0:
        with st.expander("Preview cleaned data"):
            st.dataframe(log_df, use_container_width=True)

        # ------------------------------------------------------------------
        # 3. Define reservoirs
        # ------------------------------------------------------------------
        st.header("3. Define reservoir intervals")

        n_reservoirs = st.number_input("How many reservoirs?", min_value=1, max_value=20, value=1, step=1)

        reservoirs = []
        for i in range(int(n_reservoirs)):
            st.markdown(f"**Reservoir {i + 1}**")
            c1, c2, c3 = st.columns(3)
            with c1:
                name = st.text_input(f"Name (reservoir {i + 1})", value=f"Reservoir {i + 1}", key=f"name_{i}")
            with c2:
                top = st.number_input(
                    f"Top depth", value=float(log_df["Depth"].min()), key=f"top_{i}",
                    min_value=float(log_df["Depth"].min()), max_value=float(log_df["Depth"].max()),
                )
            with c3:
                bottom = st.number_input(
                    f"Bottom depth", value=float(log_df["Depth"].max()), key=f"bottom_{i}",
                    min_value=float(log_df["Depth"].min()), max_value=float(log_df["Depth"].max()),
                )
            reservoirs.append({"name": name, "top": top, "bottom": bottom})

        if st.button("Calculate Dykstra-Parsons coefficients", type="primary"):
            results = []
            for res in reservoirs:
                r = calculate_dykstra_parsons_for_interval(log_df, res["top"], res["bottom"], res["name"])
                results.append(r)

            st.session_state["dp_results"] = results

            st.header("4. Results")

            for r in results:
                st.subheader(f"📍 {r['reservoir']}  ({r['top']:.1f}–{r['bottom']:.1f} m)")

                if "error" in r:
                    st.warning(r["error"])
                    continue

                m1, m2, m3, m4, m5, m6 = st.columns(6)
                m1.metric("Samples", r["n_samples"])
                m2.metric("k min (mD)", f"{r['k_min']:.1f}")
                m3.metric("k max (mD)", f"{r['k_max']:.1f}")
                m4.metric("k50 (mD)", f"{r['k50']:.1f}")
                m5.metric("k84.1 (mD)", f"{r['k84.1']:.1f}")
                m6.metric("V_DP", f"{r['V_DP']:.3f}")

                st.caption(f"Classification: **{r['classification']}**  |  "
                           f"Arithmetic k = {r['k_arithmetic']:.1f} mD  |  "
                           f"Geometric k = {r['k_geometric']:.1f} mD")

                col_a, col_b = st.columns(2)
                with col_a:
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=r["sorted_perms"], y=r["sorted_depths"],
                        mode="lines+markers", line=dict(color="teal"), marker=dict(size=4),
                    ))
                    fig.update_xaxes(type="log", title="Permeability (mD)")
                    fig.update_yaxes(autorange="reversed", title="Depth")
                    fig.update_layout(height=380, title="Permeability vs depth")
                    st.plotly_chart(fig, use_container_width=True)

                with col_b:
                    sorted_perm = np.sort(r["sorted_perms"])[::-1]
                    cum_prob = np.linspace(1, len(sorted_perm), len(sorted_perm)) / (len(sorted_perm) + 1)
                    fig2 = go.Figure()
                    fig2.add_trace(go.Scatter(x=cum_prob * 100, y=sorted_perm, mode="markers", marker=dict(color="indianred")))
                    fig2.add_vline(x=50, line_dash="dot")
                    fig2.add_vline(x=84.1, line_dash="dot")
                    fig2.update_yaxes(type="log", title="Permeability (mD)")
                    fig2.update_xaxes(title="Cumulative probability (%)")
                    fig2.update_layout(height=380, title="Log-probability plot")
                    st.plotly_chart(fig2, use_container_width=True)

            valid_results = [r for r in results if "error" not in r]
            if valid_results:
                summary_table = pd.DataFrame([
                    {
                        "Reservoir": r["reservoir"],
                        "Top": r["top"],
                        "Bottom": r["bottom"],
                        "Samples": r["n_samples"],
                        "k_min": round(r["k_min"], 1),
                        "k_max": round(r["k_max"], 1),
                        "k50": round(r["k50"], 1),
                        "k84.1": round(r["k84.1"], 1),
                        "V_DP": round(r["V_DP"], 3),
                        "Classification": r["classification"],
                    }
                    for r in valid_results
                ])
                st.subheader("Summary table (all reservoirs)")
                st.dataframe(summary_table, use_container_width=True)

                csv = summary_table.to_csv(index=False).encode("utf-8")
                st.download_button("Download summary as CSV", data=csv, file_name="dykstra_parsons_summary.csv", mime="text/csv")

                # Store Kmax/Kmin per reservoir for use in Module 3
                st.session_state["reservoir_kmax_kmin"] = {
                    r["reservoir"]: {"k_max": r["k_max"], "k_min": r["k_min"]} for r in valid_results
                }
else:
    st.info("Upload a permeability log file or check the sample-data box above to begin.")
