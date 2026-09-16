"""Render the dashboard to a static site: ``python export_static.py``.

Streamlit needs a live Python process and a websocket, which a static host
cannot give it. Everything the dashboard shows, though, is a Plotly figure or
a table computed from one seed and one set of assumptions, so a fixed slice of
it exports cleanly to a single self-contained page.

The result is ``site/index.html``: the same 3D section, depth profile,
buildability globe, water globe and settlement plan, at the default mission
parameters, with the sliders replaced by pre-rendered alternatives the reader
can tab between. Deploy the ``site`` directory to any static host.
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

from marswater import constants as C
from marswater.globe import settlement_plan, water_globe
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
    population_sweep,
    rank_sites,
    size_infrastructure,
)
from marswater.subsurface import (
    BurialConfig,
    architecture_table,
    decision_audit,
    depth_profile,
    design_habitat,
    buildability_field,
)

POPULATION = 100
SEED = 0

STYLE = """
:root {
  --bg: #0b0708; --panel: #140d0e; --line: #2f2022;
  --ink: #f4e7e1; --dim: #b08f85; --hot: #e08a4a; --cool: #8fd3e0;
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--ink);
  font: 16px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}
main { max-width: 1180px; margin: 0 auto; padding: 0 24px 96px; }
header { padding: 72px 0 32px; border-bottom: 1px solid var(--line); }
h1 { font-size: 56px; letter-spacing: 0.16em; margin: 0 0 8px; color: var(--hot); }
h2 { font-size: 30px; margin: 64px 0 8px; }
h3 { font-size: 20px; margin: 36px 0 8px; color: var(--cool); }
p { color: var(--ink); max-width: 78ch; }
p.note { color: var(--dim); font-size: 14px; max-width: 86ch; }
.lede { font-size: 19px; color: var(--dim); max-width: 78ch; }
.tiles { display: flex; flex-wrap: wrap; gap: 12px; margin: 24px 0; }
.tile {
  flex: 1 1 170px; background: var(--panel); border: 1px solid var(--line);
  border-radius: 10px; padding: 14px 16px;
}
.tile .k { font-size: 12px; text-transform: uppercase; letter-spacing: 0.08em;
           color: var(--dim); }
.tile .v { font-size: 26px; font-weight: 600; margin-top: 4px; }
.tile .s { font-size: 12px; color: var(--dim); margin-top: 2px; }
.figure { background: var(--panel); border: 1px solid var(--line);
          border-radius: 10px; margin: 16px 0; overflow: hidden; }
.tabs { display: flex; flex-wrap: wrap; gap: 8px; margin: 24px 0 0; }
.tabs button {
  background: var(--panel); color: var(--dim); border: 1px solid var(--line);
  border-radius: 999px; padding: 8px 18px; font-size: 14px; cursor: pointer;
}
.tabs button.on { color: var(--bg); background: var(--hot); border-color: var(--hot); }
.panel { display: none; }
.panel.on { display: block; }
table { border-collapse: collapse; width: 100%; font-size: 13px; margin: 12px 0; }
th, td { border-bottom: 1px solid var(--line); padding: 7px 10px; text-align: right; }
th { color: var(--dim); font-weight: 600; text-transform: uppercase;
     font-size: 11px; letter-spacing: 0.06em; }
