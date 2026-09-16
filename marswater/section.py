"""Three-dimensional views of the underground habitat the physics chose.

The section is the architect's drawing, and here it is generated rather than
drawn. Depth, span, shell thickness, insulation thickness, spoil volume and
the height of the tip outside are all read off the design returned by
``subsurface.design_habitat``, so moving the crew size or the water content
rebuilds the building instead of relabelling it.

The cut face of the section is coloured by radiation dose, which makes the
central argument of the whole track visible in one image: a bright band of
secondary neutron shower in the first half-metre where shielding is worse than
useless, and darkness a couple of metres further down where the same material
has taken the dose below a terrestrial occupational limit.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from . import constants as C
from .globe import field_globe
from .subsurface import (
    BERM,
    CUT_AND_COVER,
    METHODS,
    MINED,
    MINED_SINTERED,
    HabitatDesign,
    bulk_density_kg_m3,
    cohesion_kpa,
    depth_for_dose_m,
    gcr_dose_msv_per_year,
    max_unsupported_depth_m,
    self_anchoring_depth_m,
    thermal_skin_depth_m,
)

#: Hot where the dose is, cold rock where it is not. The dark end is a dull
#: regolith brown rather than black so that deep ground still reads as
#: material instead of dissolving into the background.
DOSE_COLOURSCALE = [
    [0.00, "#2b211d"],
    [0.20, "#3a2030"],
    [0.40, "#6a1f47"],
    [0.58, "#b03a3a"],
    [0.78, "#e2802f"],
    [1.00, "#ffe9a8"],
]

#: Shallow ground cannot be mined; deep ground can. The break in the scale
#: sits at the self-anchoring depth, which is the depth worth reaching.
BUILDABILITY_COLOURSCALE = [
    [0.00, "#3b1f1a"],
    [0.24, "#8a3a22"],
    [0.40, "#c9702f"],
    [0.52, "#f0d27a"],
    [0.66, "#7fc6a4"],
    [1.00, "#cdf1e4"],
]

VAULT_STEEL = "#b9c4cd"
INSULATION_GOLD = "#d8b25a"
SHAFT_GREY = "#8d979f"
SPOIL_BROWN = "#7a4a2c"
SURFACE_PLANT = "#5f6a73"


# ---------------------------------------------------------------------------
# Section
# ---------------------------------------------------------------------------
def _dose_section_face(
    design: HabitatDesign,
    x_limit: float,
    z_bottom: float,
    shaft_x: float,
    n_x: int = 120,
    n_z: int = 90,
):
    """The cut face at y = 0, coloured by dose and pierced by the excavation.

    Points that fall inside the vault or the access shaft are set to NaN so the
    face is genuinely open there. That is what makes it read as a section: the
    viewer looks through the hole in the rock at the inside of the vault
    behind it.
    """
    geometry_radius = 6.0
    x = np.linspace(-x_limit, x_limit, n_x)
    z = np.linspace(0.0, z_bottom, n_z)
    x_mesh, z_mesh = np.meshgrid(x, z)

    depth = -z_mesh
    dose = gcr_dose_msv_per_year(np.maximum(depth, 0.0), design.water_grade_wt_pct)

    centre_z = -(design.depth_m + geometry_radius)
    half_length = 20.0
    in_vault = (np.abs(x_mesh) <= half_length) & (
        np.abs(z_mesh - centre_z) <= geometry_radius
    )
    in_shaft = (np.abs(x_mesh - shaft_x) <= 2.5) & (z_mesh >= centre_z)

    face_z = np.where(in_vault | in_shaft, np.nan, z_mesh)
    return x_mesh, np.zeros_like(x_mesh), face_z, dose


def _half_cylinder_along_x(
    centre_z: float, radius: float, half_length: float, n_theta: int = 40
):
    """The half of a horizontal tube that faces the viewer across the cut."""
    theta = np.linspace(-0.5 * np.pi, 0.5 * np.pi, n_theta)
    x = np.array([-half_length, half_length])
    theta_mesh, x_mesh = np.meshgrid(theta, x, indexing="ij")
    return (
        x_mesh,
        radius * np.cos(theta_mesh),
        centre_z + radius * np.sin(theta_mesh),
    )


def _half_cylinder_vertical(
    x_centre: float, radius: float, z_top: float, z_bottom: float, n_theta: int = 24
):
    """A shaft, drawn as the half standing in the cut-away."""
    theta = np.linspace(-0.5 * np.pi, 0.5 * np.pi, n_theta)
    z = np.array([z_bottom, z_top])
    theta_mesh, z_mesh = np.meshgrid(theta, z, indexing="ij")
    return (
        x_centre + radius * np.sin(theta_mesh),
        radius * np.cos(theta_mesh),
        z_mesh,
    )


def _cone(x_centre: float, y_centre: float, radius: float, height: float):
    """The spoil tip: everything that came out of the hole, at repose."""
    theta = np.linspace(0.0, 2.0 * np.pi, 30)
    t = np.linspace(0.0, 1.0, 8)
    theta_mesh, t_mesh = np.meshgrid(theta, t)
    return (
        x_centre + radius * (1.0 - t_mesh) * np.cos(theta_mesh),
        y_centre + radius * (1.0 - t_mesh) * np.sin(theta_mesh),
        height * t_mesh,
    )


def _flat(x, y, z, colour: str, name: str, opacity: float = 1.0) -> go.Surface:
    return go.Surface(
        x=x, y=y, z=z,
        colorscale=[[0, colour], [1, colour]],
        showscale=False, opacity=opacity, name=name,
        hovertemplate=f"{name}<extra></extra>",
        lighting=dict(ambient=0.5, diffuse=0.9, specular=0.2, roughness=0.65),
    )


def habitat_section(design: HabitatDesign) -> tuple[go.Figure, dict[str, float]]:
    """A cut-away section through the chosen habitat, to scale in metres.

    Returns the figure and the dimensions it was built from, so the caption can
    state what is being shown instead of inviting the viewer to assume it is an
    impression.
    """
    radius = 6.0
    half_length = 20.0
    crown = design.depth_m
    centre_z = -(crown + radius)
    x_limit = half_length + 22.0
    z_bottom = centre_z - radius - 8.0
    shaft_x = half_length + 10.0
    y_limit = 26.0

    # The spoil tip is sized first because it can be larger than the habitat,
    # and when it is, the ground plane has to be extended to carry it. Its
    # volume is the excavation, so the pile is the honest picture of what a
    # construction method costs: a mined vault leaves a mound, and a
    # cut-and-cover trench leaves a hill taller than the building.
    spoil_volume = design.excavated_m3 / max(design.vaults, 1)
    spoil_radius = float((3.0 * spoil_volume / (np.pi * 0.577)) ** (1.0 / 3.0))
    spoil_height = 0.577 * spoil_radius
    # Placed behind the block rather than beside it: the spoil from a
    # cut-and-cover trench is tens of metres across, and putting it on the
    # along-vault axis would stretch that axis until the habitat's own
    # dimensions became unreadable.
    spoil_y = y_limit + spoil_radius * 1.1
    ground_north = spoil_y + spoil_radius * 1.2

    figure = go.Figure()

    # The cut face, carrying the dose gradient and the openings.
    fx, fy, fz, dose = _dose_section_face(design, x_limit, z_bottom, shaft_x)
    figure.add_trace(
        go.Surface(
            x=fx, y=fy, z=fz,
            surfacecolor=np.log10(np.maximum(dose, 1e-3)),
            colorscale=DOSE_COLOURSCALE,
            cmin=-2.0, cmax=np.log10(C.GCR_SURFACE_DOSE_MSV_PER_YEAR),
            colorbar=dict(
                title="dose<br>mSv/yr",
                tickvals=[-2, -1, 0, 1, 2, np.log10(230.0)],
                ticktext=["0.01", "0.1", "1", "10", "100", "230"],
                len=0.6, thickness=13,
            ),
            hovertemplate="%{z:.1f} m: %{customdata:.2f} mSv/yr<extra></extra>",
            customdata=dose,
            name="regolith section",
            lighting=dict(ambient=0.85, diffuse=0.3, specular=0.02),
        )
    )

    # Original grade, extended back to carry the spoil tip.
    ground_x, ground_y = np.meshgrid(
        np.linspace(-x_limit, x_limit, 2), np.linspace(0.0, ground_north, 2)
    )
    figure.add_trace(
        _flat(ground_x, ground_y, np.zeros_like(ground_x), "#8a4b2f", "original grade")
    )

    # Remaining faces of the block, so it reads as ground rather than a sheet.
    for face_x in (-x_limit, x_limit):
        end_y, end_z = np.meshgrid(
            np.linspace(0.0, y_limit, 2), np.linspace(z_bottom, 0.0, 2)
        )
        figure.add_trace(
            _flat(
                np.full_like(end_y, face_x), end_y, end_z,
                "#4a3129", "regolith",
            )
        )
    far_x, far_z = np.meshgrid(
        np.linspace(-x_limit, x_limit, 2), np.linspace(z_bottom, 0.0, 2)
    )
    figure.add_trace(
        _flat(far_x, np.full_like(far_x, y_limit), far_z, "#3f2a23", "regolith")
    )

    # The vault. An insulation blanket is a few centimetres on a six-metre
    # radius, so drawing it to scale would produce two pixels hidden behind
    # the liner. It is encoded as the colour of the vault instead: gold means
    # this habitat has to be insulated from the ice it is standing in, steel
    # means the surrounding regolith is dry enough to insulate itself.
    insulated = design.insulation_thickness_m >= 0.005
    vault_colour = INSULATION_GOLD if insulated else VAULT_STEEL
    vault_label = (
        "vault, insulated "
        f"({design.insulation_thickness_m * 100:.0f} cm against ice thaw)"
        if insulated
        else "vault, uninsulated (dry regolith)"
    )

    vx, vy, vz = _half_cylinder_along_x(centre_z, radius, half_length)
    figure.add_trace(_flat(vx, vy, vz, vault_colour, vault_label))

    # End walls of the vault, so the opening reads as a tube rather than a
    # trough.
    for cap_x in (-half_length, half_length):
        theta = np.linspace(-0.5 * np.pi, 0.5 * np.pi, 30)
        t = np.linspace(0.0, 1.0, 2)
        theta_mesh, t_mesh = np.meshgrid(theta, t)
        figure.add_trace(
            _flat(
                np.full_like(theta_mesh, cap_x),
                radius * t_mesh * np.cos(theta_mesh),
                centre_z + radius * t_mesh * np.sin(theta_mesh),
                "#8f9aa3",
                vault_label,
            )
        )

    # Access shaft and the surface headworks above it.
    sx, sy, sz = _half_cylinder_vertical(shaft_x, 2.5, 0.0, centre_z)
    figure.add_trace(_flat(sx, sy, sz, SHAFT_GREY, "access shaft"))

    head_x, head_y = np.meshgrid(
        shaft_x + np.array([-4.5, 4.5]), np.array([0.0, 4.5])
    )
    figure.add_trace(
        _flat(head_x, head_y, np.full_like(head_x, 3.0), SURFACE_PLANT, "airlock head")
    )

    cone_x, cone_y, cone_z = _cone(
        0.0, spoil_y, spoil_radius, spoil_height
    )
    figure.add_trace(_flat(cone_x, cone_y, cone_z, SPOIL_BROWN, "spoil tip"))

    _add_depth_markers(figure, design, x_limit, y_limit, centre_z, radius)

    figure.update_layout(
        template="plotly_dark",
        scene=dict(
            xaxis=dict(title="metres along the vault", showgrid=False, zeroline=False,
                       backgroundcolor="#0a0709"),
            yaxis=dict(visible=False),
            zaxis=dict(title="metres below grade", showgrid=False, zeroline=False,
                       backgroundcolor="#0a0709"),
            aspectmode="data",
            bgcolor="#0a0709",
            camera=dict(eye=dict(x=1.35, y=-1.75, z=0.55)),
        ),
        margin=dict(l=0, r=0, t=34, b=0),
        height=620,
        showlegend=True,
        legend=dict(
            orientation="h", yanchor="bottom", y=0.0, xanchor="left", x=0.0,
            font=dict(size=10), bgcolor="rgba(10,7,9,0.65)",
        ),
        paper_bgcolor="#0a0709",
        title=dict(
            text=(
                f"{design.site_name} — {design.method}, crown {design.depth_m:.2f} m "
                f"below grade"
            ),
            x=0.02, font=dict(size=14),
        ),
    )

    return figure, {
        "crown_depth_m": design.depth_m,
        "invert_depth_m": crown + 2.0 * radius,
        "span_m": 2.0 * radius,
        "spoil_radius_m": spoil_radius,
        "spoil_height_m": spoil_height,
        "spoil_volume_m3": spoil_volume,
        "dose_limit_depth_m": depth_for_dose_m(
            C.DOSE_LIMIT_MSV_PER_YEAR, design.water_grade_wt_pct
        ),
        "self_anchoring_depth_m": float(
            self_anchoring_depth_m(design.water_grade_wt_pct)
        ),
        "annual_skin_depth_m": design.annual_skin_depth_m,
    }


def _add_depth_markers(
    figure: go.Figure,
    design: HabitatDesign,
    x_limit: float,
    y_limit: float,
    centre_z: float,
    radius: float,
) -> None:
    """Label the three depths that compete to set the answer.

    Each of these is a different discipline asking for a different number, and
    the point of showing them together is that the chosen depth has to satisfy
    the deepest of them, not the average.
    """
    grade = design.water_grade_wt_pct
    markers = [
        (
            depth_for_dose_m(C.DOSE_LIMIT_MSV_PER_YEAR, grade),
            f"{C.DOSE_LIMIT_MSV_PER_YEAR:.0f} mSv/yr reached",
            "#ffb35c",
        ),
        (
            float(self_anchoring_depth_m(grade)),
            "overburden cancels cabin pressure",
            "#7fc6a4",
        ),
        (
            float(
                thermal_skin_depth_m(grade, C.MARS_YEAR_SOLS * C.SOL_LENGTH_S)
            ),
            "annual thermal wave 1/e depth",
            "#8db4e0",
        ),
    ]

    # Named in the legend rather than lettered onto the face. In dry ground
    # the dose depth and the annual skin depth fall within a metre of each
    # other, and at that separation 3D text either overlaps itself or lands on
    # top of the vault, where it cannot be read at all.
    for depth, label, colour in markers:
        if not np.isfinite(depth) or depth > abs(centre_z) + radius + 6.0:
            continue
        figure.add_trace(
            go.Scatter3d(
                x=[-x_limit, x_limit, np.nan, x_limit, x_limit],
                y=[0.0, 0.0, np.nan, 0.0, y_limit],
                z=[-depth, -depth, np.nan, -depth, -depth],
                mode="lines",
                line=dict(color=colour, width=4, dash="dash"),
                name=f"{label} — {depth:.1f} m",
                hovertemplate=f"{label}: %{{z:.2f}} m<extra></extra>",
                showlegend=True,
            )
        )


# ---------------------------------------------------------------------------
# Why that depth
# ---------------------------------------------------------------------------
METHOD_COLOURS = {
    BERM: "#e0863c",
    CUT_AND_COVER: "#d2544f",
    MINED: "#5fc6a0",
    MINED_SINTERED: "#7fa8e0",
}


def depth_profile_figure(
    profile: pd.DataFrame,
    design: HabitatDesign,
    config_dose_limit: float = C.DOSE_LIMIT_MSV_PER_YEAR,
    config_swing_tolerance: float = 2.0,
) -> go.Figure:
    """The four curves that decide the depth, with the chosen design marked.

    Read clockwise from the top left, the argument is: radiation says go down,
    and says the first third of a metre is wasted; the seasons say go further
    down than you expected if the ground is icy; the structure says there is a
    depth at which the pressure shell stops being necessary; and the cost says
    that only one of the four construction methods can reach it.
    """
    figure = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            "Radiation dose against depth",
            "Ground temperature swing against depth",
            "Net pressure the enclosure must carry",
            "Landed mass per habitat",
        ),
        vertical_spacing=0.13, horizontal_spacing=0.09,
    )

    # The dose curve is computed here on its own fine grid rather than read off
    # the profile table. The secondary-buildup peak sits at about 7 cm, which
    # the optimiser's 25 cm depth steps step straight over -- and that peak is
    # the whole point of the panel, because it is the reason a shallow berm is
    # poor value.
    fine = np.linspace(0.0, 4.0, 401)
    dose = gcr_dose_msv_per_year(fine, design.water_grade_wt_pct)
    peak = int(np.argmax(dose))

    figure.add_trace(
        go.Scatter(
            x=fine, y=dose,
            mode="lines", line=dict(color="#ffb35c", width=3),
            showlegend=False,
            hovertemplate="%{x:.2f} m: %{y:.1f} mSv/yr<extra></extra>",
        ),
        row=1, col=1,
    )
    figure.add_trace(
        go.Scatter(
            x=[fine[peak]], y=[dose[peak]],
            mode="markers+text", marker=dict(size=9, color="#ff6b6b"),
            text=[f" secondary shower peaks at {fine[peak]*100:.0f} cm"],
            textposition="middle right", textfont=dict(size=10, color="#ff9b9b"),
            showlegend=False, hoverinfo="skip",
        ),
        row=1, col=1,
    )
    figure.add_hline(
        y=config_dose_limit, line=dict(color="#ff6b6b", dash="dot"),
        row=1, col=1,
    )
    figure.update_yaxes(
        type="log", title_text="mSv/yr", range=[-1.0, 2.8], row=1, col=1
    )
    figure.update_xaxes(range=[0.0, 4.0], row=1, col=1)

    single = profile[profile["method"] == METHODS[0]].sort_values("depth_m")
    figure.add_trace(
        go.Scatter(
            x=single["depth_m"], y=single["temperature_swing_k"],
            mode="lines", line=dict(color="#8db4e0", width=3),
            showlegend=False,
            hovertemplate="%{x:.2f} m: %{y:.2f} K<extra></extra>",
        ),
        row=1, col=2,
    )
    figure.add_hline(
        y=config_swing_tolerance, line=dict(color="#ff6b6b", dash="dot"),
        row=1, col=2,
    )
    figure.update_yaxes(
        type="log", title_text="K peak to trough", range=[-1.4, 2.0], row=1, col=2
    )

    # Drawn deepest-method-last so the two mined variants, which share an
    # identical net pressure curve, do not hide one another.
    for method in METHODS:
        subset = profile[profile["method"] == method].sort_values("depth_m")
        colour = METHOD_COLOURS[method]
        dash = "dash" if method == MINED_SINTERED else "solid"
        figure.add_trace(
            go.Scatter(
                x=subset["depth_m"], y=subset["net_pressure_kpa"],
                mode="lines", line=dict(color=colour, width=2.5, dash=dash),
                name=method, legendgroup=method,
                hovertemplate=f"{method}<br>%{{x:.2f}} m: %{{y:.1f}} kPa<extra></extra>",
            ),
            row=2, col=1,
        )
        figure.add_trace(
            go.Scatter(
                x=subset["depth_m"], y=subset["landed_mass_t"],
                mode="lines", line=dict(color=colour, width=2.5, dash=dash),
                name=method, legendgroup=method, showlegend=False,
                hovertemplate=f"{method}<br>%{{x:.2f}} m: %{{y:.0f}} t<extra></extra>",
            ),
            row=2, col=2,
        )

    figure.add_trace(
        go.Scatter(
            x=[design.depth_m], y=[design.landed_mass_kg / 1000.0],
            mode="markers+text",
            marker=dict(size=13, color="#ffffff", symbol="star",
                        line=dict(color="#111111", width=1)),
            text=["chosen"], textposition="top center",
            textfont=dict(size=10, color="#ffffff"),
            showlegend=False,
            hovertemplate="chosen design<br>%{x:.2f} m, %{y:.0f} t<extra></extra>",
        ),
        row=2, col=2,
    )

    figure.update_yaxes(title_text="kPa", row=2, col=1)
    figure.update_yaxes(title_text="tonnes", row=2, col=2)
    for row, col in ((1, 1), (1, 2), (2, 1), (2, 2)):
        figure.update_xaxes(title_text="crown depth (m)", row=row, col=col)

    figure.update_layout(
        template="plotly_dark", height=620,
        margin=dict(l=0, r=0, t=46, b=0),
        legend=dict(orientation="h", y=-0.13, x=0.0, font=dict(size=10)),
    )
    figure.update_annotations(font_size=12)
    return figure


# ---------------------------------------------------------------------------
# Where a city can be mined
# ---------------------------------------------------------------------------
def buildability_globe(
    field: pd.DataFrame,
    ranked: pd.DataFrame | None = None,
    elevation_exaggeration: float = 30.0,
    cap_m: float = 15.0,
) -> go.Figure:
    """A global map of how deep the ground can be mined without support.

    This is the water prediction wearing a different hat. The colour break sits
    near 9 m, the depth at which overburden cancels cabin pressure: everything
    cool enough to be blue-green is ground where a city can be excavated and
    lined, and everything red is ground where habitats have to be trenched and
    their pressure shells flown from Earth.

    Values are capped for display because cemented ground runs to hundreds of
    metres, which would flatten the interesting part of the scale.
    """
    display = field.copy()
    display["_buildable_depth_display"] = np.minimum(
        display["max_unsupported_depth_m"], cap_m
    )
    return field_globe(
        display,
        value_column="_buildable_depth_display",
        colourscale=BUILDABILITY_COLOURSCALE,
        cmin=0.0,
        cmax=cap_m,
        colorbar_title="mineable<br>depth (m)",
        hovertemplate="can be mined to %{surfacecolor:.1f} m unsupported<extra></extra>",
        trace_name="mineable depth",
        ranked=ranked,
        elevation_exaggeration=elevation_exaggeration,
    )


def ground_property_table(grades: tuple[float, ...] = (0.5, 2.0, 5.0, 10.0, 20.0)):
    """The two Martian ground materials, side by side.

    Useful in its own right during a demo: it is the shortest way to show that
    everything downstream follows from one predicted number.
    """
    annual_period_s = C.MARS_YEAR_SOLS * C.SOL_LENGTH_S
    rows = []
    for grade in grades:
        rows.append(
            {
                "water wt%": grade,
                "bulk density kg/m3": round(float(bulk_density_kg_m3(grade))),
                "cohesion kPa": round(float(cohesion_kpa(grade)), 1),
                "mineable unsupported m": round(
                    float(np.minimum(max_unsupported_depth_m(grade), 999.0)), 1
                ),
                "self-anchoring m": round(float(self_anchoring_depth_m(grade)), 1),
                "annual skin depth m": round(
                    float(thermal_skin_depth_m(grade, annual_period_s)), 2
                ),
                "depth for 50 mSv/yr m": round(depth_for_dose_m(50.0, grade), 2),
            }
        )
    return pd.DataFrame(rows)
