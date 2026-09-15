"""MARSWATER dashboard: ``streamlit run app.py``.

A mission-planning console. The left panel sets the campaign assumptions, the
map shows the model's predicted water field, and the panels below show what
each candidate site costs to settle and where it stops working.
"""

from __future__ import annotations

from dataclasses import replace

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from marswater import constants as C
from marswater.physics import settlement_demand
from marswater.pipeline import run_pipeline
from marswater.simulate import (
    SettlementConfig,
    dust_storm_resilience,
    minimum_fission_units,
    mission_architecture_comparison,
    population_sweep,
    rank_sites,
    size_infrastructure,
)

MARS_COLOURS = ["#2b1a14", "#7a2f1a", "#c4562a", "#e08a4a", "#8fd3e0", "#d6f2f7"]

st.set_page_config(
    page_title="MARSWATER -- Mars settlement siting",
    page_icon="🔴",
    layout="wide",
)


@st.cache_resource(show_spinner="Training the water-yield model ...")
def load_pipeline(seed: int):
    return run_pipeline(random_state=seed, include_grid=True)


# ---------------------------------------------------------------------------
# Controls
# ---------------------------------------------------------------------------
st.sidebar.title("Mission parameters")
st.sidebar.caption(
    "Every value below feeds a physical calculation, not a fitted weight."
)

population = st.sidebar.slider(
    "Settlement population", min_value=10, max_value=4000, value=100, step=10,
    help="Crew size the infrastructure must support.",
)
fission_units = st.sidebar.slider(
    "Fission surface power units (10 kWe each)", 0, 60, 4,
    help="Reactors run through the night and through dust storms; "
         "photovoltaics make up the rest of the load.",
)
dust_choice = st.sidebar.select_slider(
    "Atmospheric dust optical depth",
    options=["clear (0.35)", "regional storm (1.5)", "global storm (4.5)"],
    value="clear (0.35)",
)
include_propellant = st.sidebar.checkbox(
    "Produce return propellant from ice", value=True,
    help="Methalox for departing vehicles. This is the single biggest water "
         "demand a settlement has -- far larger than what the crew drinks.",
)
crew_per_flight = st.sidebar.slider(
    "Crew per return flight", 10, 200, 50, step=10,
    disabled=not include_propellant,
    help="Sets how many vehicles must be fuelled each launch window.",
)
loop_closure = st.sidebar.slider(
    "ECLSS water loop closure", 0.70, 0.99, C.WATER_LOOP_CLOSURE, step=0.01,
    help="Fraction of crew water recycled. The ISS achieves about 0.93.",
)
seed = st.sidebar.number_input("Random seed", 0, 999, 0, step=1)

tau = {"clear (0.35)": C.TAU_CLEAR,
       "regional storm (1.5)": C.TAU_REGIONAL_STORM,
       "global storm (4.5)": C.TAU_GLOBAL_STORM}[dust_choice]

config = SettlementConfig(
    fission_units=fission_units,
    optical_depth=tau,
    water_loop_closure=loop_closure,
    crew_per_return_flight=float(crew_per_flight),
    include_propellant=include_propellant,
)

result = load_pipeline(int(seed))
ranked = rank_sites(result.named_sites, config, population)
viable = ranked[ranked["feasible"]]

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("MARSWATER")
st.markdown(
    "**Where should the first Martian city be built, and how big can it get?** "
    "One machine-learning model predicts subsurface water from orbital "
    "observables. Everything after that is physics: insolation, extraction "
    "energy, closed-loop life support, and the mass that has to be flown from "
    "Earth."
)

if len(viable):
    best = viable.iloc[0]
    best_row = result.named_sites[
        result.named_sites["name"] == best["name"]
    ].iloc[0]
    infra = size_infrastructure(best_row, population, config)

    cols = st.columns(5)
    cols[0].metric("Recommended site", best["name"])
    cols[1].metric("Water in ground", f"{best['water_grade_wt_pct']:.1f} wt%",
                   help="Conservative lower bound of the model's prediction.")
    cols[2].metric("Landed mass", f"{best['landed_mass_t']:.0f} t",
                   help="Power and mining hardware only; crew systems cost the "
                        "same everywhere.")
    cols[3].metric("Starship loads", f"{best['launches']:.1f}")
    cols[4].metric("Population ceiling", f"{int(best['max_population']):,}",
                   help=best["capacity_limit"])
else:
    best = best_row = infra = None
    st.error(
        f"**No shortlisted site supports {population:,} people** with "
        f"{fission_units} reactors under these assumptions. "
        "The panels below show what is binding and what would reopen a site."
    )

st.divider()

# ---------------------------------------------------------------------------
# Map
# ---------------------------------------------------------------------------
st.subheader("Predicted water-equivalent hydrogen")
st.caption(
    "Model output across a global grid of cells it was never trained on. "
    "Candidate sites are overlaid; hover for the prediction and the cost."
)

