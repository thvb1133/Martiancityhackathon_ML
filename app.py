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
from marswater.globe import settlement_plan, water_globe
from marswater.physics import settlement_demand
from marswater.pipeline import run_pipeline
from marswater.section import (
    buildability_globe,
    depth_profile_figure,
    ground_property_table,
    habitat_section,
)
from marswater.simulate import (
    SettlementConfig,
    dust_storm_resilience,
    minimum_fission_units,
    mission_architecture_comparison,
    population_sweep,
    rank_sites,
    size_infrastructure,
)
from marswater.subsurface import (
    BurialConfig,
    architecture_table,
    buildability_field,
    construction_energy_in_context,
    decision_audit,
    depth_profile,
    design_habitat,
)

MARS_COLOURS = ["#2b1a14", "#7a2f1a", "#c4562a", "#e08a4a", "#8fd3e0", "#d6f2f7"]

DOME_VOLUME_NOTE = (
    "Sized from 60 m³ of pressurised volume per person in 12 m hemispheres."
)

st.set_page_config(
    page_title="MARSWATER -- Mars settlement siting",
    page_icon="🔴",
    layout="wide",
)


@st.cache_resource(show_spinner="Training the water-yield model ...")
def load_pipeline(seed: int):
    return run_pipeline(random_state=seed, include_grid=True)


