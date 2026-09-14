# 🧪 Polymer Flood Screening & Design Tool

A Streamlit web application for reservoir engineers screening
waterflood-to-polymer-flood conversion candidates. It provides three
linked modules:

1. **Displacement Efficiency** — fractional-flow and Welge tangent
   analysis from relative-permeability curves, comparing waterflood vs.
   polymer flood.
2. **Dykstra-Parsons** — vertical permeability-heterogeneity coefficient
   from well-log data, for any number of reservoir intervals.
3. **Target Polymer Viscosity** — required polymer-solution viscosity
   for a target mobility ratio, with an optional heterogeneity
   (Kmax/Kmin) adjustment.

Results calculated in one module (relative-permeability curves,
Dykstra-Parsons Kmax/Kmin) are automatically carried over to the other
modules via Streamlit's session state.

---

## 🚀 Quick start (local)

```bash
git clone https://github.com/<your-username>/<your-repo>.git
cd <your-repo>

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt

streamlit run app.py
```

The app opens at `http://localhost:8501`.

---

## ☁️ Deploy to Streamlit Community Cloud

1. Push this repository to **GitHub** (public or private).
2. Go to **[share.streamlit.io](https://share.streamlit.io)** and sign
   in with your GitHub account.
3. Click **"New app"**.
4. Select:
   - **Repository**: `<your-username>/<your-repo>`
   - **Branch**: `main`
   - **Main file path**: `app.py`
5. Click **Deploy**.

Streamlit Cloud automatically installs everything listed in
`requirements.txt` and reruns the app on every push to the selected
branch.

---

## 📁 Repository structure

```text
polymer_flood_app/
│
├── app.py                                 # Home page
├── requirements.txt
├── README.md
│
├── .streamlit/
│   └── config.toml                        # Theme & server settings
│
├── pages/
│   ├── 1_Displacement_Efficiency.py
│   ├── 2_Dykstra_Parsons.py
│   └── 3_Target_Polymer_Viscosity.py
│
├── utils/
│   ├── fractional_flow.py                 # Welge / fractional-flow engine
│   ├── dykstra_parsons.py                 # V_DP engine
│   └── polymer_viscosity.py               # Mobility-ratio viscosity engine
│
└── sample_data/
    ├── relative_permeability_template.xlsx
    └── permeability_log_template.xlsx
```

---

## 📄 Expected file formats

### Relative-permeability file (Module 1)

| Sw | Krw | Kro |
|----|-----|-----|
| 0.20 | 0.000 | 0.850 |
| 0.25 | 0.010 | 0.670 |
| ... | ... | ... |

A ready-to-use template is provided at
`sample_data/relative_permeability_template.xlsx`.

### Permeability log file (Module 2)

| DEPTH | PERM |
|-------|------|
| 2000.0 | 210.4 |
| 2000.5 | -999.25 |
| ... | ... |

Column names can be anything — you map them to *Depth* and
*Permeability* directly in the app. Null values (default: `-999.25`,
`-999`, `-9999`, `-9999.25`) are automatically removed; you can add or
edit this list in the app.

A ready-to-use template is provided at
`sample_data/permeability_log_template.xlsx`.

---

## 🧮 Engineering methods used

### Displacement efficiency (Welge / Buckley-Leverett)

- 1-D, horizontal, incompressible, immiscible flow; gravity and
  capillary pressure neglected.
- Fractional flow: `Fw = (Krw/µw) / (Krw/µw + Kro/µo)`
- The Welge shock-front saturation `Swf` is found by **maximizing the
  secant slope** `Fw(Sw)/(Sw - Swirr)` — this is mathematically
  equivalent to, and more numerically robust than, solving
  `dFw/dSw = Fw/(Sw - Swirr)` directly.
- The tangent is extended to `Fw = 1` to obtain the average water
  saturation behind the front, `Sw_avg`.
- Displacement efficiency: `Ed = (Sw_avg - Swirr) / (1 - Swirr)`
  (optionally also expressed on a movable-oil basis if `Sor` is given).

### Dykstra-Parsons coefficient

- `V_DP = (k50 - k84.1) / k50`, where `k50` and `k84.1` are read from
  the thickness-weighted, log-probability distribution of permeability
  samples within each reservoir interval.

### Target polymer viscosity

- Mobility-ratio viscosity: `µp = (Krw · µo) / (M_target · Kro)`
- Optional heterogeneity-adjusted screening target:
  `µ_target = µp × (Kmax / Kmin)`
  > This multiplier is an empirical screening heuristic, not part of
  > the classical mobility-ratio equation, and is reported separately
  > with a warning in the app.

---

## ⚠️ Disclaimer

This tool is intended for **preliminary screening** purposes only.
Results should be validated against detailed reservoir simulation,
core/SCAL data quality checks, and company-specific EOR screening
guidelines before being used for investment decisions.
