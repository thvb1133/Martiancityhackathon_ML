"""Deterministic Mars physics: insolation, power supply, life-support demand.

Nothing in this module is learned. Every function here is a closed-form
calculation from published constants, which keeps the machine-learning claim in
this project honest: exactly one quantity is predicted by a model (subsurface
water yield, in ``model.py``), and everything downstream of it is arithmetic a
judge can check by hand.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from . import constants as C


# ---------------------------------------------------------------------------
# Orbital geometry
# ---------------------------------------------------------------------------
def solar_longitude_to_sun_distance_au(solar_longitude_deg: float | np.ndarray):
    """Mars-Sun distance in AU at a given areocentric solar longitude (Ls).

    Perihelion occurs near Ls = 251 degrees, so true anomaly is measured from
    there.
    """
    true_anomaly = np.radians(np.asarray(solar_longitude_deg, dtype=float) - 251.0)
    e = C.MARS_ECCENTRICITY
    return C.MARS_SEMI_MAJOR_AXIS_AU * (1 - e**2) / (1 + e * np.cos(true_anomaly))


def solar_declination_deg(solar_longitude_deg: float | np.ndarray):
    """Sub-solar latitude at a given solar longitude."""
    ls = np.radians(np.asarray(solar_longitude_deg, dtype=float))
    return np.degrees(np.arcsin(np.sin(np.radians(C.MARS_OBLIQUITY_DEG)) * np.sin(ls)))


def top_of_atmosphere_irradiance(solar_longitude_deg: float | np.ndarray):
    """Beam irradiance above the Martian atmosphere, W/m^2."""
    r_au = solar_longitude_to_sun_distance_au(solar_longitude_deg)
    return C.SOLAR_CONSTANT_1AU_W_M2 / r_au**2


# ---------------------------------------------------------------------------
# Surface insolation
# ---------------------------------------------------------------------------
def daily_insolation_kwh_m2(
    latitude_deg: float | np.ndarray,
    solar_longitude_deg: float = 180.0,
    optical_depth: float = C.TAU_CLEAR,
    elevation_km: float | np.ndarray = 0.0,
):
    """Energy received by a horizontal surface over one sol, in kWh/m^2.

    The beam component is integrated analytically over the sol, then attenuated
    with Beer-Lambert extinction through the dust column. Because Martian dust
    scatters strongly forward, a fixed fraction of the extinguished beam is
    returned as diffuse skylight rather than lost.
    """
    lat = np.radians(np.asarray(latitude_deg, dtype=float))
    dec = np.radians(solar_declination_deg(solar_longitude_deg))
    toa = top_of_atmosphere_irradiance(solar_longitude_deg)

    # Sunset hour angle, clipped to handle polar day and polar night.
    cos_hour_angle = np.clip(-np.tan(lat) * np.tan(dec), -1.0, 1.0)
    hour_angle = np.arccos(cos_hour_angle)

    # Sol-integrated beam energy on a horizontal plane, in J/m^2.
    beam_j = (C.SOL_LENGTH_S / np.pi) * toa * (
        hour_angle * np.sin(lat) * np.sin(dec)
        + np.cos(lat) * np.cos(dec) * np.sin(hour_angle)
    )
    beam_j = np.maximum(beam_j, 0.0)

    # Effective air mass over the sol, from the mean daytime solar elevation.
    mean_cos_zenith = np.clip(
        np.sin(lat) * np.sin(dec)
        + np.cos(lat) * np.cos(dec) * np.sin(hour_angle) / np.maximum(hour_angle, 1e-9),
        0.05,
        1.0,
    )

    # Higher ground sits under less dust: scale height of the dust column is
    # about 11 km, so optical depth thins exponentially with elevation.
    tau = np.asarray(optical_depth, dtype=float) * np.exp(
        -np.asarray(elevation_km, dtype=float) / 11.1
    )

    transmitted = np.exp(-tau / mean_cos_zenith)
    diffuse = (1.0 - transmitted) * C.DIFFUSE_RECOVERY_FRACTION
    surface_j = beam_j * (transmitted + diffuse)

    return surface_j / 3.6e6  # J -> kWh


def night_fraction(
    latitude_deg: float, solar_longitude_deg: float = 180.0
) -> float:
    """Fraction of the sol spent in darkness, from the sunset hour angle."""
    lat = np.radians(float(latitude_deg))
    dec = np.radians(solar_declination_deg(solar_longitude_deg))
    hour_angle = np.arccos(np.clip(-np.tan(lat) * np.tan(dec), -1.0, 1.0))
    return float(np.clip(1.0 - hour_angle / np.pi, 0.0, 1.0))


def array_specific_yield_kwh_m2_sol(
    latitude_deg: float,
    solar_longitude_deg: float = 180.0,
    optical_depth: float = C.TAU_CLEAR,
    elevation_km: float = 0.0,
) -> float:
    """Electrical energy per square metre of deployed array, per sol.

    This single number is what makes latitude expensive: an array at 47 deg
    north delivers roughly 60 per cent of the energy of the same array near
    the equator, so a high-latitude settlement has to land proportionally more
    photovoltaic mass for the same power.
    """
    insol = daily_insolation_kwh_m2(
        latitude_deg, solar_longitude_deg, optical_depth, elevation_km
    )
    return float(
        insol
        * C.PV_EFFICIENCY
        * C.PV_PACKING_FACTOR
        * C.PV_DUST_SETTLING_DERATE
        * C.BATTERY_ROUND_TRIP_EFFICIENCY
    )


def array_output_kwh_per_sol(
    array_area_m2: float,
    latitude_deg: float,
    solar_longitude_deg: float = 180.0,
    optical_depth: float = C.TAU_CLEAR,
    elevation_km: float = 0.0,
):
    """Electrical energy from a horizontal PV array over one sol, in kWh."""
    insol = daily_insolation_kwh_m2(
        latitude_deg, solar_longitude_deg, optical_depth, elevation_km
    )
    return (
        insol
        * array_area_m2
        * C.PV_EFFICIENCY
        * C.PV_PACKING_FACTOR
        * C.PV_DUST_SETTLING_DERATE
        * C.BATTERY_ROUND_TRIP_EFFICIENCY
    )


# ---------------------------------------------------------------------------
# ISRU: what it costs to get a kilogram of water out of the ground
# ---------------------------------------------------------------------------
REGOLITH_SPECIFIC_HEAT_J_KG_K = 800.0
REGOLITH_HEATING_DELTA_T_K = 200.0  # from ~200 K ambient to ~400 K release
WATER_SUBLIMATION_ENTHALPY_KWH_PER_KG = 2.83e6 / 3.6e6
EXCAVATION_KWH_PER_KG_REGOLITH = 0.02
ISRU_PLANT_EFFICIENCY = 0.72  # thermal losses in a real extraction chamber


def isru_energy_per_kg_water(
    ore_grade_wt_pct: float | np.ndarray, heat_recovery: float = 0.45
):
    """Energy needed to liberate one kilogram of water, kWh/kg.

    This is the coupling that makes the water prediction matter. To recover a
    kilogram of water from regolith at grade ``g`` weight percent, the plant
    has to excavate and heat ``100/g`` kilograms of rock. A rich deposit at
    12 wt% needs roughly a tenth of the processed mass of a marginal 1.5 wt%
    deposit, so the energy cost per litre rises steeply as the ground dries
    out -- and the settlement's entire power budget moves with it.
    """
    grade = np.clip(np.asarray(ore_grade_wt_pct, dtype=float), 0.2, 100.0)
    regolith_kg_per_kg_water = 100.0 / grade

    heating_kwh_per_kg_regolith = (
        REGOLITH_SPECIFIC_HEAT_J_KG_K * REGOLITH_HEATING_DELTA_T_K / 3.6e6
    )
    bulk_handling = regolith_kg_per_kg_water * (
        heating_kwh_per_kg_regolith * (1.0 - heat_recovery)
        + EXCAVATION_KWH_PER_KG_REGOLITH
    )
    return (bulk_handling + WATER_SUBLIMATION_ENTHALPY_KWH_PER_KG) / (
        ISRU_PLANT_EFFICIENCY
    )


# ---------------------------------------------------------------------------
# Settlement demand
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SettlementDemand:
    """Per-sol consumable and energy demand for a crew of a given size."""

    population: int
    water_makeup_kg: float
    water_life_support_kg: float
    water_propellant_kg: float
    oxygen_kg: float
    food_kg: float
    return_flights_per_synod: float
    energy_isru_kwh: float
    energy_electrolysis_kwh: float
    energy_greenhouse_kwh: float
    energy_habitat_kwh: float
    energy_propellant_kwh: float

    @property
    def energy_total_kwh(self) -> float:
        return (
            self.energy_isru_kwh
            + self.energy_electrolysis_kwh
            + self.energy_greenhouse_kwh
            + self.energy_habitat_kwh
            + self.energy_propellant_kwh
        )

    @property
    def energy_breakdown_kwh(self) -> dict[str, float]:
        return {
            "ISRU water extraction": self.energy_isru_kwh,
            "Electrolysis (crew O2)": self.energy_electrolysis_kwh,
            "Greenhouse lighting": self.energy_greenhouse_kwh,
            "Habitat overhead": self.energy_habitat_kwh,
            "Propellant plant": self.energy_propellant_kwh,
        }

    @property
    def water_breakdown_kg(self) -> dict[str, float]:
        return {
            "Life support makeup": self.water_life_support_kg,
            "Propellant production": self.water_propellant_kg,
        }


def settlement_demand(
    population: int,
    water_loop_closure: float = C.WATER_LOOP_CLOSURE,
    food_grown_locally_fraction: float = 1.0,
    ore_grade_wt_pct: float | None = None,
    crew_per_return_flight: float = C.DEFAULT_CREW_PER_RETURN_FLIGHT,
    include_propellant: bool = True,
) -> SettlementDemand:
    """Per-sol demand for a crew, including the energy to produce it.

    Life-support water demand is *makeup* water only: the ECLSS recycles most
    of what the crew uses, so ISRU has to mine only the loop losses plus the
    water electrolysed into breathing oxygen. That quantity is small, which is
    exactly why propellant matters -- making methalox for a single departing
    vehicle consumes several hundred tonnes of mined water, an order of
    magnitude more than the crew drinks. Any settlement that intends to send
    people home is a propellant plant with a habitat attached.

    When ``ore_grade_wt_pct`` is supplied, the mining energy is computed from
    that grade rather than from the generic flat rate, which is how the
    model's per-site water prediction enters the power budget.
    """
    if population < 0:
        raise ValueError("population must be non-negative")

    gross_water = population * (
        C.POTABLE_WATER_KG_PER_PERSON_SOL + C.HYGIENE_WATER_KG_PER_PERSON_SOL
    )
    loop_losses = gross_water * (1.0 - water_loop_closure)

    oxygen = population * C.O2_KG_PER_PERSON_SOL
    # Electrolysis of H2O yields O2 at 8/9 of the feedstock mass.
    water_for_oxygen = oxygen * 9.0 / 8.0

    water_life_support = loop_losses + water_for_oxygen
    food = population * C.FOOD_DRY_KG_PER_PERSON_SOL * food_grown_locally_fraction

    # Return capability. A settlement always keeps at least one vehicle
    # fuelled for the next launch window, and needs more as the crew grows.
    if include_propellant and population > 0:
        flights = max(1.0, math.ceil(population / max(crew_per_return_flight, 1.0)))
    else:
        flights = 0.0
    water_propellant = (
        flights * C.PROPELLANT_WATER_KG_PER_LAUNCH / C.SYNOD_SOLS
    )
    energy_propellant = water_propellant * C.PROPELLANT_PLANT_KWH_PER_KG_WATER

    water_makeup = water_life_support + water_propellant

    if ore_grade_wt_pct is None:
        isru_kwh_per_kg = C.ISRU_WATER_EXTRACTION_KWH_PER_KG
    else:
        isru_kwh_per_kg = float(isru_energy_per_kg_water(ore_grade_wt_pct))

    return SettlementDemand(
        population=population,
        water_makeup_kg=water_makeup,
        water_life_support_kg=water_life_support,
        water_propellant_kg=water_propellant,
        oxygen_kg=oxygen,
        food_kg=food,
        return_flights_per_synod=flights,
        energy_isru_kwh=water_makeup * isru_kwh_per_kg,
        energy_electrolysis_kwh=oxygen * C.ELECTROLYSIS_KWH_PER_KG_O2,
        energy_greenhouse_kwh=food * C.GREENHOUSE_KWH_PER_KG_FOOD,
        energy_habitat_kwh=population * C.HABITAT_OVERHEAD_KWE_PER_PERSON * 24.66,
        energy_propellant_kwh=energy_propellant,
    )