@st.cache_data(show_spinner="Designing the underground habitat ...")
def load_architecture(
    seed: int,
    population: int,
    dose_limit: float,
    swing_tolerance: float,
    internal_pressure: float,
):
    """Size the habitat at every site, and audit the decision behind it.

    Cached on the values that change the answer rather than on the config
    object, so that moving an unrelated slider on the settlement side of the
    dashboard does not re-run the whole depth sweep.
    """
    result = load_pipeline(seed)
    config = BurialConfig(
        dose_limit_msv_per_year=dose_limit,
        temperature_swing_tolerance_k=swing_tolerance,
        internal_pressure_kpa=internal_pressure,
    )
    return (
        config,
        architecture_table(result.named_sites, population, config),
        decision_audit(result.named_sites, population, config),
        buildability_field(result.grid),
    )


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
st.sidebar.subheader("Habitat design limits")
st.sidebar.caption(
    "These three numbers decide how deep the settlement has to dig, and "
    "between them they decide what kind of building it gets."
)
dose_limit = st.sidebar.slider(
    "Crew radiation limit (mSv/yr)", 5, 200, int(C.DOSE_LIMIT_MSV_PER_YEAR), step=5,
    help="The Martian surface delivers about 230 mSv/yr. Terrestrial "
         "background is 2.4 and a NASA career limit is of order 600. A place "
         "people live should be nearer the former.",
)
swing_tolerance = st.sidebar.slider(
    "Ground temperature swing tolerance (K)", 0.5, 10.0, 2.0, step=0.5,
    help="How still the surrounding rock has to be. Mars swings about 90 K "
         "over a sol and tens of kelvin over a year; burial is what removes "
         "both.",
)
internal_pressure = st.sidebar.slider(
    "Habitat pressure (kPa)", 30, 101, int(C.HABITAT_PRESSURE_KPA), step=1,
    help="Sets the depth at which the weight of the overburden cancels the "
         "cabin pressure, and the shell stops needing to be a pressure vessel.",
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
# Underground architecture
# ---------------------------------------------------------------------------
st.header("Underground architecture")
st.markdown(
    "**The surface of Mars is the worst place on the planet to put a house.** "
    "It takes 230 mSv a year, swings 90 K between afternoon and dawn, and "
    "offers nothing to hold a pressure vessel down. All three problems are "
    "solved a few metres below it, by the material already there.\n\n"
    "So the architectural question is not what shape the dome is. It is *how "
    "deep* — and that is a decision the water model already knows how to make, "
    "because pore ice is what separates loose regolith from rock. Dry ground "
    "cannot hold an unsupported roof, so the vault has to be trenched and its "
    "pressure shell flown from Earth. Ice-cemented ground will hold a mined "
    "vault open, and below the depth where its own weight cancels the cabin "
    "pressure the shell stops being a pressure vessel at all."
)

burial_config, architecture, audit, buildable = load_architecture(
    int(seed), population, float(dose_limit), float(swing_tolerance),
    float(internal_pressure),
)
viable_architecture = architecture[architecture["feasible"]]

site_options = list(architecture["site"])
default_site = best["name"] if best is not None else site_options[0]
chosen_site = st.selectbox(
    "Site to design for",
    site_options,
    index=site_options.index(default_site) if default_site in site_options else 0,
    help="Defaults to the site the settlement simulation recommends, so the "
         "two halves of the project are looking at the same place.",
)

chosen_row = result.named_sites[result.named_sites["name"] == chosen_site].iloc[0]
design = design_habitat(chosen_row, population, burial_config)

arch_cols = st.columns(5)
arch_cols[0].metric(
    "Construction method",
    design.method.replace("mined vault in ice-cemented ground", "mined vault")
    .replace("surface vault under a regolith berm", "regolith berm")
    .replace("cut-and-cover buried vault", "cut-and-cover")
    .replace("mined vault with sintered regolith support", "mined, sintered"),
    help=design.limiting_factor,
)
arch_cols[1].metric(
    "Crown depth", f"{design.depth_m:.2f} m",
    help="Depth to the top of the vault, below original grade.",
)
arch_cols[2].metric(
    "Pressure shell", f"{design.shell_thickness_mm:.2f} mm",
    help=f"Sized on a net {design.net_pressure_kpa:.1f} kPa. Overburden at "
         f"this depth is {design.overburden_kpa:.1f} kPa against "
         f"{internal_pressure} kPa of cabin pressure.",
)
arch_cols[3].metric(
    "Landed mass", f"{design.landed_mass_kg / 1000:.1f} t",
    help=f"{design.vaults} vault(s) for {population:,} crew, including shell, "
         "liner, insulation and the excavation fleet.",
)
arch_cols[4].metric(
    "Not flown as shielding",
    f"{design.mass_saved_vs_imported_shielding_kg / 1000:,.0f} t",
    delta=f"{design.imported_shielding_equivalent_kg / C.STARSHIP_PAYLOAD_KG:.0f}"
          " Starships avoided",
    help="Matching the same dose limit with material brought from Earth means "
         "flying the same areal density. Digging is the difference between "
         "that and nothing.",
)

section_tab, why_tab, map_tab, rank_tab = st.tabs(
    ["Section (3D)", "Why that depth", "Where you can mine (3D)", "Every site"]
)

with section_tab:
    section_figure, dimensions = habitat_section(design)
    st.plotly_chart(section_figure, use_container_width=True)
    st.caption(
        "A cut-away section, to scale in metres, generated from the sizing "
        "result rather than drawn. The cut face is coloured by radiation dose: "
        "the bright band in the first half-metre is the secondary neutron "
        "shower the shielding itself produces, which is why thin cover is "
        "close to worthless. The cone behind the block is the spoil — its "
        f"volume is the {dimensions['spoil_volume_m3']:,.0f} m³ this method "
        "actually has to move per vault, which is why a trench costs more than "
        "a mine even when the building is identical."
    )
    energy_context = construction_energy_in_context(
        design,
        infra.energy_demand_kwh_per_sol if infra is not None else 1.0,
    )
    section_cols = st.columns(4)
    section_cols[0].metric(
        "Excavated", f"{design.excavated_m3:,.0f} m³",
        help=f"{design.excavated_mass_kg / 1e6:,.1f} kilotonnes of regolith, "
             f"moved by {design.excavator_units} machines inside one launch "
             "window.",
    )
    section_cols[1].metric(
        "Construction energy",
        f"{design.construction_energy_kwh / 1000:,.0f} MWh",
        help="Drawn from the same surface power system that runs the water "
             "plant, because a settlement has only one grid.",
    )
    section_cols[2].metric(
        "Sols of total settlement power",
        f"{energy_context['sols_of_total_settlement_power']:,.0f}",
        help="Digging is not free just because the regolith is.",
    )
    section_cols[3].metric(
        "Insulation", f"{design.insulation_thickness_m * 100:.1f} cm",
        help="Zero in dry regolith, which insulates itself. In ice-cemented "
             "ground the rock face behind the liner has to stay below 263 K or "
             "the habitat thaws the cement it is standing in.",
    )

with why_tab:
    st.plotly_chart(
        depth_profile_figure(
            depth_profile(chosen_row, population, burial_config),
            design,
            config_dose_limit=float(dose_limit),
            config_swing_tolerance=float(swing_tolerance),
        ),
        use_container_width=True,
    )
    st.caption(
        "Four curves, pulling in different directions. Radiation says go down, "
        "and says the first third of a metre is wasted. The seasons say go "
        "further down than you would expect if the ground is icy, because pore "
        "ice conducts the annual temperature wave metres deeper than dry sand "
        "does. The structure says there is a depth at which the pressure shell "
        "stops being necessary. And the cost says only one of the four methods "
        "can reach it. The star is the design above."
    )
    st.dataframe(
        ground_property_table().round(2), hide_index=True,
        use_container_width=True,
    )
    st.caption(
        "The two Martian ground materials, and why one predicted number "
        "decides the building. Between 2 and 20 wt% water, cohesion rises by a "
        "factor of three hundred and the ground goes from unmineable to "
        "effectively unlimited."
    )

with map_tab:
    st.plotly_chart(
        buildability_globe(buildable, ranked),
        use_container_width=True,
    )
    mineable_cells = int(buildable["can_mine_to_self_anchoring"].sum())
    st.caption(
        "The water prediction wearing a different hat: how deep the ground at "
        "each cell could be mined without support. Pale ground is where a city "
        "can be excavated and lined; dark red is where habitats have to be "
        f"trenched and their shells flown from Earth. {mineable_cells:,} of "
        f"{len(buildable):,} grid cells can be mined past the depth where "
        "overburden cancels cabin pressure. Note that the boundary is not a "
        "line of latitude — it follows the mantling deposit, which is exactly "
        "the part a latitude rule of thumb gets wrong."
    )

with rank_tab:
    st.dataframe(
        architecture[[
            "rank", "site", "latitude_deg", "water_grade_wt_pct", "method",
            "depth_m", "shell_mm", "insulation_cm", "landed_mass_t",
            "construction_energy_mwh", "feasible",
        ]].round({
            "latitude_deg": 1, "water_grade_wt_pct": 1, "depth_m": 2,
            "shell_mm": 2, "insulation_cm": 1, "landed_mass_t": 1,
            "construction_energy_mwh": 0,
        }).rename(columns={
            "rank": "#", "latitude_deg": "lat", "water_grade_wt_pct": "water wt%",
            "depth_m": "depth m", "shell_mm": "shell mm",
            "insulation_cm": "insul cm", "landed_mass_t": "mass t",
            "construction_energy_mwh": "dig MWh", "feasible": "buildable",
        }),
        hide_index=True, use_container_width=True, height=420,
    )
    if len(viable_architecture):
        cheapest = viable_architecture.iloc[0]
        st.caption(
            f"Cheapest habitat on the shortlist is **{cheapest['site']}** at "
            f"{cheapest['landed_mass_t']:.0f} t, built as a "
            f"{cheapest['method']}. The settlement simulation above picks its "
            "site on water and power alone and arrives at the same part of the "
            "planet, which is worth noticing: two independent physical "
            "arguments agreeing is not a weighting choice."
        )

st.subheader("Was the model worth having?")
st.caption(
    "Every site is designed five times, from five different beliefs about how "
    "much water is in the ground, and each design is then re-costed against "
    "the ground as it really is. A design that still meets its requirements is "
    "charged the difference against perfect foresight; one that does not is "
    "charged everything it landed, because that hardware has flown, failed, "
    "and the correct habitat still has to follow it. Note which way the errors "
    "go: under-predicting water keeps the roof safe but builds too shallow for "
    "the seasons, because dry ground is assumed to insulate better than it "
    "does. There is no safe direction to be wrong in."
)
st.dataframe(audit, hide_index=True, use_container_width=True)

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
globe_tab, flat_tab = st.tabs(["Globe (3D)", "Flat map"])

with globe_tab:
    exaggeration = st.slider(
        "Topographic exaggeration", 0, 80, 30, step=5,
        help="Mars' full relief is about 30 km against a 3,390 km radius, so "
             "true-scale topography is invisible on a globe. Set this to zero "
             "for a perfect sphere.",
    )
    st.plotly_chart(
        water_globe(grid, ranked, elevation_exaggeration=float(exaggeration)),
        use_container_width=True,
    )
    st.caption(
        "Rotate and zoom with the mouse. Colour is the model's predicted water "
        "content, draped over Mars' topography; the pale bands either side of "
        "the equator are the mantling deposits the regressor learned to find. "
        "Pins are candidate sites — green is viable at the current crew size, "
        "red is not."
    )

with flat_tab:
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
    ]].round({
        "latitude_deg": 1, "water_grade_wt_pct": 1, "regolith_t_per_sol": 1,
        "pv_area_km2": 3, "landed_mass_t": 0,
    }).rename(columns={
        "rank": "#", "name": "site", "latitude_deg": "lat",
        "water_grade_wt_pct": "water wt%", "regolith_t_per_sol": "rock t/sol",
        "pv_area_km2": "array km2", "landed_mass_t": "mass t",
        "max_population": "ceiling", "feasible": "viable",
        "limiting_factor": "binding constraint",
    })
    st.dataframe(display, hide_index=True, use_container_width=True, height=420)

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
# Settlement plan, generated from the sizing result
# ---------------------------------------------------------------------------
if infra is not None:
    st.subheader("The settlement this implies, to scale")
    st.caption(
        "Not a concept drawing. Every dimension below is computed from the "
        "sizing result for this site and crew size, so moving the population "
        "slider rebuilds the base."
    )
    plan_figure, derived = settlement_plan(infra, best["name"])
    st.plotly_chart(plan_figure, use_container_width=True)

    plan_cols = st.columns(4)
    plan_cols[0].metric(
        "Solar farm", f"{derived['array_side_m']:,.0f} m square",
        help=f"{derived['array_area_m2']:,.0f} m² of collector, drawn as "
             f"{derived['panel_rows_drawn']:.0f} tilted rows.",
    )
    plan_cols[1].metric(
        "Habitat domes", f"{derived['domes_needed']:,.0f}",
        help=f"{DOME_VOLUME_NOTE} That is about "
             f"{derived['crew_per_dome']:.0f} crew per dome."
             + ("" if derived["domes_needed"] <= derived["domes_drawn"]
                else f" Showing {derived['domes_drawn']:.0f} for clarity."),
    )
    plan_cols[2].metric(
        "Open-pit mine", f"{derived['pit_radius_m']:,.0f} m radius",
        help=f"{derived['regolith_m3_per_sol']:,.0f} m³ of regolith per sol, "
             f"or {derived['excavated_m3_per_synod']:,.0f} m³ excavated over one "
             "launch window at 1,600 kg/m³ bulk density.",
    )
    plan_cols[3].metric(
        "Excavators", f"{infra.excavator_units}",
        help=f"Each unit moves {C.EXCAVATOR_UNIT_THROUGHPUT_KG_PER_SOL / 1000:,.0f}"
             f" t of rock per sol. Fleet limit is {config.max_excavator_fleet}.",
    )
    st.caption(
        "The mine is the part that scales with the model's prediction: richer "
        "ground means a smaller pit and fewer excavators for the same litres "
        "of water, because less rock has to be heated to release it."
    )

    st.divider()

# ---------------------------------------------------------------------------
# The two arguments that make the model load bearing
# ---------------------------------------------------------------------------
st.subheader("Does the water prediction actually change the decision?")
st.caption(
    "Hold every other assumption fixed and change only whether the settlement "
    "intends to send people home. A one-way outpost recycles nearly all its "
    "water, so even a dry site stays competitive. A settlement with a return "
    "vehicle has to electrolyse hundreds of tonnes of mined water per "
    "departure: landed mass roughly doubles, the dry sites fall out of "
    "contention, and past a few hundred people half the shortlist stops "
    "qualifying at all."
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