grid = result.grid
fig = go.Figure()
fig.add_trace(
    go.Scattergl(
        x=grid["longitude_deg"], y=grid["latitude_deg"],
        mode="markers",
        marker=dict(
            size=9, symbol="square",
            color=grid["predicted_weh_wt_pct"],
            colorscale=[[i / (len(MARS_COLOURS) - 1), c]
                        for i, c in enumerate(MARS_COLOURS)],
            colorbar=dict(title="wt% H2O"), cmin=0, cmax=30,
        ),
        hovertemplate=(
            "%{y:.0f}N %{x:.0f}E<br>predicted %{marker.color:.1f} wt%<extra></extra>"
        ),
        name="model prediction",
    )
)
site_labels = ranked.merge(
    result.named_sites[["name", "note"]], on="name", how="left"
)
fig.add_trace(
    go.Scattergl(
        x=site_labels["longitude_deg"], y=site_labels["latitude_deg"],
        mode="markers+text",
        marker=dict(
            size=14,
            color=["#39ff88" if f else "#ff4b4b" for f in site_labels["feasible"]],
            line=dict(color="white", width=1.5), symbol="diamond",
        ),
        text=site_labels["name"], textposition="top center",
        textfont=dict(size=9, color="white"),
        customdata=site_labels[
            ["water_grade_wt_pct", "landed_mass_t", "limiting_factor", "note"]
        ],
        hovertemplate=(
            "<b>%{text}</b><br>%{customdata[3]}<br>"
            "water %{customdata[0]:.1f} wt%<br>"
            "landed mass %{customdata[1]:.0f} t<br>"
            "%{customdata[2]}<extra></extra>"
        ),
        name="candidate sites",
    )
)
fig.update_layout(
    height=520, template="plotly_dark",
    xaxis=dict(title="longitude (deg E)", range=[-180, 180]),
    yaxis=dict(title="latitude (deg N)", range=[-75, 75]),
    margin=dict(l=0, r=0, t=10, b=0), showlegend=False,
)
st.plotly_chart(fig, use_container_width=True)
st.caption(
    "Green diamonds are viable at the current population; red are not. "
    "The wet mid-latitude bands are the mantling deposits the model learned to "
    "find; the equatorial belt is dry."
)

st.divider()

# ---------------------------------------------------------------------------
# Ranking and cost breakdown
# ---------------------------------------------------------------------------
left, right = st.columns([3, 2])

with left:
    st.subheader(f"Site ranking for {population:,} people")
    st.caption(
        "Ordered by the landed mass each site needs, which is a physical cost "
        "rather than a weighted score."
    )
    display = ranked[[
        "rank", "name", "latitude_deg", "water_grade_wt_pct",
        "regolith_t_per_sol", "pv_area_km2", "landed_mass_t",
        "max_population", "feasible", "limiting_factor",
    ]].rename(columns={
        "rank": "#", "name": "site", "latitude_deg": "lat",
        "water_grade_wt_pct": "water wt%", "regolith_t_per_sol": "rock t/sol",
        "pv_area_km2": "array km2", "landed_mass_t": "mass t",
        "max_population": "ceiling", "feasible": "viable",
        "limiting_factor": "binding constraint",
    })
    st.dataframe(
        display.style.format({
            "lat": "{:.1f}", "water wt%": "{:.1f}", "rock t/sol": "{:.1f}",
            "array km2": "{:.3f}", "mass t": "{:.0f}", "ceiling": "{:,.0f}",
        }),
        hide_index=True, use_container_width=True, height=420,
    )

with right:
    if infra is not None:
        st.subheader("What you have to fly there")
        mass = pd.DataFrame(
            {"component": list(infra.mass_breakdown_kg),
             "tonnes": [v / 1000 for v in infra.mass_breakdown_kg.values()]}
        )
        st.plotly_chart(
            px.bar(mass, x="tonnes", y="component", orientation="h",
                   template="plotly_dark", color="component",
                   color_discrete_sequence=px.colors.sequential.Oranges_r)
            .update_layout(height=230, showlegend=False,
                           margin=dict(l=0, r=0, t=10, b=0),
                           yaxis_title=None),
            use_container_width=True,
        )

        st.subheader("Where the power goes")
        demand = settlement_demand(
            population, water_loop_closure=loop_closure,
            ore_grade_wt_pct=float(best["water_grade_wt_pct"]),
            crew_per_return_flight=float(crew_per_flight),
            include_propellant=include_propellant,
        )
        energy = pd.DataFrame(
            {"load": list(demand.energy_breakdown_kwh),
             "MWh/sol": [v / 1000 for v in demand.energy_breakdown_kwh.values()]}
        )
        st.plotly_chart(
            px.bar(energy, x="MWh/sol", y="load", orientation="h",
                   template="plotly_dark", color="load",
                   color_discrete_sequence=px.colors.sequential.Teal_r)
            .update_layout(height=250, showlegend=False,
                           margin=dict(l=0, r=0, t=10, b=0),
                           yaxis_title=None),
            use_container_width=True,
        )

