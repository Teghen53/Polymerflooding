import streamlit as st

st.set_page_config(
    page_title="Polymer Flood Screening Tool",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded", # <-- forces sidebar open on load
)

st.title("🧪 Polymer Flood Screening & Design Tool")

st.markdown(
    """
Welcome! This application supports three reservoir-engineering screening
workflows for waterflood-to-polymer-flood conversion projects.

Use the **sidebar navigation** to open a module.
"""
)

col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("1️⃣ Displacement Efficiency")
    st.markdown(
        """
        - Upload relative-permeability curves (Sw, Krw, Kro)
        - Enter water, polymer and oil viscosities
        - Plots relative permeability & fractional-flow curves
        - Automatic Welge tangent construction
        - Calculates displacement efficiency for water vs. polymer
        """
    )

with col2:
    st.subheader("2️⃣ Dykstra-Parsons")
    st.markdown(
        """
        - Upload permeability log (depth + permeability)
        - Define any number of reservoir intervals
        - Automatic null-value handling
        - Calculates V_DP for every reservoir
        - Permeability log & probability plots
        """
    )

with col3:
    st.subheader("3️⃣ Target Polymer Viscosity")
    st.markdown(
        """
        - Enter Kmax / Kmin per reservoir (or reuse module 2 results)
        - Enter Kro / Krw (manual or from module 1 curves)
        - Calculates unity-mobility-ratio viscosity
        - Calculates heterogeneity-adjusted screening target
        """
    )

st.divider()

st.info(
    "💡 Tip: Results calculated in one module (e.g. relative-permeability "
    "curves or Dykstra-Parsons Kmax/Kmin) are automatically carried over "
    "to the other modules via the session state, so you only need to "
    "enter data once."
)

with st.expander("📄 Expected file formats"):
    st.markdown("**Relative permeability file** (Module 1) — columns:")
    st.code("Sw, Krw, Kro", language="text")

    st.markdown("**Permeability log file** (Module 2) — columns, e.g.:")
    st.code("DEPTH, PERM   (any column names — you will map them in-app)", language="text")
    st.markdown(
        "Null values such as `-999.25` are automatically detected and "
        "removed. You can add extra null-value codes in the module itself."
    )
