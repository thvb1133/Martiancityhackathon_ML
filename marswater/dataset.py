"""Feature generation and the labelled survey used to train the yield model.

Real orbital datasets for this problem exist -- Mars Odyssey Neutron
Spectrometer water-equivalent hydrogen maps, TES thermal inertia, MOLA
topography, SHARAD radar soundings -- but they are multi-gigabyte PDS archives
that cannot be downloaded and georeferenced inside a single evening.

Instead this module builds a *physically motivated surrogate survey*: each grid
cell gets plausible observable properties, and its subsurface water content is
drawn from a documented stability model of Martian ground ice. The machine
learning model in ``model.py`` never sees that stability model -- it only sees
noisy observables and noisy labels, exactly as it would with real data, and has
to recover the relationship. The surrogate is stated openly in the README; it
is a stand-in for the PDS archive, not a claim of measured data.

The stability model encodes four results from the Mars literature:

1. Ground ice is thermodynamically stable within a metre of the surface
   poleward of roughly +/-50 degrees latitude (Mellon & Jakosky 1993).
2. A mid-latitude band near 30-50 degrees holds relict ice in debris-covered
   glaciers and viscous flow features, left from a higher-obliquity epoch.
3. High thermal inertia often indicates ice-cemented rather than loose
   regolith, so it correlates positively with water content.
4. Dark, low-albedo ground absorbs more sunlight, runs warmer, and loses
   shallow ice faster.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .sites import synthetic_elevation_km

FEATURE_COLUMNS: tuple[str, ...] = (
    "abs_latitude_deg",
    "elevation_km",
    "thermal_inertia",
    "albedo",
    "dust_cover_index",
    "slope_deg",
    "rock_abundance",
    "radar_dielectric_contrast",
    "summer_peak_temp_k",
    "mantling_unit_index",
)

TARGET_COLUMN = "water_equivalent_hydrogen_wt_pct"


def _summer_peak_temp_k(abs_lat, elevation_km, albedo, thermal_inertia):
    """Peak summer surface temperature, K.

    A radiative-balance approximation: insolation falls with latitude, dark
    ground absorbs more, thin high-altitude air cools less effectively, and
    high thermal inertia damps the diurnal peak.
    """
    insolation_factor = np.cos(np.radians(np.minimum(abs_lat, 89.0))) ** 0.5
    return (
        218.0
        + 62.0 * insolation_factor
        - 55.0 * albedo
        - 2.1 * elevation_km
        - 0.012 * thermal_inertia
    )


def generate_features(frame: pd.DataFrame, seed: int = 0) -> pd.DataFrame:
    """Attach plausible orbital observables to a frame of sites.

    ``frame`` must carry ``latitude_deg``, ``longitude_deg`` and
    ``elevation_km``. Observables are correlated with location in the way real
    ones are, so the resulting table is not pure noise.
    """
    required = {"latitude_deg", "longitude_deg", "elevation_km"}
    missing = required - set(frame.columns)
    if missing:
        raise KeyError(f"frame is missing required columns: {sorted(missing)}")

    rng = np.random.default_rng(seed)
    out = frame.copy().reset_index(drop=True)
    n = len(out)

    abs_lat = out["latitude_deg"].abs().to_numpy()
    elev = out["elevation_km"].to_numpy()

    # Dust mantles the low-inertia equatorial belt; polar terrain is coarser
    # and ice-cemented ground raises thermal inertia further.
    dust_cover = np.clip(
        0.955 - 0.0012 * abs_lat + 0.010 * elev + rng.normal(0, 0.015, n), 0.80, 0.99
    )
    thermal_inertia = np.clip(
        120.0
        + 3.4 * abs_lat
        - 240.0 * (dust_cover - 0.90)
        + rng.normal(0, 45.0, n),
        24.0,
        800.0,
    )
    albedo = np.clip(
        0.17 + 0.42 * (dust_cover - 0.90) + 0.0011 * abs_lat + rng.normal(0, 0.028, n),
        0.07,
        0.40,
    )
    # Cratered southern highlands are rougher than resurfaced northern plains.
    slope = np.clip(
        np.abs(rng.gamma(shape=1.9, scale=1.5, size=n))
        + 0.9 * np.maximum(elev, 0.0)
        + 0.03 * np.maximum(-out["latitude_deg"].to_numpy(), 0.0),
        0.05,
        40.0,
    )
    rock_abundance = np.clip(
        0.055 + 0.011 * slope + rng.normal(0, 0.030, n), 0.005, 0.60
    )

    summer_peak = _summer_peak_temp_k(abs_lat, elev, albedo, thermal_inertia)

    # Regional geology. Mars is not zonally uniform: the latitude-dependent
    # mantling deposit is thick and ice-rich over Arcadia and Utopia and thin
    # over other longitudes at the same latitude. This index stands in for a
    # mapped geologic unit, so it carries information latitude alone does not.
    lon_rad = np.radians(out["longitude_deg"].to_numpy())
    mantling = np.clip(
        0.5
        + 0.34 * np.cos(lon_rad + np.radians(168.0))
        + 0.18 * np.cos(2 * lon_rad - np.radians(40.0))
        + rng.normal(0, 0.05, n),
        0.0,
        1.0,
    )

    out["abs_latitude_deg"] = abs_lat
    out["thermal_inertia"] = thermal_inertia
    out["albedo"] = albedo
    out["dust_cover_index"] = dust_cover
    out["slope_deg"] = slope
    out["rock_abundance"] = rock_abundance
    out["summer_peak_temp_k"] = summer_peak
    out["mantling_unit_index"] = mantling

    # Radar dielectric contrast responds to buried ice, so it is genuinely
    # informative, but a real SHARAD return is ambiguous between clean ice and
    # porous dry rock. Generated from latent truth, then corrupted.
    latent = latent_water_content(out)
    out["radar_dielectric_contrast"] = np.clip(
        0.45 * latent + rng.normal(0, 2.0, n), 0.0, None
    )

    return out


def latent_water_content(frame: pd.DataFrame) -> np.ndarray:
    """The 'ground truth' water-equivalent hydrogen field, in weight percent.

    This is the relationship the ML model has to discover. It is never exposed
    as a feature and never used at prediction time.
    """
    abs_lat = frame["abs_latitude_deg"].to_numpy()
    elev = frame["elevation_km"].to_numpy()
    ti = frame["thermal_inertia"].to_numpy()
    albedo = frame["albedo"].to_numpy()
    mantling = frame["mantling_unit_index"].to_numpy()

    # (1) Thermodynamic stability of shallow ice, switching on near 50 deg.
    stability = 1.0 / (1.0 + np.exp(-(abs_lat - 50.0) / 5.5))
    polar_reservoir = 24.0 * stability

    # (2) Relict mid-latitude glacial ice, peaking near 42 deg, but only where
    # the mantling deposit is actually present. This is the key interaction:
    # latitude says where ice *could* survive, and the geologic unit says
    # whether any was ever emplaced there. Neither feature alone is enough.
    glacial_band = (
        30.0 * np.exp(-(((abs_lat - 42.0) / 9.5) ** 2)) * (mantling**1.4)
    )

    # (3) Ice-cemented ground raises thermal inertia, but only where ice can
    # survive; over dry equatorial ground high inertia just means bare rock.
    cementation = 0.045 * (ti - 190.0) * np.clip(stability + 0.55 * mantling, 0, 1)

    # (4) Warm dark ground desiccates; cold high ground preserves.
    thermal_loss = -16.0 * (albedo < 0.145) * (1.0 - stability)
    elevation_bonus = 0.55 * elev * (1.0 - 0.6 * stability)

    # Equatorial hydrated minerals: chemically bound water in sulphates and
    # clays rather than mineable ice, so the floor stays low but nonzero.
    bound_water = 2.4 * np.exp(-(((abs_lat - 5.0) / 14.0) ** 2))

    weh = (
        polar_reservoir
        + glacial_band
        + cementation
        + thermal_loss
        + elevation_bonus
        + bound_water
    )
    return np.clip(weh, 0.5, 60.0)


def labelled_survey(
    n_samples: int = 4200, seed: int = 42, noise_scale: float = 1.0
) -> pd.DataFrame:
    """Build the training survey: observables plus noisy measured labels.

    Measurement noise grows with water content, mirroring a neutron
    spectrometer whose counting statistics degrade over the wettest ground.
    """
    rng = np.random.default_rng(seed)

    # Sample locations continuously rather than on the display grid, so the
    # evaluation grid is genuinely unseen.
    lat = rng.uniform(-75.0, 75.0, n_samples)
    lon = rng.uniform(-180.0, 180.0, n_samples)

    # Same synthetic areoid the map uses, so training and display topography
    # are consistent.
    elev = synthetic_elevation_km(lat, lon) + rng.normal(0, 0.5, n_samples)

    base = pd.DataFrame(
        {
            "name": [f"survey_{i:05d}" for i in range(n_samples)],
            "latitude_deg": lat,
            "longitude_deg": lon,
            "elevation_km": elev,
        }
    )
    featured = generate_features(base, seed=seed)

    truth = latent_water_content(featured)
    noise = rng.normal(0.0, noise_scale * (0.9 + 0.11 * truth))
    featured[TARGET_COLUMN] = np.clip(truth + noise, 0.1, None)
    featured["latent_truth_wt_pct"] = truth

    return featured
