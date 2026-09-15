"""Settlement resilience simulation: what does a site cost, and where does it break?

The model predicts how much water is in the ground. This module answers the
question a mission planner actually asks, which is different: *how much
hardware must we fly from Earth to keep N people alive here, and at what crew
size does this site stop working altogether?*

Two opposed physical pressures drive every result below.

Energy pushes the settlement toward the equator. A photovoltaic array at 47
degrees north yields roughly 60 per cent of what the same array yields near the
equator, so a high-latitude base pays for its power in landed array mass.

Water pushes the settlement toward the mid-latitudes. To recover a kilogram of
water the extraction plant must heat ``100/grade`` kilograms of regolith, so a
0.6 wt% equatorial deposit needs around forty times the rock throughput of a
22 wt% mid-latitude one for the same litre of water.

At a small outpost the energy term dominates and the equator wins. As the crew
grows, rock throughput at a dry site climbs past what any maintainable mining
fleet can move, and the site does not merely get expensive -- it becomes
infeasible. That is the breakpoint the demo is built around, and it is a
consequence of the physics rather than a weighting chosen to produce it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

from . import constants as C
from .physics import (
    array_specific_yield_kwh_m2_sol,
    isru_energy_per_kg_water,
    night_fraction,
    settlement_demand,
)

ABSOLUTE_MAX_POPULATION = 20_000


@dataclass(frozen=True)
class SettlementConfig:
    """Operating assumptions and the limits of the landed campaign."""

    fission_units: int = 4  # 10 kWe Kilopower-class reactors
    solar_longitude_deg: float = 180.0  # northern autumn equinox
    optical_depth: float = C.TAU_CLEAR
    water_loop_closure: float = C.WATER_LOOP_CLOSURE
    food_grown_locally_fraction: float = 1.0
    reserve_margin: float = 0.15  # power held back for faults and growth
    crew_per_return_flight: float = C.DEFAULT_CREW_PER_RETURN_FLIGHT
    include_propellant: bool = True
    max_excavator_fleet: int = C.MAX_EXCAVATOR_FLEET
    max_pv_area_m2: float = C.MAX_PV_AREA_M2

    @property
    def fission_kwh_per_sol(self) -> float:
        return self.fission_units * C.KILOPOWER_UNIT_KWE * (C.SOL_LENGTH_S / 3600.0)

    def with_optical_depth(self, optical_depth: float) -> "SettlementConfig":
        return replace(self, optical_depth=optical_depth)


@dataclass(frozen=True)
class Infrastructure:
    """The hardware one site needs to support one crew size."""

    site_name: str
    population: int
    water_grade_wt_pct: float

    energy_demand_kwh_per_sol: float
    isru_kwh_per_kg_water: float
    isru_share_of_load: float
    fission_kwh_per_sol: float
    pv_energy_kwh_per_sol: float

    specific_yield_kwh_m2_sol: float
    pv_area_m2: float
    pv_mass_kg: float
    battery_capacity_kwh: float
    battery_mass_kg: float
    fission_mass_kg: float

    water_makeup_kg_per_sol: float
    water_life_support_kg_per_sol: float
    water_propellant_kg_per_sol: float
    return_flights_per_synod: float
    regolith_kg_per_sol: float
    excavator_units: int
    excavator_mass_kg: float
    processing_plant_mass_kg: float

    feasible: bool
    limiting_factor: str

    @property
    def total_mass_kg(self) -> float:
        """Site-dependent landed mass.

        Pressure vessels, consumables and crew systems are deliberately
        excluded: they cost the same everywhere, so including them would only
        dilute the comparison between sites.
        """
        return (
            self.pv_mass_kg
            + self.battery_mass_kg
            + self.fission_mass_kg
            + self.excavator_mass_kg
            + self.processing_plant_mass_kg
        )

    @property
    def launches(self) -> float:
        return self.total_mass_kg / C.STARSHIP_PAYLOAD_KG

    @property
    def mass_breakdown_kg(self) -> dict[str, float]:
        return {
            "Solar array": self.pv_mass_kg,
            "Energy storage": self.battery_mass_kg,
            "Fission units": self.fission_mass_kg,
            "Mining fleet": self.excavator_mass_kg,
            "Extraction plant": self.processing_plant_mass_kg,
        }

    @property
    def water_infrastructure_mass_kg(self) -> float:
        return self.excavator_mass_kg + self.processing_plant_mass_kg

    @property
    def power_infrastructure_mass_kg(self) -> float:
        return self.pv_mass_kg + self.battery_mass_kg + self.fission_mass_kg


def landability(site: pd.Series) -> tuple[bool, str]:
    """Hard terrain gates on entry, descent, landing and surface mobility."""
    slope = float(site.get("slope_deg", 0.0))
    rocks = float(site.get("rock_abundance", 0.0))
    if slope > C.MAX_LANDING_SLOPE_DEG:
        return False, f"terrain slope {slope:.1f} deg exceeds the {C.MAX_LANDING_SLOPE_DEG:.0f} deg EDL limit"
    if rocks > C.MAX_ROCK_ABUNDANCE:
        return False, f"rock abundance {rocks:.0%} blocks array and habitat layout"
    return True, "within landing and surface-mobility limits"


def size_infrastructure(
    site: pd.Series,
    population: int,
    config: SettlementConfig,
    grade_column: str = "predicted_weh_lower_wt_pct",
) -> Infrastructure:
    """Size the power and mining plant one site needs for a given crew.

    The conservative lower bound of the model's prediction is used by default.
    Sizing a water plant on the mean forecast fails half the time the forecast
    is wrong, which is not an acceptable risk posture for the crew's only
    source of drinking water and breathing oxygen.
    """
    if population < 1:
        raise ValueError("population must be at least 1")

    grade = float(site[grade_column])
    latitude = float(site["latitude_deg"])
    elevation = float(site["elevation_km"])

    demand = settlement_demand(
        population,
        water_loop_closure=config.water_loop_closure,
        food_grown_locally_fraction=config.food_grown_locally_fraction,
        ore_grade_wt_pct=grade,
        crew_per_return_flight=config.crew_per_return_flight,
        include_propellant=config.include_propellant,
    )
    required = demand.energy_total_kwh / (1.0 - config.reserve_margin)

    # Power: reactors first, because they run through the night and through
    # dust storms; photovoltaics make up whatever is left.
    fission = config.fission_kwh_per_sol
    pv_energy = max(0.0, required - fission)

    specific_yield = array_specific_yield_kwh_m2_sol(
        latitude_deg=latitude,
        solar_longitude_deg=config.solar_longitude_deg,
        optical_depth=config.optical_depth,
        elevation_km=elevation,
    )
    pv_area = pv_energy / specific_yield if specific_yield > 1e-9 else math.inf

    # Storage covers the photovoltaic share of the load through the night.
    dark = night_fraction(latitude, config.solar_longitude_deg)
    battery_kwh = pv_energy * dark
    battery_mass = battery_kwh * 1000.0 / C.BATTERY_SPECIFIC_ENERGY_WH_KG

    # Mining: rock throughput is set by the ore grade the model predicted.
    regolith = demand.water_makeup_kg * (100.0 / max(grade, 0.2))
    excavators = int(math.ceil(regolith / C.EXCAVATOR_UNIT_THROUGHPUT_KG_PER_SOL))
    plant_mass = regolith * C.PROCESSING_PLANT_MASS_KG_PER_KG_SOL
    water_mass = excavators * C.EXCAVATOR_UNIT_MASS_KG + plant_mass
    power_mass = (
        pv_area * C.PV_AREAL_MASS_KG_M2
        + battery_mass
        + config.fission_units * C.FISSION_UNIT_MASS_KG
    )

    landable, landing_note = landability(site)
    if not landable:
        feasible, limiting = False, landing_note
    elif excavators > config.max_excavator_fleet:
        feasible = False
        limiting = (
            f"mining fleet: {regolith / 1000:.0f} t of regolith per sol needs "
            f"{excavators} excavators, above the {config.max_excavator_fleet}-unit "
            f"maintenance limit at {grade:.1f} wt% water"
        )
    elif pv_area > config.max_pv_area_m2:
        feasible = False
        limiting = (
            f"array footprint: {pv_area / 1e6:.2f} km2 of collector needed, above "
            f"the {config.max_pv_area_m2 / 1e6:.2f} km2 solar farm limit"
        )
    else:
        feasible = True
        water_share = water_mass / max(water_mass + power_mass, 1e-9)
        limiting = (
            f"power-dominated ({1 - water_share:.0%} of landed mass)"
            if water_share < 0.5
            else f"water-extraction-dominated ({water_share:.0%} of landed mass)"
        )

    return Infrastructure(
        site_name=str(site.get("name", "unnamed")),
        population=population,
        water_grade_wt_pct=grade,
        energy_demand_kwh_per_sol=demand.energy_total_kwh,
        isru_kwh_per_kg_water=float(isru_energy_per_kg_water(grade)),
        isru_share_of_load=demand.energy_isru_kwh
        / max(demand.energy_total_kwh, 1e-9),
        fission_kwh_per_sol=fission,
        pv_energy_kwh_per_sol=pv_energy,
        specific_yield_kwh_m2_sol=specific_yield,
        pv_area_m2=pv_area,
        pv_mass_kg=pv_area * C.PV_AREAL_MASS_KG_M2,
        battery_capacity_kwh=battery_kwh,
        battery_mass_kg=battery_mass,
        fission_mass_kg=config.fission_units * C.FISSION_UNIT_MASS_KG,
        water_makeup_kg_per_sol=demand.water_makeup_kg,
        water_life_support_kg_per_sol=demand.water_life_support_kg,
        water_propellant_kg_per_sol=demand.water_propellant_kg,
        return_flights_per_synod=demand.return_flights_per_synod,
        regolith_kg_per_sol=regolith,
        excavator_units=excavators,
        excavator_mass_kg=excavators * C.EXCAVATOR_UNIT_MASS_KG,
        processing_plant_mass_kg=regolith * C.PROCESSING_PLANT_MASS_KG_PER_KG_SOL,
        feasible=feasible,
        limiting_factor=limiting,
    )


def max_supportable_population(
    site: pd.Series,
    config: SettlementConfig,
    grade_column: str = "predicted_weh_lower_wt_pct",
) -> tuple[int, str]:
    """Largest crew the site sustains, and what stops it growing further.

    Feasibility is monotonically decreasing in crew size, so the ceiling is
    found by bisection rather than by simulating every population.
    """
    if not size_infrastructure(site, 1, config, grade_column).feasible:
        return 0, size_infrastructure(site, 1, config, grade_column).limiting_factor

    high_probe = size_infrastructure(
        site, ABSOLUTE_MAX_POPULATION, config, grade_column
    )
    if high_probe.feasible:
        return ABSOLUTE_MAX_POPULATION, "no limit below the model's population ceiling"

    low, high = 1, ABSOLUTE_MAX_POPULATION
    while high - low > 1:
        mid = (low + high) // 2
        if size_infrastructure(site, mid, config, grade_column).feasible:
            low = mid
        else:
            high = mid
    return low, size_infrastructure(site, high, config, grade_column).limiting_factor


def rank_sites(
    sites: pd.DataFrame,
    config: SettlementConfig,
    target_population: int = 100,
    grade_column: str = "predicted_weh_lower_wt_pct",
) -> pd.DataFrame:
    """Order candidate sites by the launch mass each needs for a target crew.

    Sites are ranked by a physical cost -- landed kilograms -- and not by a
    hand-weighted index of features, so the ordering is an output of the
    simulation rather than a set of weights chosen to favour an answer.
    Infeasible sites are listed last regardless of cost.
    """
    rows = []
    for _, site in sites.iterrows():
        infra = size_infrastructure(site, target_population, config, grade_column)
        capacity, capacity_limit = max_supportable_population(
            site, config, grade_column
        )
        rows.append(
            {
                "name": infra.site_name,
                "latitude_deg": float(site["latitude_deg"]),
                "longitude_deg": float(site["longitude_deg"]),
                "elevation_km": float(site["elevation_km"]),
                "water_grade_wt_pct": infra.water_grade_wt_pct,
                "isru_kwh_per_kg_water": infra.isru_kwh_per_kg_water,
                "specific_yield_kwh_m2_sol": infra.specific_yield_kwh_m2_sol,
                "energy_demand_kwh_per_sol": infra.energy_demand_kwh_per_sol,
                "pv_area_km2": infra.pv_area_m2 / 1e6,
                "water_t_per_sol": infra.water_makeup_kg_per_sol / 1000.0,
                "regolith_t_per_sol": infra.regolith_kg_per_sol / 1000.0,
                "excavator_units": infra.excavator_units,
                "power_mass_t": infra.power_infrastructure_mass_kg / 1000.0,
                "water_mass_t": infra.water_infrastructure_mass_kg / 1000.0,
                "landed_mass_t": infra.total_mass_kg / 1000.0,
                "launches": infra.launches,
                "feasible": infra.feasible,
                "limiting_factor": infra.limiting_factor,
                "max_population": capacity,
                "capacity_limit": capacity_limit,
            }
        )

    frame = pd.DataFrame(rows)
    frame = frame.sort_values(
        ["feasible", "landed_mass_t"], ascending=[False, True]
    ).reset_index(drop=True)
    frame.insert(0, "rank", np.arange(1, len(frame) + 1))
    return frame


def population_sweep(
    sites: pd.DataFrame,
    config: SettlementConfig,
    populations: tuple[int, ...] = (20, 100, 300, 1000, 2000, 4000),
    grade_column: str = "predicted_weh_lower_wt_pct",
) -> pd.DataFrame:
    """How the leaderboard changes as the settlement grows.

    This is the result the project exists to produce: the site you would pick
    for a first landing is not the site you would pick for a city, because the
    constraint that binds has changed underneath the decision.
    """
    rows = []
    for population in populations:
        ranked = rank_sites(sites, config, population, grade_column)
        viable = ranked[ranked["feasible"]]
        best = viable.iloc[0] if len(viable) else None
        rows.append(
            {
                "population": population,
                "sites_viable": int(len(viable)),
                "sites_considered": int(len(ranked)),
                "best_site": None if best is None else best["name"],
                "best_site_latitude": None if best is None else best["latitude_deg"],
                "best_site_water_wt_pct": None
                if best is None
                else round(float(best["water_grade_wt_pct"]), 1),
                "landed_mass_t": None
                if best is None
                else round(float(best["landed_mass_t"]), 1),
                "driver": None if best is None else best["limiting_factor"],
            }
        )
    return pd.DataFrame(rows)


def minimum_fission_units(
    site: pd.Series,
    population: int,
    config: SettlementConfig,
    grade_column: str = "predicted_weh_lower_wt_pct",
    ceiling: int = 400,
) -> int | None:
    """Fewest reactors that make a site work for a crew size, or None.

    When the population sweep reports that no site is viable, the useful answer
    is not "impossible" but "here is the hardware you are missing". Reactors
    substitute for array area and storage, so raising the fission count is the
    lever that reopens a site -- unless the binding limit is mining throughput,
    in which case no amount of power helps and the function returns None.
    """
    for units in range(config.fission_units, ceiling + 1):
        trial = replace(config, fission_units=units)
        if size_infrastructure(site, population, trial, grade_column).feasible:
            return units
    return None


def mission_architecture_comparison(
    sites: pd.DataFrame,
    config: SettlementConfig,
    target_population: int = 100,
    grade_column: str = "predicted_weh_lower_wt_pct",
) -> pd.DataFrame:
    """Does the settlement intend to send anyone home, and does that move it?

    A one-way outpost only has to keep its crew alive, and a closed ECLSS makes
    that a small water demand -- so the siting decision is won on sunlight, and
    the best site is a dry, high-elevation one near the equator. The moment the
    settlement commits to a return capability, propellant dwarfs the crew's
    water demand by an order of magnitude, and the decision is won on ice
    instead. The recommended landing site changes accordingly.

    This is the clearest demonstration that the water prediction is load
    bearing: hold everything else fixed, change only whether vehicles depart,
    and the model's output reorders the answer.
    """
    rows = []
    for label, propellant in (
        ("one-way outpost (no return vehicle)", False),
        ("return capability (methalox from ice)", True),
    ):
        scenario = replace(config, include_propellant=propellant)
        ranked = rank_sites(sites, scenario, target_population, grade_column)
        viable = ranked[ranked["feasible"]]
        if not len(viable):
            rows.append({"architecture": label, "recommended_site": None})
            continue
        best = viable.iloc[0]
        rows.append(
            {
                "architecture": label,
                "recommended_site": best["name"],
                "latitude_deg": best["latitude_deg"],
                "water_grade_wt_pct": round(float(best["water_grade_wt_pct"]), 1),
                "water_t_per_sol": round(float(best["water_t_per_sol"]), 2),
                "landed_mass_t": round(float(best["landed_mass_t"]), 1),
                "sites_viable": int(len(viable)),
                "driver": best["limiting_factor"],
            }
        )
    return pd.DataFrame(rows)


def dust_storm_resilience(
    site: pd.Series,
    config: SettlementConfig,
    target_population: int,
    grade_column: str = "predicted_weh_lower_wt_pct",
) -> pd.DataFrame:
    """Cost and capacity under clear skies, a regional storm, a global storm.

    The 2018 planet-encircling dust storm ended the Opportunity mission. A
    solar-powered settlement plan that does not state what happens during one
    is incomplete, so this is reported next to the nominal answer rather than
    as a footnote.
    """
    scenarios = {
        "clear (tau 0.35)": C.TAU_CLEAR,
        "regional storm (tau 1.5)": C.TAU_REGIONAL_STORM,
        "global storm (tau 4.5)": C.TAU_GLOBAL_STORM,
    }
    rows = []
    for label, tau in scenarios.items():
        scenario_config = config.with_optical_depth(tau)
        infra = size_infrastructure(
            site, target_population, scenario_config, grade_column
        )
        capacity, _ = max_supportable_population(
            site, scenario_config, grade_column
        )
        rows.append(
            {
                "scenario": label,
                "optical_depth": tau,
                "specific_yield_kwh_m2_sol": round(infra.specific_yield_kwh_m2_sol, 3),
                "pv_area_km2": round(infra.pv_area_m2 / 1e6, 3),
                "landed_mass_t": round(infra.total_mass_kg / 1000.0, 1),
                "max_population": capacity,
                "feasible": infra.feasible,
            }
        )
    return pd.DataFrame(rows)
