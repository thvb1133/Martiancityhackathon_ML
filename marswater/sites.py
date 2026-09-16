"""Candidate landing sites and the survey grid the model scores.

The named sites are real locations that have appeared in NASA human-landing
site studies or robotic mission site selections, with their published
coordinates and MOLA elevations. Their *observable* geophysical properties are
modelled (see ``dataset.py``) rather than measured, which is stated plainly in
the README so the provenance of every number is clear.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class NamedSite:
    name: str
    latitude_deg: float
    longitude_deg: float
    elevation_km: float
    note: str


# Coordinates and elevations from published mission and site-study literature.
NAMED_SITES: tuple[NamedSite, ...] = (
    NamedSite("Arcadia Planitia", 46.7, -168.0, -3.8,
              "Shallow ice detected by SHARAD; a leading ISRU candidate."),
    NamedSite("Deuteronilus Mensae", 43.9, 23.0, -3.3,
              "Debris-covered glaciers in the northern dichotomy boundary."),
    NamedSite("Utopia Planitia", 42.0, 110.0, -4.6,
              "Broad northern lowland with widespread ice-rich terrain."),
    NamedSite("Phlegra Montes", 38.0, 165.0, -3.0,
              "Lobate debris aprons interpreted as buried glacial ice."),
    NamedSite("Erebus Montes", 37.0, -170.0, -3.7,
              "Studied for shallow, accessible ice under thin regolith."),
    NamedSite("Milankovic Crater", 54.7, -146.7, -4.1,
              "Exposed thick ice sheet revealed in a scarp wall."),
    NamedSite("Amazonis Planitia", 15.0, -158.0, -3.9,
              "Young, very smooth lava plain; excellent landing terrain."),
    NamedSite("Jezero Crater", 18.4, 77.7, -2.6,
              "Perseverance landing site; ancient delta deposits."),
    NamedSite("Gale Crater", -4.6, 137.4, -4.5,
              "Curiosity landing site with hydrated sedimentary layers."),
    NamedSite("Meridiani Planum", -2.0, 354.0, -1.4,
              "Hematite plains explored by Opportunity."),
    NamedSite("Valles Marineris", -13.0, -59.2, -4.0,
              "Deep canyon system; high surface pressure, hard terrain."),
    NamedSite("Hellas Planitia", -42.4, 70.5, -7.2,
              "Lowest elevation on Mars; highest atmospheric pressure."),
    NamedSite("Hebrus Valles", 20.0, 126.4, -3.9,
              "Outflow channels with possible subsurface volatiles."),
    NamedSite("Elysium Planitia", 4.5, 135.9, -2.7,
              "InSight landing site; flat, low-hazard plain."),
    NamedSite("Protonilus Mensae", 43.9, 49.4, -3.6,
              "Ice-rich mantling deposits at the dichotomy boundary."),
    NamedSite("Acidalia Planitia", 50.0, -22.0, -4.3,
              "High-latitude northern plain with shallow ground ice."),
    NamedSite("Noctis Labyrinthus", -7.0, -100.0, 3.5,
              "High-standing fractured plateau; strong solar, poor ice."),
    NamedSite("Isidis Planitia", 12.9, 87.0, -3.8,
              "Large impact basin; Beagle 2 target."),
    NamedSite("Ismenius Lacus", 40.0, 0.0, -3.4,
              "Mid-latitude terrain with viscous flow features."),
    NamedSite("Nilosyrtis Mensae", 30.0, 68.0, -2.9,
              "Fretted terrain with ice-cemented fill."),
    NamedSite("Chryse Planitia", 22.5, -49.0, -3.6,
              "Viking 1 landing site at the mouth of outflow channels."),
    NamedSite("Terra Cimmeria", -34.0, 145.0, 1.2,
              "Southern highlands; rugged and heavily cratered."),
    NamedSite("Argyre Planitia", -49.7, -43.0, -5.2,
              "Southern impact basin with seasonal frost."),
    NamedSite("Olympus Mons Aureole", 23.0, -140.0, 2.1,
              "High-elevation aureole deposits; thin dust column."),
)


def named_sites_frame() -> pd.DataFrame:
    """Named candidate sites as a dataframe."""
    return pd.DataFrame(
        {
            "name": [s.name for s in NAMED_SITES],
            "latitude_deg": [s.latitude_deg for s in NAMED_SITES],
            "longitude_deg": [s.longitude_deg for s in NAMED_SITES],
            "elevation_km": [s.elevation_km for s in NAMED_SITES],
            "note": [s.note for s in NAMED_SITES],
        }
    )


def synthetic_elevation_km(latitude_deg, longitude_deg):
    """A smooth stand-in for MOLA topography.

    Reproduces the first-order shape of Mars so that elevation is spatially
    coherent rather than random: the low northern plains, the high southern
    highlands, the Tharsis rise and the Hellas basin.
    """
    lat = np.asarray(latitude_deg, dtype=float)
    lon = np.asarray(longitude_deg, dtype=float)

    # Hemispheric dichotomy: northern lowlands sit several km below the south.
    dichotomy = -3.5 * np.tanh((lat - 10.0) / 22.0)
    # Tharsis rise, centred near 0 N, 260 E (= -100 E).
    tharsis = 6.0 * np.exp(-(((lat - 2.0) / 22.0) ** 2 + ((lon + 100.0) / 28.0) ** 2))
    # Hellas basin, centred near 42 S, 70 E.
    hellas = -4.5 * np.exp(-(((lat + 42.0) / 12.0) ** 2 + ((lon - 70.0) / 16.0) ** 2))
    return dichotomy + tharsis + hellas


def survey_grid(
    lat_step_deg: float = 5.0,
    lon_step_deg: float = 10.0,
    lat_limit_deg: float = 70.0,
    seed: int = 7,
) -> pd.DataFrame:
    """A global grid of unvisited cells for the model to score."""
    rng = np.random.default_rng(seed)
    lats = np.arange(-lat_limit_deg, lat_limit_deg + 1e-9, lat_step_deg)
    lons = np.arange(-180.0, 180.0, lon_step_deg)
    lat_grid, lon_grid = np.meshgrid(lats, lons, indexing="ij")
    lat_flat = lat_grid.ravel()
    lon_flat = lon_grid.ravel()

    elevation = synthetic_elevation_km(lat_flat, lon_flat) + rng.normal(
        0.0, 0.5, size=lat_flat.size
    )

    return pd.DataFrame(
        {
            "name": [
                f"grid_{la:+.0f}_{lo:+.0f}" for la, lo in zip(lat_flat, lon_flat)
            ],
            "latitude_deg": lat_flat,
            "longitude_deg": lon_flat,
            "elevation_km": elevation,
            "note": "unsurveyed grid cell",
        }
    )
