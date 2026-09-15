"""Three-dimensional views of the model output and the settlement it implies.

Neither of these figures is decorative. The globe drapes the model's predicted
water field over Mars' real topography, so the wet mid-latitude bands the
regressor learned to find are visible as a physical feature of the planet. The
settlement plan is generated from the simulation's own output: the solar farm
footprint is the computed array area in square metres, the dome count comes
from the pressurised volume the crew needs, and the mine radius scales with the
rock throughput the predicted ore grade demands. Move the population slider and
the base is rebuilt, because the geometry is a consequence of the physics rather
than a drawing of it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from . import constants as C

MARS_RADIUS_KM = 3389.5

#: Rust-red through to ice-blue: dry regolith to mineable ground ice.
WATER_COLOURSCALE = [
    [0.00, "#2b1a14"],
    [0.18, "#7a2f1a"],
    [0.38, "#c4562a"],
    [0.55, "#e08a4a"],
    [0.72, "#9fd8c8"],
    [0.88, "#7ec8e3"],
    [1.00, "#dff4fb"],
]

REGOLITH = "#8a4b2f"
PANEL_BLUE = "#2b5f87"
DOME_WHITE = "#dfe6ec"
REACTOR_GREY = "#9aa4ad"
PLANT_STEEL = "#6f7b85"
EXCAVATOR_AMBER = "#e0a33c"


# ---------------------------------------------------------------------------
# Globe
# ---------------------------------------------------------------------------
def water_globe(
    grid: pd.DataFrame,
    ranked: pd.DataFrame | None = None,
    elevation_exaggeration: float = 30.0,
    label_top_n: int = 6,
) -> go.Figure:
    """Predicted water-equivalent hydrogen draped over Mars' topography.

    ``elevation_exaggeration`` multiplies real relief. Mars' full dynamic range
    is about 30 km against a 3,390 km radius, so unexaggerated topography is
    invisible on a globe; the default makes Tharsis and Hellas readable while
    keeping the sphere recognisable.
    """
    water = grid.pivot_table(
        index="latitude_deg", columns="longitude_deg",
        values="predicted_weh_wt_pct", aggfunc="mean",
    )
    elevation = grid.pivot_table(
        index="latitude_deg", columns="longitude_deg",
        values="elevation_km", aggfunc="mean",
    ).reindex(index=water.index, columns=water.columns)

    latitudes = water.index.to_numpy(dtype=float)
    longitudes = water.columns.to_numpy(dtype=float)
    water_values = water.to_numpy(dtype=float)
    elevation_values = elevation.to_numpy(dtype=float)

    # Close the meridian seam so the globe has no visible slit, then pad to the
    # poles with the nearest sampled row so the sphere is capped.
    longitudes = np.append(longitudes, longitudes[0] + 360.0)
    water_values = np.hstack([water_values, water_values[:, :1]])
    elevation_values = np.hstack([elevation_values, elevation_values[:, :1]])

    latitudes = np.concatenate([[-90.0], latitudes, [90.0]])
    water_values = np.vstack([water_values[:1], water_values, water_values[-1:]])
    elevation_values = np.vstack(
        [elevation_values[:1], elevation_values, elevation_values[-1:]]
    )

    lat_mesh, lon_mesh = np.meshgrid(
        np.radians(latitudes), np.radians(longitudes), indexing="ij"
    )
    radius = MARS_RADIUS_KM + elevation_exaggeration * elevation_values

    x = radius * np.cos(lat_mesh) * np.cos(lon_mesh)
    y = radius * np.cos(lat_mesh) * np.sin(lon_mesh)
    z = radius * np.sin(lat_mesh)

    figure = go.Figure()
    figure.add_trace(
        go.Surface(
            x=x, y=y, z=z,
            surfacecolor=water_values,
            colorscale=WATER_COLOURSCALE, cmin=0.0, cmax=30.0,
            colorbar=dict(title="wt% H₂O", len=0.7, thickness=14),
            lighting=dict(ambient=0.62, diffuse=0.85, specular=0.12, roughness=0.92),
            hovertemplate="predicted %{surfacecolor:.1f} wt%<extra></extra>",
            name="predicted water",
        )
    )

    if ranked is not None and len(ranked):
        _add_site_pins(figure, ranked, elevation_exaggeration, label_top_n)

    figure.update_layout(
        template="plotly_dark",
        scene=dict(
            xaxis=dict(visible=False), yaxis=dict(visible=False),
            zaxis=dict(visible=False),
            aspectmode="data", bgcolor="#07040a",
            camera=dict(eye=dict(x=1.25, y=1.25, z=0.75)),
        ),
        margin=dict(l=0, r=0, t=0, b=0), height=620, showlegend=False,
        paper_bgcolor="#07040a",
    )
    return figure


def _add_site_pins(
    figure: go.Figure,
    ranked: pd.DataFrame,
    elevation_exaggeration: float,
    label_top_n: int,
) -> None:
    """Candidate sites as pins standing off the surface.

    Pins are raised clear of the terrain so they stay visible when the globe is
    rotated, and coloured by whether the site is viable at the current crew
    size: green survives, red does not.
    """
    lat = np.radians(ranked["latitude_deg"].to_numpy(dtype=float))
    lon = np.radians(ranked["longitude_deg"].to_numpy(dtype=float))
    base = MARS_RADIUS_KM + elevation_exaggeration * ranked[
        "elevation_km"
    ].to_numpy(dtype=float)
    tip = base + 190.0

    def to_cartesian(r):
        return (
            r * np.cos(lat) * np.cos(lon),
            r * np.cos(lat) * np.sin(lon),
            r * np.sin(lat),
        )

    bx, by, bz = to_cartesian(base)
    tx, ty, tz = to_cartesian(tip)

    # One trace holding every pin stem, separated by NaN breaks.
    stem_x, stem_y, stem_z = [], [], []
    for i in range(len(ranked)):
        stem_x += [bx[i], tx[i], np.nan]
        stem_y += [by[i], ty[i], np.nan]
        stem_z += [bz[i], tz[i], np.nan]

    figure.add_trace(
        go.Scatter3d(
            x=stem_x, y=stem_y, z=stem_z, mode="lines",
            line=dict(color="rgba(255,255,255,0.45)", width=3),
            hoverinfo="skip", showlegend=False,
        )
    )

    labels = ranked["name"].to_numpy()
    text = np.where(np.arange(len(ranked)) < label_top_n, labels, "")
    figure.add_trace(
        go.Scatter3d(
            x=tx, y=ty, z=tz, mode="markers+text",
            marker=dict(
                size=6,
                color=["#46f08a" if f else "#ff5a5a" for f in ranked["feasible"]],
                line=dict(color="white", width=1),
                symbol="diamond",
            ),
            text=text, textposition="top center",
            textfont=dict(size=10, color="#f2f2f2"),
            customdata=np.stack(
                [
                    labels,
                    ranked["water_grade_wt_pct"].to_numpy(dtype=float),
                    ranked["landed_mass_t"].to_numpy(dtype=float),
                    ranked["limiting_factor"].to_numpy(),
                ],
                axis=-1,
            ),
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "water %{customdata[1]:.1f} wt%<br>"
                "landed mass %{customdata[2]:.0f} t<br>"
                "%{customdata[3]}<extra></extra>"
            ),
            showlegend=False,
        )
    )


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------
def _hemisphere(cx: float, cy: float, radius: float, n_u: int = 26, n_v: int = 12):
    u = np.linspace(0.0, 2.0 * np.pi, n_u)
    v = np.linspace(0.0, 0.5 * np.pi, n_v)
    u_mesh, v_mesh = np.meshgrid(u, v)
    return (
        cx + radius * np.cos(u_mesh) * np.cos(v_mesh),
        cy + radius * np.sin(u_mesh) * np.cos(v_mesh),
        radius * np.sin(v_mesh),
    )


def _cylinder(cx: float, cy: float, radius: float, height: float, n_u: int = 18):
    u = np.linspace(0.0, 2.0 * np.pi, n_u)
    h = np.linspace(0.0, height, 2)
    u_mesh, h_mesh = np.meshgrid(u, h)
    return (
        cx + radius * np.cos(u_mesh),
        cy + radius * np.sin(u_mesh),
        h_mesh,
    )


def _inverted_cone(cx: float, cy: float, radius: float, depth: float, n_u: int = 28):
    """An open-pit mine: a bowl cut into the ground plane."""
    u = np.linspace(0.0, 2.0 * np.pi, n_u)
    t = np.linspace(0.0, 1.0, 8)
    u_mesh, t_mesh = np.meshgrid(u, t)
    return (
        cx + radius * t_mesh * np.cos(u_mesh),
        cy + radius * t_mesh * np.sin(u_mesh),
        -depth * (1.0 - t_mesh),
    )


def _solid_surface(x, y, z, colour: str, name: str, opacity: float = 1.0):
    return go.Surface(
        x=x, y=y, z=z,
        colorscale=[[0, colour], [1, colour]],
        showscale=False, opacity=opacity, name=name,
        hovertemplate=f"{name}<extra></extra>",
        lighting=dict(ambient=0.55, diffuse=0.9, specular=0.25, roughness=0.6),
    )


def _panel_row(x0: float, x1: float, y: float, width: float, tilt_deg: float):
    """One tilted photovoltaic row, as a quad."""
    tilt = np.radians(tilt_deg)
    dy = width * np.cos(tilt)
    dz = width * np.sin(tilt)
    x = np.array([[x0, x1], [x0, x1]])
    y_arr = np.array([[y, y], [y + dy, y + dy]])
    z = np.array([[1.0, 1.0], [1.0 + dz, 1.0 + dz]])
    return x, y_arr, z


# ---------------------------------------------------------------------------
# Settlement plan
# ---------------------------------------------------------------------------
PRESSURISED_VOLUME_M3_PER_PERSON = 60.0
DOME_RADIUS_M = 12.0
MAX_DRAWN_DOMES = 28
MAX_DRAWN_PANEL_ROWS = 22
MAX_DRAWN_REACTORS = 10
MAX_DRAWN_EXCAVATORS = 10
REGOLITH_BULK_DENSITY = 1600.0  # kg/m^3, loose Martian regolith
PIT_DEPTH_RATIO = 0.35  # pit depth as a fraction of its radius


def settlement_plan(infra, site_name: str) -> tuple[go.Figure, dict[str, float]]:
    """Build the base implied by one sizing result, to scale in metres.

    Returns the figure and the derived quantities it was built from, so the
    caption can state what is being shown rather than leaving the viewer to
    assume it is artistic licence.
    """
    array_area = float(infra.pv_area_m2)
    array_side = float(np.sqrt(max(array_area, 1.0)))

    dome_volume = (2.0 / 3.0) * np.pi * DOME_RADIUS_M**3
    crew_per_dome = dome_volume / PRESSURISED_VOLUME_M3_PER_PERSON
    domes_needed = int(np.ceil(infra.population / crew_per_dome))

    # A pit is cumulative excavation, not one sol's worth, so it is sized over
    # a full launch window -- the natural planning period, and the interval the
    # propellant campaign is already pegged to. Modelled as an inverted cone of
    # depth 0.35r, whose volume is (1/3)·pi·0.35·r³.
    regolith_m3_per_sol = infra.regolith_kg_per_sol / REGOLITH_BULK_DENSITY
    excavated_m3 = regolith_m3_per_sol * C.SYNOD_SOLS
    pit_radius = float(
        (max(excavated_m3, 1.0) / (np.pi * PIT_DEPTH_RATIO / 3.0)) ** (1.0 / 3.0)
    )

    extent = max(array_side * 0.85, pit_radius * 2.2, 260.0)

    figure = go.Figure()

    # Ground plane.
    ground = np.linspace(-extent, extent, 2)
    gx, gy = np.meshgrid(ground, ground)
    figure.add_trace(
        _solid_surface(gx, gy, np.zeros_like(gx), REGOLITH, "regolith surface")
    )

    # Solar farm, west of the habitat. Row count is capped for rendering, and
    # the total collector area is preserved by widening the drawn rows.
    rows = min(MAX_DRAWN_PANEL_ROWS, max(4, int(array_side / 14.0)))
    row_width = array_area / (rows * array_side)
    pitch = array_side / rows
    for i in range(rows):
        x0 = -array_side - 40.0
        x1 = x0 + array_side
        y = -array_side / 2.0 + i * pitch
        px, py, pz = _panel_row(x0, x1, y, row_width, tilt_deg=25.0)
        figure.add_trace(_solid_surface(px, py, pz, PANEL_BLUE, "solar array"))

    # Habitat domes in a hexagonal cluster east of the array.
    drawn_domes = min(domes_needed, MAX_DRAWN_DOMES)
    spacing = DOME_RADIUS_M * 2.9
    for index in range(drawn_domes):
        ring = int((3 + np.sqrt(9 + 12 * index)) // 6) if index else 0
        if ring == 0:
            cx, cy = 60.0, 0.0
        else:
            per_ring = 6 * ring
            position = index - (3 * ring * (ring - 1) + 1)
            angle = 2.0 * np.pi * position / per_ring
            cx = 60.0 + ring * spacing * np.cos(angle)
            cy = ring * spacing * np.sin(angle)
        hx, hy, hz = _hemisphere(cx, cy, DOME_RADIUS_M)
        figure.add_trace(_solid_surface(hx, hy, hz, DOME_WHITE, "habitat dome"))

    # Fission units, set back from the habitat as they would be for shielding.
    for index in range(min(infra.fission_units, MAX_DRAWN_REACTORS)):
        cx = 40.0 + index * 26.0
        cy = -extent * 0.55
        rx, ry, rz = _cylinder(cx, cy, 6.0, 9.0)
        figure.add_trace(_solid_surface(rx, ry, rz, REACTOR_GREY, "fission unit"))

    # The mine, and the extraction plant beside it.
    pit_cx = extent * 0.52
    px, py, pz = _inverted_cone(
        pit_cx, extent * 0.42, pit_radius, pit_radius * PIT_DEPTH_RATIO
    )
    figure.add_trace(_solid_surface(px, py, pz, "#5b2f1e", "open-pit mine"))

    plant_x, plant_y, plant_z = _cylinder(
        pit_cx - pit_radius - 45.0, extent * 0.42, 16.0, 22.0
    )
    figure.add_trace(
        _solid_surface(plant_x, plant_y, plant_z, PLANT_STEEL, "extraction plant")
    )

    for index in range(min(infra.excavator_units, MAX_DRAWN_EXCAVATORS)):
        angle = 2.0 * np.pi * index / max(
            min(infra.excavator_units, MAX_DRAWN_EXCAVATORS), 1
        )
        ex = pit_cx + (pit_radius + 24.0) * np.cos(angle)
        ey = extent * 0.42 + (pit_radius + 24.0) * np.sin(angle)
        cx_, cy_, cz_ = _cylinder(ex, ey, 4.5, 5.0)
        figure.add_trace(
            _solid_surface(cx_, cy_, cz_, EXCAVATOR_AMBER, "excavator")
        )

    figure.update_layout(
        template="plotly_dark",
        scene=dict(
            xaxis=dict(title="metres", showgrid=False, zeroline=False,
                       backgroundcolor="#0b0709"),
            yaxis=dict(title="metres", showgrid=False, zeroline=False,
                       backgroundcolor="#0b0709"),
            zaxis=dict(visible=False),
            aspectmode="data", bgcolor="#0b0709",
            camera=dict(eye=dict(x=1.5, y=-1.5, z=0.85)),
        ),
        margin=dict(l=0, r=0, t=0, b=0), height=560, showlegend=False,
        paper_bgcolor="#0b0709",
        title=dict(text=f"{site_name} — {infra.population:,} crew", x=0.02,
                   font=dict(size=15)),
    )

    return figure, {
        "array_area_m2": array_area,
        "array_side_m": array_side,
        "domes_needed": float(domes_needed),
        "domes_drawn": float(drawn_domes),
        "crew_per_dome": crew_per_dome,
        "pit_radius_m": pit_radius,
        "regolith_m3_per_sol": regolith_m3_per_sol,
        "excavated_m3_per_synod": excavated_m3,
        "panel_rows_drawn": float(rows),
    }