st.divider()

# ---------------------------------------------------------------------------
# The two arguments that make the model load bearing
# ---------------------------------------------------------------------------
st.subheader("Does the water prediction actually change the decision?")
st.caption(
    "Hold every other assumption fixed and change only whether the settlement "
    "intends to send people home. A one-way outpost recycles nearly all its "
    "water and is sited on sunlight. A settlement with a return vehicle has to "
    "electrolyse hundreds of tonnes of mined water per departure, so it is "
    "sited on ice -- and half the shortlist stops qualifying."
)
st.dataframe(
    mission_architecture_comparison(result.named_sites, config, population),
    hide_index=True, use_container_width=True,
)

st.subheader("Where it breaks as the city grows")
sweep = population_sweep(
    result.named_sites, config,
    populations=(20, 100, 300, 1000, 2000, 4000),
)
sweep_fig = px.line(
    sweep, x="population", y="sites_viable", markers=True,
    template="plotly_dark", labels={"sites_viable": "viable sites"},
)
sweep_fig.update_traces(line_color="#e08a4a")
sweep_fig.update_layout(height=260, margin=dict(l=0, r=0, t=10, b=0))
st.plotly_chart(sweep_fig, use_container_width=True)
st.dataframe(sweep, hide_index=True, use_container_width=True)

stalled = sweep[sweep["sites_viable"] == 0]
if len(stalled) and best_row is not None:
    failure_population = int(stalled.iloc[0]["population"])
    needed = minimum_fission_units(best_row, failure_population, config)
    if needed is None:
        st.warning(
            f"At {failure_population:,} people no shortlisted site works, and "
            "more power will not fix it: the binding limit is rock throughput. "
            "The settlement needs a larger mining fleet or a richer deposit."
        )
    else:
        st.info(
            f"At {failure_population:,} people no shortlisted site works on "
            f"{fission_units} reactors. **{best['name']} reopens at {needed} "
            f"units ({needed * 10:,} kWe of surface power.)**"
        )

if best_row is not None:
    st.subheader(f"Dust-storm resilience at {best['name']}")
    st.caption(
        "The 2018 planet-encircling storm ended the Opportunity mission. A "
        "solar settlement plan has to state what happens during one."
    )
    st.dataframe(
        dust_storm_resilience(best_row, config, population),
        hide_index=True, use_container_width=True,
    )

st.divider()

# ---------------------------------------------------------------------------
# Model validation
# ---------------------------------------------------------------------------
with st.expander("Model validation -- how good is the water prediction?"):
    report = result.report
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Held-out R2", f"{report.test_r2:.3f}")
    c2.metric("Mean abs. error", f"{report.test_mae:.2f} wt%")
    c3.metric("Ridge baseline R2", f"{report.ridge_test_r2:.3f}",
              delta=f"{report.test_r2 - report.ridge_test_r2:+.3f}")
    c4.metric("Mean baseline R2", f"{report.mean_baseline_test_r2:.3f}")
    st.caption(
        f"Gradient boosting on {report.n_train:,} survey cells, scored on "
        f"{report.n_test:,} held out. Five-fold cross-validated R2 "
        f"{report.cv_r2_mean:.3f} +/- {report.cv_r2_std:.3f}. The gap over "
        "ridge regression is the thresholded interaction between latitude and "
        "geology, which a linear model cannot represent. Sizing uses the "
        f"prediction minus one residual sigma ({report.residual_std:.2f} wt%), "
        "because a water plant built on the mean forecast fails half the time "
        "the forecast is wrong."
    )
    importance = pd.DataFrame(
        {"feature": list(report.feature_importance),
         "importance": list(report.feature_importance.values())}
    )
    st.plotly_chart(
        px.bar(importance, x="importance", y="feature", orientation="h",
               template="plotly_dark",
               labels={"importance": "drop in R2 when shuffled"})
        .update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0),
                       yaxis=dict(autorange="reversed"), yaxis_title=None),
        use_container_width=True,
    )

    st.markdown(
        "**Provenance.** Named sites use their real published coordinates and "
        "MOLA elevations. The orbital survey the model trains on is a "
        "physically motivated surrogate for the NASA Planetary Data System "
        "archive -- multi-gigabyte neutron-spectrometer, thermal-inertia and "
        "radar products that cannot be georeferenced in an evening. The "
        "surrogate encodes published ground-ice stability results; it is a "
        "stand-in for measured data and is not presented as measured data. "
        "Every physical constant is sourced in `marswater/constants.py`."
    )