td:first-child, th:first-child { text-align: left; }
tbody tr:hover { background: #1c1214; }
footer { border-top: 1px solid var(--line); margin-top: 72px; padding-top: 24px;
         color: var(--dim); font-size: 14px; }
a { color: var(--hot); }
code { background: var(--panel); padding: 2px 6px; border-radius: 4px;
       font-size: 13px; }
"""

SCRIPT = """
document.querySelectorAll('.tabs').forEach(function (bar) {
  var group = bar.dataset.group;
  bar.querySelectorAll('button').forEach(function (button) {
    button.addEventListener('click', function () {
      bar.querySelectorAll('button').forEach(function (b) {
        b.classList.remove('on');
      });
      button.classList.add('on');
      document.querySelectorAll('.panel[data-group="' + group + '"]')
        .forEach(function (panel) {
          panel.classList.toggle('on', panel.dataset.key === button.dataset.key);
          if (panel.classList.contains('on')) {
            panel.querySelectorAll('.js-plotly-plot').forEach(function (plot) {
              window.Plotly.Plots.resize(plot);
            });
          }
        });
    });
  });
});
"""


def _figure_html(figure: go.Figure, first: bool, height: int = 620) -> str:
    """Emit one figure, loading plotly.js from the CDN exactly once."""
    figure.update_layout(
        height=height,
        paper_bgcolor="#140d0e",
        plot_bgcolor="#140d0e",
        font=dict(color="#f4e7e1"),
    )
    return figure.to_html(
        full_html=False,
        include_plotlyjs="cdn" if first else False,
        config={"displaylogo": False, "responsive": True},
    )


def _table_html(frame: pd.DataFrame) -> str:
    return frame.to_html(index=False, border=0, justify="left", escape=False)


def _tile(key: str, value: str, sub: str = "") -> str:
    sub_html = f'<div class="s">{sub}</div>' if sub else ""
    return (
        f'<div class="tile"><div class="k">{key}</div>'
        f'<div class="v">{value}</div>{sub_html}</div>'
    )


def _tabs(group: str, panels: list[tuple[str, str, str]]) -> str:
    """``panels`` is a list of (key, label, inner html); the first is open."""
    buttons = "".join(
        f'<button data-key="{key}" class="{"on" if i == 0 else ""}">{label}</button>'
        for i, (key, label, _) in enumerate(panels)
    )
    bodies = "".join(
        f'<div class="panel {"on" if i == 0 else ""}" data-group="{group}" '
        f'data-key="{key}">{body}</div>'
        for i, (key, _, body) in enumerate(panels)
    )
    return f'<div class="tabs" data-group="{group}">{buttons}</div>{bodies}'


def _contrast_sites(sites: pd.DataFrame, recommended: str) -> list[str]:
    """The recommended site, plus the driest and the wettest to contrast it.

    Those three are what makes the argument on a page nobody can drag a
    slider on: the same crew, the same dose limit, three different grounds,
    three different buildings.
    """
    order = sites.sort_values("predicted_weh_wt_pct")
    picks = [recommended, order.iloc[0]["name"], order.iloc[-1]["name"]]
    seen: list[str] = []
    for name in picks:
        if name not in seen:
            seen.append(name)
    return seen


def build(output: Path) -> Path:
    result = run_pipeline(random_state=SEED, include_grid=True)
    config = SettlementConfig()
    burial = BurialConfig()

    ranked = rank_sites(result.named_sites, config, POPULATION)
    viable = ranked[ranked["feasible"]]
    best = viable.iloc[0]
    best_row = result.named_sites[
        result.named_sites["name"] == best["name"]
    ].iloc[0]
    infra = size_infrastructure(best_row, POPULATION, config)

    architecture = architecture_table(result.named_sites, POPULATION, burial)
    audit = decision_audit(result.named_sites, POPULATION, burial)
    buildable = buildability_field(result.grid)

    blocks: list[str] = []
    first = True

    # --- underground architecture -----------------------------------------
    design = design_habitat(best_row, POPULATION, burial)
    blocks.append(
        "<h2>Underground architecture</h2>"
        "<p>The surface of Mars is the worst place on the planet to put a "
        "house. It takes 230 mSv a year, swings 90 K between afternoon and "
        "dawn, and offers nothing to hold a pressure vessel down. All three "
        "problems are solved a few metres below it, by the material already "
        "there. So the architectural question is not what shape the dome is; "
        "it is <em>how deep</em> — and that is a decision the water model "
        "already knows how to make, because pore ice is what separates loose "
        "regolith from rock.</p>"
    )

    section_panels = []
    for name in _contrast_sites(result.named_sites, best["name"]):
        row = result.named_sites[result.named_sites["name"] == name].iloc[0]
        site_design = design_habitat(row, POPULATION, burial)
        figure, dimensions = habitat_section(site_design)
        tiles = "".join([
            _tile("Method", site_design.method),
            _tile("Crown depth", f"{site_design.depth_m:.2f} m"),
            _tile("Pressure shell", f"{site_design.shell_thickness_mm:.2f} mm"),
            _tile("Landed mass", f"{site_design.landed_mass_kg / 1000:.1f} t"),
            _tile(
                "Excavated",
                f"{site_design.excavated_m3:,.0f} m³",
                f"{dimensions['spoil_volume_m3']:,.0f} m³ of spoil per vault",
            ),
        ])
        section_panels.append((
            name.replace(" ", "-").lower(),
            f"{name} · {row['predicted_weh_wt_pct']:.0f} wt% predicted",
            f'<div class="tiles">{tiles}</div>'
            f'<div class="figure">{_figure_html(figure, first)}</div>'
            f'<p class="note">{site_design.limiting_factor}</p>',
        ))
        first = False

    blocks.append(_tabs("section", section_panels))
    blocks.append(
        '<p class="note">A cut-away section, to scale in metres, generated '
        "from the sizing result rather than drawn. The cut face is coloured "
        "by radiation dose: the bright band in the first half-metre is the "
        "secondary neutron shower the shielding itself produces, which is why "
        "thin cover is close to worthless. Switch sites to watch the building "
        "change: dry ground cannot hold an unsupported roof, so the vault has "
        "to be trenched and its shell flown from Earth; ice-cemented ground "
        "holds a mined vault open.</p>"
    )

    blocks.append("<h3>Why that depth</h3>")
    blocks.append(
        f'<div class="figure">'
        f"{_figure_html(depth_profile_figure(depth_profile(best_row, POPULATION, burial), design), first, 700)}"
        f"</div>"
    )
    blocks.append(
        '<p class="note">Four curves pulling in different directions. '
        "Radiation says go down, and says the first third of a metre is "
        "wasted. The seasons say go further down than you would expect if the "
        "ground is icy, because pore ice conducts the annual temperature wave "
        "metres deeper than dry sand does. The structure says there is a depth "
        "at which the pressure shell stops being necessary. The cost says only "
        "one of the four methods can reach it.</p>"
    )
    blocks.append(_table_html(ground_property_table().round(2)))

    blocks.append("<h3>Where you can mine</h3>")
    blocks.append(
        f'<div class="figure">'
        f"{_figure_html(buildability_globe(buildable, ranked), first)}</div>"
    )
    mineable = int(buildable["can_mine_to_self_anchoring"].sum())
    blocks.append(
        '<p class="note">The water prediction wearing a different hat: how '
        "deep the ground at each cell could be mined without support. Pale "
        "ground is where a city can be excavated and lined; dark red is where "
        f"habitats have to be trenched. {mineable:,} of {len(buildable):,} "
        "grid cells can be mined past the depth where overburden cancels "
        "cabin pressure. The boundary is not a line of latitude — it follows "
        "the mantling deposit, which is exactly the part a latitude rule of "
        "thumb gets wrong.</p>"
    )

    blocks.append("<h3>Every site</h3>")
    blocks.append(_table_html(
        architecture[[
            "rank", "site", "latitude_deg", "water_grade_wt_pct", "method",
            "depth_m", "shell_mm", "insulation_cm", "landed_mass_t",
            "construction_energy_mwh", "feasible",
        ]].round({
            "latitude_deg": 1, "water_grade_wt_pct": 1, "depth_m": 2,
            "shell_mm": 2, "insulation_cm": 1, "landed_mass_t": 1,
            "construction_energy_mwh": 0,
        }).rename(columns={
            "rank": "#", "latitude_deg": "lat",
            "water_grade_wt_pct": "water wt%", "depth_m": "depth m",
            "shell_mm": "shell mm", "insulation_cm": "insul cm",
            "landed_mass_t": "mass t", "construction_energy_mwh": "dig MWh",
            "feasible": "buildable",
        })
    ))

    blocks.append("<h3>Was the model worth having?</h3>")
    blocks.append(
        "<p>Every site is designed five times, from five different beliefs "
        "about how much water is in the ground, and each design is then "
        "re-costed against the ground as it really is. A design that still "
        "meets its requirements is charged the difference against perfect "
        "foresight; one that does not is charged everything it landed, "
        "because that hardware has flown, failed, and the correct habitat "
        "still has to follow it.</p>"
    )
    blocks.append(_table_html(audit))

    # --- prediction and settlement ----------------------------------------
    blocks.append("<h2>Predicted water-equivalent hydrogen</h2>")
    blocks.append(
        "<p>Model output across a global grid of cells it was never trained "
        "on, draped over Mars' topography. The pale bands either side of the "
        "equator are the mantling deposits the regressor learned to find. "
        "Pins are candidate sites: green is viable at 100 crew, red is "
        "not.</p>"
    )
    blocks.append(
        f'<div class="figure">{_figure_html(water_globe(result.grid, ranked), first)}</div>'
    )

    blocks.append("<h3>Site ranking for 100 people</h3>")
    blocks.append(_table_html(
        ranked[[
            "rank", "name", "latitude_deg", "water_grade_wt_pct",
            "regolith_t_per_sol", "pv_area_km2", "landed_mass_t",
            "max_population", "feasible", "limiting_factor",
        ]].round({
            "latitude_deg": 1, "water_grade_wt_pct": 1,
            "regolith_t_per_sol": 1, "pv_area_km2": 3, "landed_mass_t": 0,
        }).rename(columns={
            "rank": "#", "name": "site", "latitude_deg": "lat",
            "water_grade_wt_pct": "water wt%",
            "regolith_t_per_sol": "rock t/sol", "pv_area_km2": "array km2",
            "landed_mass_t": "mass t", "max_population": "ceiling",
            "feasible": "viable", "limiting_factor": "binding constraint",
        })
    ))

    blocks.append("<h2>The settlement this implies, to scale</h2>")
    plan_figure, derived = settlement_plan(infra, best["name"])
    blocks.append(
        "<p>Not a concept drawing. Every dimension is computed from the "
        "sizing result for this site and crew size.</p>"
    )
    blocks.append(f'<div class="figure">{_figure_html(plan_figure, first)}</div>')
    blocks.append('<div class="tiles">' + "".join([
        _tile("Solar farm", f"{derived['array_side_m']:,.0f} m square"),
        _tile("Habitat domes", f"{derived['domes_needed']:,.0f}"),
        _tile("Open-pit mine", f"{derived['pit_radius_m']:,.0f} m radius"),
        _tile("Excavators", f"{infra.excavator_units}"),
    ]) + "</div>")

    blocks.append("<h2>Where it breaks as the city grows</h2>")
    blocks.append(_table_html(
        population_sweep(
            result.named_sites, config,
            populations=(20, 100, 300, 1000, 2000, 4000),
        )
    ))
    blocks.append(f"<h3>Dust-storm resilience at {best['name']}</h3>")
    blocks.append(_table_html(
        dust_storm_resilience(best_row, config, POPULATION)
    ))

    blocks.append("<h2>Model validation</h2>")
    report = result.report
    blocks.append('<div class="tiles">' + "".join([
        _tile("Held-out R²", f"{report.test_r2:.3f}"),
        _tile("Mean abs. error", f"{report.test_mae:.2f} wt%"),
        _tile("Ridge baseline R²", f"{report.ridge_test_r2:.3f}"),
        _tile("Mean baseline R²", f"{report.mean_baseline_test_r2:.3f}"),
    ]) + "</div>")
    blocks.append(
        f'<p class="note">Gradient boosting on {report.n_train:,} survey '
        f"cells, scored on {report.n_test:,} held out. Five-fold "
        f"cross-validated R² {report.cv_r2_mean:.3f} ± "
        f"{report.cv_r2_std:.3f}. Sizing uses the prediction minus one "
        f"residual sigma ({report.residual_std:.2f} wt%), because a water "
        "plant built on the mean forecast fails half the time the forecast "
        "is wrong. The orbital survey the model trains on is a physically "
        "motivated surrogate for the NASA Planetary Data System archive; it "
        "encodes published ground-ice stability results and is not presented "
        "as measured data. Every physical constant is sourced in "
        "<code>marswater/constants.py</code>.</p>"
    )

    header_tiles = "".join([
        _tile("Recommended site", best["name"]),
        _tile("Water in ground", f"{best['water_grade_wt_pct']:.1f} wt%"),
        _tile("Habitat", design.method, f"{design.depth_m:.2f} m down"),
        _tile("Landed mass", f"{best['landed_mass_t']:.0f} t"),
        _tile("Population ceiling", f"{int(best['max_population']):,}"),
    ])
    head = (
        "<header><h1>MARSWATER</h1>"
        '<p class="lede">Where should the first Martian city be built, how '
        "deep does it have to dig, and how big can it get? One machine "
        "learning model predicts subsurface water from orbital observables. "
        "Everything after that is physics: radiation, thermal diffusion, "
        "overburden, insolation, extraction energy, closed-loop life support, "
        "and the mass that has to be flown from Earth.</p>"
        f'<div class="tiles">{header_tiles}</div>'
        '<p class="note">A static render at the default mission parameters: '
        f"{POPULATION} crew, {config.fission_units} fission units, clear "
        "skies, return propellant produced on site. The interactive version, "
        "where every one of those is a slider, is "
        "<code>streamlit run app.py</code>.</p>"
        "</header>"
    )

    html = (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<title>MARSWATER — siting and building the first Martian city</title>"
        '<link rel="icon" href="data:image/svg+xml,'
        "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E"
        "%3Ccircle cx='16' cy='16' r='14' fill='%23c4562a'/%3E%3C/svg%3E\">"
        f"<style>{STYLE}</style></head><body><main>"
        + head
        + "".join(blocks)
        + "<footer>MARSWATER · Mars Hackathon 2026 · Architecture and Life "
          "Support tracks. Built with scikit-learn, Plotly and Streamlit."
          "</footer></main>"
        f"<script>{SCRIPT}</script></body></html>"
    )

    output.mkdir(parents=True, exist_ok=True)
    page = output / "index.html"
    page.write_text(html, encoding="utf-8")
    return page


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=Path("site"),
        help="Directory to write the static site into.",
    )
    parser.add_argument(
        "--clean", action="store_true", help="Remove the directory first."
    )
    arguments = parser.parse_args()
    if arguments.clean and arguments.output.exists():
        shutil.rmtree(arguments.output)
    page = build(arguments.output)
    size_mb = page.stat().st_size / 1e6
    print(f"wrote {page} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
