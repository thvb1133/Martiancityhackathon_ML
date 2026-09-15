"""Underground architecture: how deep to build, and what the ground will carry.

The surface of Mars is the worst place on the planet to put a house. It takes
roughly 230 mSv of cosmic radiation a year, swings 90 K between afternoon and
dawn, and offers nothing to hold a pressure vessel down. Everything that makes
a habitat liveable -- shielding, thermal stability, structural mass -- is
available a few metres below it, for free, in the material already there.

So the architectural question is not what shape the dome should be. It is *how
deep*, and that turns out to be a decision the water model already knows how
to make. Pore ice is what separates the two Martian ground materials:

    Dry regolith is a loose, weak, superbly insulating sand. It cannot hold an
    unsupported roof, so a vault has to be placed in an open trench and buried,
    and the pressure shell has to be flown from Earth because nothing on site
    will resist the internal pressure.

    Ice-cemented regolith is a dense, strong, thermally conductive rock. It
    will hold a mined vault open, and at the depth where its own weight exceeds
    the habitat's internal pressure the shell stops being a pressure vessel and
    becomes a gas-tight liner. But it conducts heat sixty times better, and if
    the habitat warms the rock around it above about 263 K the cement the vault
    is standing in begins to go.

Those two materials want opposite buildings, and which one is under a given
site is exactly what ``model.py`` predicts. This module turns that prediction
into a depth, a construction method, a shell thickness and a bill of landed
mass -- and reports what the same decision would have cost if it had been made
by the obvious guess instead.

Sign conventions: depth is always measured to the *crown* of the vault, in
metres below original grade. Masses are kilograms landed from Earth; energies
are kilowatt-hours drawn from the same surface power system that ``simulate.py``
sizes for the water plant, because on a real settlement there is only one grid.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from functools import lru_cache

import numpy as np
import pandas as pd

from . import constants as C
from .physics import (
    EXCAVATION_KWH_PER_KG_REGOLITH,
    REGOLITH_SPECIFIC_HEAT_J_KG_K,
    daily_insolation_kwh_m2,
)

STEFAN_BOLTZMANN = 5.670374419e-8
REGOLITH_EMISSIVITY = 0.95
#: Carbon dioxide condenses out of the atmosphere below this, which puts a
#: floor under how cold bare ground can get in polar winter.
CO2_FROST_POINT_K = 148.0

BERM = "surface vault under a regolith berm"
CUT_AND_COVER = "cut-and-cover buried vault"
MINED = "mined vault in ice-cemented ground"
MINED_SINTERED = "mined vault with sintered regolith support"

#: Construction methods in the order they are tried. All four are evaluated at
#: every depth; the optimiser picks between them on landed mass.
METHODS: tuple[str, ...] = (BERM, CUT_AND_COVER, MINED, MINED_SINTERED)

#: Spoil handled per cubic metre excavated. A berm is placed once. A trench is
#: dug out and then backfilled, so every cubic metre is moved twice with
#: re-handling losses on top.
HANDLING_FACTOR: dict[str, float] = {
    BERM: 1.0,
    CUT_AND_COVER: 1.8,
    MINED: 1.0,
    MINED_SINTERED: 1.0,
}

ACCESS_SHAFT_RADIUS_M = 2.5
#: Mined openings need more than the vault itself: cross-drifts, a plant
#: chamber, an airlock gallery and a second means of escape.
MINED_ANCILLARY_FRACTION = 0.15


# ---------------------------------------------------------------------------
# What the ground is made of
# ---------------------------------------------------------------------------
def pore_ice_saturation(weh_wt_pct):
    """Fraction of the pore space filled with ice, from 0 to 1."""
    water = np.clip(np.asarray(weh_wt_pct, dtype=float), 0.0, None) / 100.0
    return np.clip(water / (C.PORE_ICE_SATURATION_WT_PCT / 100.0), 0.0, 1.0)


def cementation_index(weh_wt_pct):
    """How far the ground is from loose sand toward ice-cemented rock.

    Zero below the percolation threshold, where the ice sits in isolated pore
    necks and bridges no grains, rising to one when the pores are full.
    """
    water = np.clip(np.asarray(weh_wt_pct, dtype=float), 0.0, None)
    span = C.PORE_ICE_SATURATION_WT_PCT - C.ICE_CEMENT_ONSET_WT_PCT
    return np.clip((water - C.ICE_CEMENT_ONSET_WT_PCT) / span, 0.0, 1.0)


def bulk_density_kg_m3(weh_wt_pct):
    """Bulk density of the ground, kg/m^3.

    Water held at ``w`` mass fraction adds to the rock it sits in, so density
    rises as ``rho_dry / (1 - w)`` until the pores are full. This is a small
    effect -- around 25 per cent across the full range -- but it works in the
    settlement's favour twice over: denser ground shields better per metre dug,
    and it reaches the self-anchoring depth sooner.
    """
    water = np.clip(
        np.asarray(weh_wt_pct, dtype=float), 0.0, C.PORE_ICE_SATURATION_WT_PCT
    ) / 100.0
    return C.REGOLITH_DRY_BULK_DENSITY_KG_M3 / (1.0 - water)


def cohesion_kpa(weh_wt_pct):
    """Cohesion of the ground, kPa.

    This single quantity decides whether the settlement can mine a vault or
    has to dig a trench, and it spans nearly three orders of magnitude between
    the two Martian ground materials. The exponent above the cementation
    threshold is steeper than linear because strength develops as the ice
    bridges percolate into a connected load path.
    """
    return C.REGOLITH_DRY_COHESION_KPA + (
        C.ICE_CEMENTED_COHESION_KPA - C.REGOLITH_DRY_COHESION_KPA
    ) * cementation_index(weh_wt_pct) ** 1.8


def thermal_conductivity_w_m_k(weh_wt_pct):
    """Thermal conductivity of the ground, W/m/K.

    Dry regolith at 6 mbar conducts about as well as a vacuum flask because
    the gas in its pores is too thin to carry heat. Pore ice short-circuits
    that, which is why the geometric interpolation spans a factor of sixty.
    """
    ratio = C.ICE_CEMENTED_CONDUCTIVITY_W_M_K / C.REGOLITH_DRY_CONDUCTIVITY_W_M_K
    return C.REGOLITH_DRY_CONDUCTIVITY_W_M_K * ratio ** cementation_index(weh_wt_pct)


def volumetric_heat_capacity_j_m3_k(weh_wt_pct):
    """Heat capacity per cubic metre of ground, J/m^3/K."""
    water = np.clip(
        np.asarray(weh_wt_pct, dtype=float), 0.0, C.PORE_ICE_SATURATION_WT_PCT
    ) / 100.0
    specific_heat = (
        (1.0 - water) * REGOLITH_SPECIFIC_HEAT_J_KG_K
        + water * C.ICE_SPECIFIC_HEAT_J_KG_K
    )
    return bulk_density_kg_m3(weh_wt_pct) * specific_heat


def thermal_diffusivity_m2_s(weh_wt_pct):
    """Thermal diffusivity, m^2/s."""
    return thermal_conductivity_w_m_k(weh_wt_pct) / volumetric_heat_capacity_j_m3_k(
        weh_wt_pct
    )


def thermal_inertia_from_water(weh_wt_pct):
    """Thermal inertia implied by the water content, J m^-2 K^-1 s^-1/2.

    Provided as a consistency check rather than as a model input: the orbital
    thermal inertia is an *observable* the water model is trained on, so
    recomputing it from the prediction is a way of confirming the two agree.
    """
    return np.sqrt(
        thermal_conductivity_w_m_k(weh_wt_pct)
        * volumetric_heat_capacity_j_m3_k(weh_wt_pct)
    )


# ---------------------------------------------------------------------------
# Heat: how far down the surface stops happening
# ---------------------------------------------------------------------------
def thermal_skin_depth_m(weh_wt_pct, period_s: float):
    """Depth at which a surface temperature wave falls to 1/e of its amplitude.

    The classic diffusion result, ``sqrt(alpha * P / pi)``. Both Martian cycles
    matter and they behave very differently: the diurnal wave dies within a few
    centimetres, so almost any burial removes it, while the annual wave reaches
    metres and is what actually sets the depth of a stable habitat.
    """
    return np.sqrt(thermal_diffusivity_m2_s(weh_wt_pct) * period_s / np.pi)


def surface_diurnal_swing_k(thermal_inertia: float) -> float:
    """Peak-to-trough surface temperature range over one sol, K.

    An empirical parameterisation of the Martian diurnal range against thermal
    inertia: dusty low-inertia ground at Gale swings close to 90 K, while
    rocky or ice-cemented high-inertia ground swings appreciably less because
    it stores the afternoon's heat instead of radiating it straight back.
    """
    inertia = max(float(thermal_inertia), 20.0)
    return float(np.clip(110.0 * (200.0 / inertia) ** 0.4, 25.0, 130.0))


def surface_temperature_profile(
    latitude_deg: float,
    albedo: float,
    elevation_km: float = 0.0,
    optical_depth: float = C.TAU_CLEAR,
    n_seasons: int = 24,
) -> tuple[float, float]:
    """Annual mean surface temperature and seasonal swing, both in K.

    Radiative equilibrium against the sol-averaged insolation already computed
    in ``physics.py``, sampled around the orbit. The mean is what a deep
    habitat sees as its far-field boundary condition; the swing is the wave it
    has to be buried beneath.
    """
    solar_longitudes = np.linspace(0.0, 360.0, n_seasons, endpoint=False)
    insolation = daily_insolation_kwh_m2(
        latitude_deg, solar_longitudes, optical_depth, elevation_km
    )
    flux = np.asarray(insolation, dtype=float) * 3.6e6 / C.SOL_LENGTH_S
    equilibrium = (
        (1.0 - float(albedo)) * flux / (REGOLITH_EMISSIVITY * STEFAN_BOLTZMANN)
    ) ** 0.25
    equilibrium = np.maximum(equilibrium, CO2_FROST_POINT_K)
    return float(equilibrium.mean()), float(equilibrium.max() - equilibrium.min())


def temperature_swing_at_depth_k(
    depth_m,
    weh_wt_pct: float,
    diurnal_swing_k: float,
    annual_swing_k: float,
) -> float:
    """Residual peak-to-trough temperature variation at depth, K.

    Both waves are attenuated through their own skin depths and summed. The
    annual term dominates below the first few centimetres, and because
    ice-cemented ground is far more diffusive its annual skin depth is metres
    rather than centimetres -- so a wet site has to be dug *deeper* to reach
    the same thermal quiet as a dry one. That is the first of two ways the
    water prediction pushes the answer downward.
    """
    depth = np.asarray(depth_m, dtype=float)
    diurnal = thermal_skin_depth_m(weh_wt_pct, C.SOL_LENGTH_S)
    annual = thermal_skin_depth_m(weh_wt_pct, C.MARS_YEAR_SOLS * C.SOL_LENGTH_S)
    return diurnal_swing_k * np.exp(-depth / diurnal) + annual_swing_k * np.exp(
        -depth / annual
    )


def depth_for_thermal_stability_m(
    weh_wt_pct: float,
    diurnal_swing_k: float,
    annual_swing_k: float,
    tolerance_k: float,
    search_limit_m: float = 60.0,
) -> float:
    """Shallowest depth at which the ground stops changing temperature."""
    depths = np.linspace(0.0, search_limit_m, 2401)
    swing = temperature_swing_at_depth_k(
        depths, weh_wt_pct, diurnal_swing_k, annual_swing_k
    )
    within = np.flatnonzero(swing <= tolerance_k)
    return float(depths[within[0]]) if within.size else math.inf


# ---------------------------------------------------------------------------
# Radiation: the reason to be underground at all
# ---------------------------------------------------------------------------
def areal_density_g_cm2(depth_m, weh_wt_pct):
    """Shielding mass above a given depth, g/cm^2.

    Radiation transport does not care about metres, it cares about how much
    matter the particle has to cross, so every dose calculation here is in
    areal density and depth is only a way of buying it.
    """
    density_g_cm3 = bulk_density_kg_m3(weh_wt_pct) / 1000.0
    return density_g_cm3 * np.asarray(depth_m, dtype=float) * 100.0


def gcr_dose_msv_per_year(depth_m, weh_wt_pct):
    """Galactic cosmic ray dose equivalent under regolith, mSv/yr.

    Two terms. Primaries attenuate exponentially. Secondaries -- mostly
    neutrons knocked out of the shielding by the primaries it stops -- build up
    from zero, peak at a few tens of g/cm^2, and then die away. Their sum has a
    genuinely awkward consequence for architecture: over roughly the first
    third of a metre, the dose barely falls, because the shield is producing
    almost as much radiation as it absorbs. Thin shielding is close to a waste
    of digging, which is an argument for committing to depth rather than
    compromising on it.
    """
    x = areal_density_g_cm2(depth_m, weh_wt_pct)
    primary = np.exp(-x / C.GCR_PRIMARY_ATTENUATION_G_CM2)
    secondary = (
        C.GCR_SECONDARY_AMPLITUDE
        * (x / C.GCR_SECONDARY_ATTENUATION_G_CM2)
        * np.exp(-x / C.GCR_SECONDARY_ATTENUATION_G_CM2)
    )
    return C.GCR_SURFACE_DOSE_MSV_PER_YEAR * (primary + secondary)


@lru_cache(maxsize=4096)
def depth_for_dose_m(
    target_msv_per_year: float,
    weh_wt_pct: float,
    search_limit_m: float = 30.0,
) -> float:
    """Shallowest burial depth meeting a dose limit, m.

    Scanned rather than solved because the dose profile is not monotonic near
    the surface -- secondary buildup makes it rise before it falls -- so a
    bisection would be entitled to return the wrong root.
    """
    depths = np.linspace(0.0, search_limit_m, 3001)
    dose = gcr_dose_msv_per_year(depths, weh_wt_pct)
    within = np.flatnonzero(dose <= target_msv_per_year)
    return float(depths[within[0]]) if within.size else math.inf


def useless_shielding_depth_m(weh_wt_pct: float) -> float:
    """Depth at which secondary buildup peaks: the worst shielding to stop at."""
    depths = np.linspace(0.0, 2.0, 801)
    return float(depths[int(np.argmax(gcr_dose_msv_per_year(depths, weh_wt_pct)))])


# ---------------------------------------------------------------------------
# Structure: weight instead of steel
# ---------------------------------------------------------------------------
def overburden_pressure_kpa(depth_m, weh_wt_pct):
    """Vertical stress from the ground above, kPa."""
    return (
        bulk_density_kg_m3(weh_wt_pct)
        * C.MARS_SURFACE_GRAVITY_M_S2
        * np.asarray(depth_m, dtype=float)
        / 1000.0
    )


def self_anchoring_depth_m(
    weh_wt_pct, internal_pressure_kpa: float = C.HABITAT_PRESSURE_KPA
):
    """Depth at which overburden weight cancels the habitat's internal pressure.

    Above it, a habitat is a pressure vessel: something has to hold 55 kPa of
    air in against vacuum, and on Mars that something is flown from Earth.
    Below it, the ground's own weight is doing the work, the net load on the
    enclosure falls to zero, and the structure collapses -- in the good sense
    -- from a pressure shell into a gas-tight liner. In dry regolith the
    crossover is 9.2 m; in ice-cemented ground it is 7.4 m, because the ice
    makes the overburden heavier.
    """
    return (
        internal_pressure_kpa
        * 1000.0
        / (bulk_density_kg_m3(weh_wt_pct) * C.MARS_SURFACE_GRAVITY_M_S2)
    )


def stability_number(depth_m, weh_wt_pct):
    """Overburden stress over cohesion: the soft-ground tunnelling criterion."""
    return overburden_pressure_kpa(depth_m, weh_wt_pct) / cohesion_kpa(weh_wt_pct)


def max_unsupported_depth_m(
    weh_wt_pct, stability_limit: float = C.TUNNEL_STABILITY_NUMBER
):
    """Deepest an opening can be mined and still stand without support, m.

    This is the quantity that decides the building. It is about 5 m in dry
    regolith -- short of the 9.2 m where the pressure shell would have become
    unnecessary -- and effectively unlimited once pore ice cements the ground.
    A map of this number is a map of where a Martian city can be mined instead
    of assembled, and it is produced entirely from the water model's output.
    Ground below the cementation threshold returns zero rather than a small
    depth: an uncemented span does not stand briefly, it does not stand.
    """
    depth = (
        stability_limit
        * cohesion_kpa(weh_wt_pct)
        * 1000.0
        / (bulk_density_kg_m3(weh_wt_pct) * C.MARS_SURFACE_GRAVITY_M_S2)
    )
    return np.where(cementation_index(weh_wt_pct) > 0.0, depth, 0.0)


# ---------------------------------------------------------------------------
# Geometry and configuration
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class VaultGeometry:
    """One habitat vault: a horizontal cylinder with domed ends."""

    radius_m: float = 6.0
    length_m: float = 40.0
    volume_per_person_m3: float = 60.0

    @property
    def span_m(self) -> float:
        return 2.0 * self.radius_m

    @property
    def pressurised_volume_m3(self) -> float:
        return math.pi * self.radius_m**2 * self.length_m

    @property
    def enclosure_area_m2(self) -> float:
        """Area to be shelled, lined and insulated, including the end caps."""
        return (
            2.0 * math.pi * self.radius_m * self.length_m
            + 2.0 * math.pi * self.radius_m**2
        )

    @property
    def plan_area_m2(self) -> float:
        return self.span_m * self.length_m

    @property
    def crew_capacity(self) -> float:
        return self.pressurised_volume_m3 / self.volume_per_person_m3


@dataclass(frozen=True)
class BurialConfig:
    """Design limits for the habitat, and the campaign it has to fit inside."""

    dose_limit_msv_per_year: float = C.DOSE_LIMIT_MSV_PER_YEAR
    temperature_swing_tolerance_k: float = 2.0
    internal_pressure_kpa: float = C.HABITAT_PRESSURE_KPA
    ground_loss_budget_kw: float = C.HABITAT_GROUND_LOSS_BUDGET_KW
    build_window_sols: float = C.SYNOD_SOLS
    max_excavator_fleet: int = C.MAX_EXCAVATOR_FLEET
    stability_limit: float = C.TUNNEL_STABILITY_NUMBER
    #: How far past the unsupported limit sintered ground support can reach.
    #: Kept deliberately modest: support has to be installed into an opening
    #: that is already standing, so sintering buys a margin on cemented ground
    #: rather than a licence to mine anything.
    sintered_support_stability_multiple: float = 1.5
    optical_depth: float = C.TAU_CLEAR
    geometry: VaultGeometry = field(default_factory=VaultGeometry)
    depth_step_m: float = 0.25
    max_depth_m: float = 20.0

    @property
    def candidate_depths_m(self) -> np.ndarray:
        return np.arange(
            self.depth_step_m,
            self.max_depth_m + 1e-9,
            self.depth_step_m,
        )


@dataclass(frozen=True)
class HabitatDesign:
    """One fully specified underground habitat, with its bill of materials."""

    site_name: str
    population: int
    water_grade_wt_pct: float
    method: str
    depth_m: float
    vaults: int

    dose_msv_per_year: float
    temperature_swing_k: float
    annual_skin_depth_m: float
    ground_far_field_temp_k: float

    overburden_kpa: float
    net_pressure_kpa: float
    shell_thickness_mm: float
    stability_number: float

    shell_mass_kg: float
    liner_mass_kg: float
    insulation_thickness_m: float
    insulation_mass_kg: float
    excavator_units: int
    excavator_mass_kg: float

    excavated_m3: float
    excavated_mass_kg: float
    excavation_energy_kwh: float
    sintering_energy_kwh: float
    imported_shielding_equivalent_kg: float

    feasible: bool
    limiting_factor: str
    #: One of ``radiation``, ``thermal``, ``ground strength``, ``excavation``
    #: or ``none``. Kept alongside the human-readable string so that failures
    #: can be counted by cause without parsing prose.
    limiting_category: str

    @property
    def mass_breakdown_kg(self) -> dict[str, float]:
        return {
            "Pressure shell": self.shell_mass_kg,
            "Gas-tight liner": self.liner_mass_kg,
            "Insulation": self.insulation_mass_kg,
            "Excavation fleet": self.excavator_mass_kg,
        }

    @property
    def landed_mass_kg(self) -> float:
        return sum(self.mass_breakdown_kg.values())

    @property
    def launches(self) -> float:
        return self.landed_mass_kg / C.STARSHIP_PAYLOAD_KG

    @property
    def construction_energy_kwh(self) -> float:
        return self.excavation_energy_kwh + self.sintering_energy_kwh

    @property
    def mass_saved_vs_imported_shielding_kg(self) -> float:
        """What not flying the shielding is worth.

        The honest comparison for an underground habitat is not another
        underground habitat, it is the alternative of landing the shielding.
        Matching the same dose limit with material brought from Earth means
        flying the same areal density, which is measured in Starships per
        habitat rather than tonnes.
        """
        return self.imported_shielding_equivalent_kg - self.landed_mass_kg

    @property
    def is_mined(self) -> bool:
        return self.method in (MINED, MINED_SINTERED)


# ---------------------------------------------------------------------------
# Costing one option
# ---------------------------------------------------------------------------
def _net_enclosure_pressure_kpa(
    method: str, depth_m: float, weh_wt_pct: float, internal_kpa: float
) -> float:
    """Governing pressure the enclosure must carry by itself, kPa.

    The three cases differ in who carries the weight of the ground, and that
    is the whole structural argument for mining.

    A berm does not confine the vault's sides, so the shell still has to hold
    the full internal pressure, and burying it deeper only piles more dead load
    on the crown.

    A backfilled trench is worse than it looks. Loose fill cannot arch, so when
    the habitat is depressurised for maintenance the shell carries the entire
    overburden. Cut-and-cover therefore wants to be as shallow as the dose
    limit allows.

    A mined vault in competent ground is the exception: the rock arches over
    the opening and carries its own weight, so the enclosure sees only the
    difference between inside and outside. At the self-anchoring depth that
    difference is zero.
    """
    overburden = float(overburden_pressure_kpa(depth_m, weh_wt_pct))
    if method == BERM:
        return max(internal_kpa, overburden)
    if method == CUT_AND_COVER:
        return max(internal_kpa - overburden, overburden)
    return max(0.0, internal_kpa - overburden)


def _shell_thickness_m(net_pressure_kpa: float, radius_m: float) -> float:
    """Membrane thickness for a cylinder under a net pressure difference.

    Thin-wall hoop stress with a safety factor of two, floored at the minimum
    gauge a shell can be manufactured and handled in. Sizing the external
    pressure cases as a membrane is optimistic -- a real depressurised buried
    shell would need stiffening against buckling -- so the trench option here
    is being flattered rather than penalised.
    """
    hoop = (
        C.PRESSURE_SHELL_SAFETY_FACTOR
        * net_pressure_kpa
        * 1000.0
        * radius_m
        / C.PRESSURE_SHELL_ALLOWABLE_STRESS_PA
    )
    return max(C.PRESSURE_SHELL_MIN_GAUGE_M, hoop)


def _excavated_volume_m3(
    method: str, depth_m: float, geometry: VaultGeometry
) -> float:
    """Ground moved per vault, m^3.

    The berm and the trench are the same shape of problem: a 12 m diameter
    vault is a tall object, and covering or burying it means a prism whose side
    slopes stand at the angle of repose, so the volume grows with the square of
    the height. Mining moves only the vault itself plus its access.
    """
    cot_repose = 1.0 / math.tan(math.radians(C.REGOLITH_ANGLE_OF_REPOSE_DEG))
    span = geometry.span_m
    length = geometry.length_m
    vault_volume = geometry.pressurised_volume_m3

    if method == BERM:
        height = depth_m + span
        prism = length * (span * height + cot_repose * height**2)
        return max(prism - vault_volume, depth_m * geometry.plan_area_m2)

    if method == CUT_AND_COVER:
        trench_depth = depth_m + span
        return length * (span * trench_depth + cot_repose * trench_depth**2)

    shaft = math.pi * ACCESS_SHAFT_RADIUS_M**2 * (depth_m + geometry.radius_m)
    return vault_volume * (1.0 + MINED_ANCILLARY_FRACTION) + shaft


def _ground_thermal_resistance_m2k_w(
    method: str, depth_m: float, weh_wt_pct: float, geometry: VaultGeometry
) -> float:
    """Resistance from the enclosure wall to the far-field ground, m^2K/W.

    For a buried cylinder the steady conduction path has a characteristic
    length of ``R ln(2d/R)``; for a bermed vault the path is simply the cover
    thickness. Dry regolith makes this enormous, which is why a dry site needs
    no insulation at all, and why a wet one needs a great deal.
    """
    conductivity = float(thermal_conductivity_w_m_k(weh_wt_pct))
    if method == BERM:
        return max(depth_m, 0.05) / conductivity
    centre_depth = depth_m + geometry.radius_m
    shape = max(math.log(2.0 * centre_depth / geometry.radius_m), 0.2)
    return geometry.radius_m * shape / conductivity


def required_insulation_r_m2k_w(
    method: str,
    depth_m: float,
    weh_wt_pct: float,
    ground_temp_k: float,
    geometry: VaultGeometry,
    config: BurialConfig,
) -> float:
    """Thermal resistance the habitat must add, m^2K/W.

    Two constraints, and at an ice-cemented site the second is the one that
    bites. The first is a power budget: only so much heat may be allowed to
    conduct away into the ground. The second is structural, and is the price of
    building in ice -- the rock face behind the liner has to stay below about
    263 K, because the habitat is standing in the cement and warming it up
    would dissolve the structure it is relying on. A habitat in ice has to be
    insulated from its own building.
    """
    area = geometry.enclosure_area_m2
    ground_r = _ground_thermal_resistance_m2k_w(method, depth_m, weh_wt_pct, geometry)
    drop = C.HABITAT_INTERIOR_TEMP_K - ground_temp_k
    if drop <= 0.0:
        return 0.0

    budget_flux = config.ground_loss_budget_kw * 1000.0 / area
    required = drop / budget_flux - ground_r

    if float(cementation_index(weh_wt_pct)) > 0.0:
        headroom = C.ICE_STABILITY_INTERFACE_TEMP_K - ground_temp_k
        if headroom <= 0.0:
            return max(required, 0.0)
        ice_flux = headroom / ground_r
        required = max(required, drop / ice_flux - ground_r)

    return max(required, 0.0)


def evaluate_option(
    site_name: str,
    population: int,
    weh_wt_pct: float,
    method: str,
    depth_m: float,
    diurnal_swing_k: float,
    annual_swing_k: float,
    ground_temp_k: float,
    config: BurialConfig,
) -> HabitatDesign:
    """Cost one construction method at one depth for one crew."""
    if population < 1:
        raise ValueError("population must be at least 1")
    if method not in METHODS:
        raise ValueError(f"unknown construction method: {method!r}")

    geometry = config.geometry
    vaults = int(math.ceil(population / geometry.crew_capacity))
    area = geometry.enclosure_area_m2

    dose = float(gcr_dose_msv_per_year(depth_m, weh_wt_pct))
    swing = float(
        temperature_swing_at_depth_k(
            depth_m, weh_wt_pct, diurnal_swing_k, annual_swing_k
        )
    )
    overburden = float(overburden_pressure_kpa(depth_m, weh_wt_pct))
    net_pressure = _net_enclosure_pressure_kpa(
        method, depth_m, weh_wt_pct, config.internal_pressure_kpa
    )
    thickness = _shell_thickness_m(net_pressure, geometry.radius_m)
    shell_mass = thickness * area * C.PRESSURE_SHELL_DENSITY_KG_M3 * vaults
    liner_mass = C.GAS_TIGHT_LINER_KG_M2 * area * vaults

    insulation_r = required_insulation_r_m2k_w(
        method, depth_m, weh_wt_pct, ground_temp_k, geometry, config
    )
    insulation_thickness = insulation_r * C.INSULATION_CONDUCTIVITY_W_M_K
    insulation_mass = (
        insulation_thickness * C.INSULATION_DENSITY_KG_M3 * area * vaults
    )

    volume = _excavated_volume_m3(method, depth_m, geometry) * vaults
    excavated_mass = volume * float(bulk_density_kg_m3(weh_wt_pct))
    excavation_energy = (
        excavated_mass * EXCAVATION_KWH_PER_KG_REGOLITH * HANDLING_FACTOR[method]
    )
    throughput = excavated_mass / max(config.build_window_sols, 1.0)
    excavators = int(math.ceil(throughput / C.EXCAVATOR_UNIT_THROUGHPUT_KG_PER_SOL))

    sintering_energy = 0.0
    if method == MINED_SINTERED:
        sintered_mass = (
            C.SINTERED_SUPPORT_THICKNESS_M
            * area
            * float(bulk_density_kg_m3(weh_wt_pct))
            * vaults
        )
        sintering_energy = sintered_mass * C.SINTER_ENERGY_KWH_PER_KG

    shielding_areal = float(
        areal_density_g_cm2(
            depth_for_dose_m(config.dose_limit_msv_per_year, weh_wt_pct), weh_wt_pct
        )
    )
    if not math.isfinite(shielding_areal):
        shielding_areal = 0.0
    imported_equivalent = shielding_areal * 10.0 * geometry.plan_area_m2 * vaults

    number = float(stability_number(depth_m, weh_wt_pct))
    feasible, limiting, category = _verdict(
        method, depth_m, dose, swing, number, excavators, weh_wt_pct, config
    )

    return HabitatDesign(
        site_name=site_name,
        population=population,
        water_grade_wt_pct=float(weh_wt_pct),
        method=method,
        depth_m=float(depth_m),
        vaults=vaults,
        dose_msv_per_year=dose,
        temperature_swing_k=swing,
        annual_skin_depth_m=float(
            thermal_skin_depth_m(weh_wt_pct, C.MARS_YEAR_SOLS * C.SOL_LENGTH_S)
        ),
        ground_far_field_temp_k=float(ground_temp_k),
        overburden_kpa=overburden,
        net_pressure_kpa=net_pressure,
        shell_thickness_mm=thickness * 1000.0,
        stability_number=number,
        shell_mass_kg=shell_mass,
        liner_mass_kg=liner_mass,
        insulation_thickness_m=insulation_thickness,
        insulation_mass_kg=insulation_mass,
        excavator_units=excavators,
        excavator_mass_kg=excavators * C.EXCAVATOR_UNIT_MASS_KG,
        excavated_m3=volume,
        excavated_mass_kg=excavated_mass,
        excavation_energy_kwh=excavation_energy,
        sintering_energy_kwh=sintering_energy,
        imported_shielding_equivalent_kg=imported_equivalent,
        feasible=feasible,
        limiting_factor=limiting,
        limiting_category=category,
    )


def _verdict(
    method: str,
    depth_m: float,
    dose: float,
    swing: float,
    number: float,
    excavators: int,
    weh_wt_pct: float,
    config: BurialConfig,
) -> tuple[bool, str, str]:
    """Whether one option is buildable, and what stops it if not."""
    if dose > config.dose_limit_msv_per_year:
        return False, (
            f"radiation: {dose:.0f} mSv/yr at {depth_m:.2f} m, above the "
            f"{config.dose_limit_msv_per_year:.0f} mSv/yr design limit"
        ), "radiation"
    if swing > config.temperature_swing_tolerance_k:
        return False, (
            f"thermal: ground still swings {swing:.1f} K at {depth_m:.2f} m, "
            f"above the {config.temperature_swing_tolerance_k:.1f} K tolerance"
        ), "thermal"
    if method in (MINED, MINED_SINTERED) and float(
        cementation_index(weh_wt_pct)
    ) <= 0.0:
        return False, (
            f"ground strength: at {weh_wt_pct:.1f} wt% water the pore ice "
            "bridges nothing, and a cohesionless 12 m span cannot be held open "
            "long enough to be lined -- this ground has to be trenched, not mined"
        ), "ground strength"
    if method == MINED and number > config.stability_limit:
        return False, (
            f"ground strength: stability number {number:.1f} at {depth_m:.2f} m "
            f"exceeds {config.stability_limit:.0f}, so an unsupported vault will "
            f"not stand in {weh_wt_pct:.1f} wt% ground"
        ), "ground strength"
    if method == MINED_SINTERED and number > (
        config.stability_limit * config.sintered_support_stability_multiple
    ):
        return False, (
            f"ground strength: stability number {number:.1f} is beyond what "
            "sintered support can hold open"
        ), "ground strength"
    if excavators > config.max_excavator_fleet:
        return False, (
            f"excavation: {excavators} machines needed to finish inside one "
            f"launch window, above the {config.max_excavator_fleet}-unit "
            "maintenance limit"
        ), "excavation"
    return True, _driver(method, depth_m, number, config), "none"


def _driver(
    method: str, depth_m: float, number: float, config: BurialConfig
) -> str:
    """A short description of why this option is the shape it is."""
    if method in (MINED, MINED_SINTERED):
        return (
            f"mined at {depth_m:.1f} m; overburden carries the pressure load "
            f"(stability number {number:.2f})"
        )
    if method == CUT_AND_COVER:
        return f"trenched at {depth_m:.1f} m; shell carries the pressure load"
    return f"bermed under {depth_m:.1f} m of cover; shell carries the full 55 kPa"


# ---------------------------------------------------------------------------
# Choosing the design
# ---------------------------------------------------------------------------
def site_thermal_context(
    site: pd.Series, config: BurialConfig
) -> tuple[float, float, float]:
    """Diurnal swing, seasonal swing and mean ground temperature for a site."""
    diurnal = surface_diurnal_swing_k(float(site.get("thermal_inertia", 200.0)))
    mean_temp, annual = surface_temperature_profile(
        latitude_deg=float(site["latitude_deg"]),
        albedo=float(site.get("albedo", 0.20)),
        elevation_km=float(site.get("elevation_km", 0.0)),
        optical_depth=config.optical_depth,
    )
    return diurnal, annual, mean_temp


def depth_profile(
    site: pd.Series,
    population: int,
    config: BurialConfig | None = None,
    grade_column: str = "predicted_weh_wt_pct",
) -> pd.DataFrame:
    """Every method at every candidate depth, as a table.

    This is the figure the architectural argument rests on, because the three
    curves it contains go in different directions: dose falls with depth,
    trench and berm volumes grow with the square of it, and the mined vault's
    shell mass falls to nothing at the self-anchoring depth. The optimum is a
    real interior minimum rather than a preference.
    """
    config = config or BurialConfig()
    grade = float(site[grade_column])
    diurnal, annual, mean_temp = site_thermal_context(site, config)
    name = str(site.get("name", "unnamed"))

    rows = []
    for method in METHODS:
        for depth in config.candidate_depths_m:
            option = evaluate_option(
                name, population, grade, method, float(depth),
                diurnal, annual, mean_temp, config,
            )
            rows.append(
                {
                    "method": method,
                    "depth_m": option.depth_m,
                    "dose_msv_per_year": option.dose_msv_per_year,
                    "temperature_swing_k": option.temperature_swing_k,
                    "overburden_kpa": option.overburden_kpa,
                    "net_pressure_kpa": option.net_pressure_kpa,
                    "shell_thickness_mm": option.shell_thickness_mm,
                    "stability_number": option.stability_number,
                    "landed_mass_t": option.landed_mass_kg / 1000.0,
                    "excavated_m3": option.excavated_m3,
                    "construction_energy_mwh": option.construction_energy_kwh / 1000.0,
                    "feasible": option.feasible,
                    "limiting_factor": option.limiting_factor,
                }
            )
    return pd.DataFrame(rows)


def mining_authorised(
    option: HabitatDesign, authorisation_grade_wt_pct: float, config: BurialConfig
) -> bool:
    """Whether an unsupported vault may be signed off on a pessimistic reading.

    Sizing and authorisation are different decisions and deserve different
    statistics. Getting the insulation wrong wastes power; getting the roof
    wrong drops it, so the roof is signed off against the water content the
    model is confident the ground has *at least*, while everything else is
    sized on its best estimate.
    """
    if not option.is_mined:
        return True
    if float(cementation_index(authorisation_grade_wt_pct)) <= 0.0:
        return False
    limit = config.stability_limit * (
        config.sintered_support_stability_multiple
        if option.method == MINED_SINTERED
        else 1.0
    )
    return (
        float(stability_number(option.depth_m, authorisation_grade_wt_pct)) <= limit
    )


def design_habitat(
    site: pd.Series,
    population: int,
    config: BurialConfig | None = None,
    grade_column: str = "predicted_weh_wt_pct",
    authorisation_column: str | None = "predicted_weh_lower_wt_pct",
) -> HabitatDesign:
    """Cheapest buildable habitat for a site and a crew size.

    The objective is landed mass, because that is the currency the rest of this
    project is denominated in and the only one a launch manifest recognises.
    Construction energy breaks ties, since two designs that cost the same to
    fly are not equal if one of them spends a month of the settlement's entire
    power output digging.

    Depth, shielding, shell and insulation are sized on the model's best
    estimate of the water content. Whether the settlement is allowed to mine an
    unsupported vault at all is decided against the model's conservative lower
    bound instead. Using one statistic for both is what makes an underground
    habitat either needlessly heavy or unsafe, and which of the two depends on
    which way the error went.
    """
    config = config or BurialConfig()
    grade = float(site[grade_column])
    authorisation = (
        float(site[authorisation_column])
        if authorisation_column and authorisation_column in site
        else grade
    )
    diurnal, annual, mean_temp = site_thermal_context(site, config)
    name = str(site.get("name", "unnamed"))

    options = [
        evaluate_option(
            name, population, grade, method, float(depth),
            diurnal, annual, mean_temp, config,
        )
        for method in METHODS
        for depth in config.candidate_depths_m
    ]
    buildable = [
        option
        for option in options
        if option.feasible and mining_authorised(option, authorisation, config)
    ]

    if not buildable:
        shallowest = min(options, key=lambda o: (o.dose_msv_per_year, o.depth_m))
        return replace(shallowest, feasible=False)

    return min(
        buildable,
        key=lambda o: (
            round(o.landed_mass_kg / 100.0),
            o.construction_energy_kwh,
            o.depth_m,
        ),
    )


def architecture_table(
    sites: pd.DataFrame,
    population: int,
    config: BurialConfig | None = None,
    grade_column: str = "predicted_weh_wt_pct",
    authorisation_column: str | None = "predicted_weh_lower_wt_pct",
) -> pd.DataFrame:
    """The chosen habitat design for every candidate site, ranked by mass."""
    config = config or BurialConfig()
    rows = []
    for _, site in sites.iterrows():
        design = design_habitat(
            site, population, config, grade_column, authorisation_column
        )
        rows.append(
            {
                "site": design.site_name,
                "latitude_deg": float(site["latitude_deg"]),
                "water_grade_wt_pct": design.water_grade_wt_pct,
                "method": design.method,
                "depth_m": design.depth_m,
                "vaults": design.vaults,
                "dose_msv_per_year": design.dose_msv_per_year,
                "swing_k": design.temperature_swing_k,
                "shell_mm": design.shell_thickness_mm,
                "insulation_cm": design.insulation_thickness_m * 100.0,
                "landed_mass_t": design.landed_mass_kg / 1000.0,
                "excavated_m3": design.excavated_m3,
                "construction_energy_mwh": design.construction_energy_kwh / 1000.0,
                "imported_shielding_t": (
                    design.imported_shielding_equivalent_kg / 1000.0
                ),
                "mass_saved_t": design.mass_saved_vs_imported_shielding_kg / 1000.0,
                "feasible": design.feasible,
                "limiting_factor": design.limiting_factor,
            }
        )
    frame = pd.DataFrame(rows)
    frame = frame.sort_values(
        ["feasible", "landed_mass_t"], ascending=[False, True]
    ).reset_index(drop=True)
    frame.insert(0, "rank", np.arange(1, len(frame) + 1))
    return frame


# ---------------------------------------------------------------------------
# What a map of buildability looks like
# ---------------------------------------------------------------------------
def buildability_field(
    grid: pd.DataFrame,
    grade_column: str = "predicted_weh_lower_wt_pct",
    internal_pressure_kpa: float = C.HABITAT_PRESSURE_KPA,
) -> pd.DataFrame:
    """Turn a predicted water field into a map of what can be built on it.

    Vectorised over the whole grid, because none of it needs the optimiser:
    the deepest unsupported opening and the self-anchoring depth are both
    closed-form functions of the ground's water content. Their ratio is the
    interesting number -- above one, the settlement can mine deep enough that
    its habitats stop being pressure vessels.
    """
    grade = grid[grade_column].to_numpy(dtype=float)
    mineable = max_unsupported_depth_m(grade)
    anchoring = self_anchoring_depth_m(grade, internal_pressure_kpa)

    out = grid.copy()
    out["cohesion_kpa"] = cohesion_kpa(grade)
    out["bulk_density_kg_m3"] = bulk_density_kg_m3(grade)
    out["max_unsupported_depth_m"] = mineable
    out["self_anchoring_depth_m"] = anchoring
    out["mineable_margin"] = mineable / anchoring
    out["can_mine_to_self_anchoring"] = mineable >= anchoring
    return out


# ---------------------------------------------------------------------------
# Was the model worth having?
# ---------------------------------------------------------------------------
def latitude_rule_of_thumb(latitude_deg) -> np.ndarray:
    """The guess an experienced planner would make without a model.

    Shallow ground ice is thermodynamically stable poleward of about 50
    degrees, patchy through the mid-latitudes, and absent at the equator. That
    is a genuinely good heuristic and it is what the model has to beat: it is
    right about the zonal trend and wrong about everything else, because the
    mantling deposit that actually holds the ice is not zonally uniform.
    """
    abs_lat = np.abs(np.asarray(latitude_deg, dtype=float))
    return np.select(
        [abs_lat >= 50.0, abs_lat >= 30.0],
        [18.0, 6.0],
        default=1.5,
    )


def as_built_under_truth(
    design: HabitatDesign,
    site: pd.Series,
    truth_grade_wt_pct: float,
    config: BurialConfig | None = None,
) -> HabitatDesign:
    """Re-cost a design at its chosen method and depth against the real ground.

    The construction decision -- trench or mine, and how deep -- is made before
    anyone has been there, so it is made on a belief. The bill, though, is
    settled against the ground that is actually present: that is what sets the
    shell thickness, the insulation, and whether the roof stands at all.
    """
    config = config or BurialConfig()
    diurnal, annual, mean_temp = site_thermal_context(site, config)
    return evaluate_option(
        design.site_name,
        design.population,
        truth_grade_wt_pct,
        design.method,
        design.depth_m,
        diurnal,
        annual,
        mean_temp,
        config,
    )


def decision_audit(
    sites: pd.DataFrame,
    population: int,
    config: BurialConfig | None = None,
    predicted_column: str = "predicted_weh_lower_wt_pct",
    mean_column: str = "predicted_weh_wt_pct",
    truth_column: str = "latent_truth_wt_pct",
) -> pd.DataFrame:
    """Score the architectural decision, not the regression.

    An R-squared says how close the predictions were. It does not say whether
    anybody would have built a different building without them, which is the
    only question that matters here.

    So each site is designed from five different beliefs about its water
    content: the model's mean prediction, the model's conservative lower bound,
    the latitude rule of thumb a good planner would use instead, the survey
    average, and -- cheating -- the ground truth, which gives the best decision
    that could possibly have been made.

    Every design is then re-costed against the ground as it really is, holding
    its method and depth fixed, and scored on *regret* in landed tonnes. A
    design that meets its requirements is charged the difference between what
    it landed and what the cheating design would have. A design that does not
    is charged everything it landed, because that hardware has been flown, has
    failed, and the correct habitat still has to be flown after it.

    The result is not the usual story about accuracy. Under-predicting water
    keeps the crew structurally safe -- no unsupported vault gets authorised in
    ground that cannot hold one -- but it is *not* conservative overall,
    because dry ground is predicted to be a better insulator than it is, and
    the habitat gets built too shallow to escape the seasonal temperature wave.
    Over-predicting reverses both errors. There is no safe direction to be
    wrong in, which is the strongest argument this project has for spending the
    effort on a calibrated prediction rather than a margin.
    """
    config = config or BurialConfig()
    frame = sites.copy()
    frame["_latitude_guess"] = latitude_rule_of_thumb(frame["latitude_deg"])
    frame["_survey_mean"] = float(frame[predicted_column].mean())

    strategies: dict[str, tuple[str, str | None]] = {
        "water model (sized on mean, mining authorised on bound)": (
            mean_column,
            predicted_column,
        ),
        "water model, conservative bound throughout": (predicted_column, None),
        "latitude rule of thumb": ("_latitude_guess", None),
        "survey average": ("_survey_mean", None),
        "perfect foresight": (truth_column, None),
    }

    ideal = {
        index: design_habitat(site, population, config, truth_column, None)
        for index, site in frame.iterrows()
    }

    rows = []
    for label, (column, authorisation) in strategies.items():
        regrets: list[float] = []
        wrong_method = 0
        causes = {"radiation": 0, "thermal": 0, "ground strength": 0}
        for index, site in frame.iterrows():
            truth = float(site[truth_column])
            chosen = design_habitat(
                site, population, config, column, authorisation
            )
            realised = as_built_under_truth(chosen, site, truth, config)

            wrong_method += int(chosen.method != ideal[index].method)
            if realised.feasible:
                regrets.append(
                    (realised.landed_mass_kg - ideal[index].landed_mass_kg) / 1000.0
                )
            else:
                regrets.append(realised.landed_mass_kg / 1000.0)
                if not mining_authorised(chosen, truth, config):
                    causes["ground strength"] += 1
                elif realised.limiting_category in causes:
                    causes[realised.limiting_category] += 1

        rows.append(
            {
                "grade source": label,
                "wasted tonnes per site": round(float(np.mean(regrets)), 1),
                "wasted tonnes, all sites": round(float(np.sum(regrets)), 1),
                "wrong construction method": wrong_method,
                "built too shallow for the seasons": causes["thermal"],
                "built over the dose limit": causes["radiation"],
                "vaults that will not stand": causes["ground strength"],
                "sites audited": len(frame),
            }
        )
    return pd.DataFrame(rows)


def audit_against_truth(
    design: HabitatDesign,
    site: pd.Series,
    truth_grade_wt_pct: float,
    config: BurialConfig | None = None,
) -> dict[str, float | bool | str]:
    """Hold a design fixed and ask what the real ground does to it.

    The method and the depth were chosen on a belief about the water content.
    Here they stay exactly as built while the ground properties are recomputed
    from the truth, which is how a construction decision is actually tested.
    """
    config = config or BurialConfig()
    diurnal, annual, mean_temp = site_thermal_context(site, config)

    dose = float(gcr_dose_msv_per_year(design.depth_m, truth_grade_wt_pct))
    swing = float(
        temperature_swing_at_depth_k(
            design.depth_m, truth_grade_wt_pct, diurnal, annual
        )
    )
    number = float(stability_number(design.depth_m, truth_grade_wt_pct))

    limit = config.stability_limit * (
        config.sintered_support_stability_multiple
        if design.method == MINED_SINTERED
        else 1.0
    )
    roof_stands = (not design.is_mined) or number <= limit

    required_r = required_insulation_r_m2k_w(
        design.method, design.depth_m, truth_grade_wt_pct, mean_temp,
        config.geometry, config,
    )
    as_built_r = design.insulation_thickness_m / C.INSULATION_CONDUCTIVITY_W_M_K
    insulation_adequate = as_built_r + 1e-9 >= required_r

    if not roof_stands:
        verdict = (
            f"unsupported vault authorised at {design.depth_m:.1f} m in "
            f"{truth_grade_wt_pct:.1f} wt% ground (stability number {number:.1f})"
        )
    elif dose > config.dose_limit_msv_per_year:
        verdict = f"crew takes {dose:.0f} mSv/yr against a {config.dose_limit_msv_per_year:.0f} limit"
    elif not insulation_adequate:
        verdict = "insulation undersized; the ice cement around the vault warms through"
    elif swing > config.temperature_swing_tolerance_k:
        verdict = f"ground still swings {swing:.1f} K at the as-built depth"
    else:
        verdict = "stands up under the real ground"

    return {
        "method": design.method,
        "depth_m": design.depth_m,
        "design_grade_wt_pct": design.water_grade_wt_pct,
        "truth_grade_wt_pct": float(truth_grade_wt_pct),
        "dose_msv_per_year": dose,
        "temperature_swing_k": swing,
        "stability_number": number,
        "roof_stands": roof_stands,
        "dose_met": dose <= config.dose_limit_msv_per_year,
        "insulation_adequate": insulation_adequate,
        "verdict": verdict,
    }


def construction_energy_in_context(
    design: HabitatDesign, settlement_energy_kwh_per_sol: float
) -> dict[str, float]:
    """Express construction energy in the units the settlement actually feels.

    Digging is not free just because the regolith is. Every kilowatt-hour spent
    moving ground is a kilowatt-hour the water plant did not get, so the
    honest way to quote an excavation programme is in sols of the settlement's
    entire power output -- and in the water that was not mined while it ran.
    """
    per_sol = max(settlement_energy_kwh_per_sol, 1e-9)
    energy = design.construction_energy_kwh
    return {
        "construction_energy_mwh": energy / 1000.0,
        "sols_of_total_settlement_power": energy / per_sol,
        "excavation_share": design.excavation_energy_kwh / max(energy, 1e-9),
        "sintering_share": design.sintering_energy_kwh / max(energy, 1e-9),
    }
