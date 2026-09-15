"""Tests for the deterministic physics layer.

These are the checks that matter most: the physics is what the machine-learning
prediction feeds into, so an error here would quietly corrupt every siting
decision the tool makes.
"""

from __future__ import annotations

import numpy as np
import pytest

from marswater import constants as C
from marswater.physics import (
    array_specific_yield_kwh_m2_sol,
    daily_insolation_kwh_m2,
    isru_energy_per_kg_water,
    night_fraction,
    settlement_demand,
    solar_declination_deg,
    solar_longitude_to_sun_distance_au,
    top_of_atmosphere_irradiance,
)


class TestOrbitalGeometry:
    def test_sun_distance_spans_perihelion_and_aphelion(self):
        distances = solar_longitude_to_sun_distance_au(np.arange(0, 360, 5))
        a, e = C.MARS_SEMI_MAJOR_AXIS_AU, C.MARS_ECCENTRICITY
        assert distances.min() == pytest.approx(a * (1 - e), rel=1e-3)
        assert distances.max() == pytest.approx(a * (1 + e), rel=1e-3)

    def test_perihelion_near_solar_longitude_251(self):
        longitudes = np.arange(0, 360, 1.0)
        closest = longitudes[np.argmin(solar_longitude_to_sun_distance_au(longitudes))]
        assert closest == pytest.approx(251.0, abs=1.0)

    def test_declination_bounded_by_obliquity(self):
        declinations = solar_declination_deg(np.arange(0, 360, 5))
        assert np.abs(declinations).max() == pytest.approx(
            C.MARS_OBLIQUITY_DEG, abs=0.01
        )

    def test_declination_zero_at_equinoxes(self):
        assert solar_declination_deg(0.0) == pytest.approx(0.0, abs=1e-9)
        assert solar_declination_deg(180.0) == pytest.approx(0.0, abs=1e-9)

    def test_irradiance_near_published_mean(self):
        mean = top_of_atmosphere_irradiance(np.arange(0, 360, 1.0)).mean()
        # Published mean solar irradiance at Mars is about 586 W/m^2.
        assert 570 < mean < 600


class TestInsolation:
    def test_equator_receives_more_than_high_latitude_at_equinox(self):
        equator = daily_insolation_kwh_m2(0.0, solar_longitude_deg=180.0)
        high = daily_insolation_kwh_m2(60.0, solar_longitude_deg=180.0)
        assert equator > high > 0

    def test_polar_night_yields_no_sunlight(self):
        # Northern winter solstice: the north pole is in darkness.
        assert daily_insolation_kwh_m2(85.0, solar_longitude_deg=270.0) == 0.0

    def test_polar_summer_exceeds_equator(self):
        # Continuous daylight beats a 12-hour equatorial day.
        pole = daily_insolation_kwh_m2(85.0, solar_longitude_deg=90.0)
        equator = daily_insolation_kwh_m2(0.0, solar_longitude_deg=90.0)
        assert pole > equator

    def test_dust_reduces_surface_energy(self):
        clear = daily_insolation_kwh_m2(0.0, optical_depth=C.TAU_CLEAR)
        storm = daily_insolation_kwh_m2(0.0, optical_depth=C.TAU_GLOBAL_STORM)
        assert storm < clear

    def test_forward_scattering_keeps_some_light_in_a_global_storm(self):
        """Opportunity survived earlier storms on diffuse light alone."""
        clear = daily_insolation_kwh_m2(0.0, optical_depth=C.TAU_CLEAR)
        storm = daily_insolation_kwh_m2(0.0, optical_depth=C.TAU_GLOBAL_STORM)
        assert 0.3 < storm / clear < 0.8

    def test_elevation_thins_the_dust_column(self):
        low = daily_insolation_kwh_m2(0.0, elevation_km=-4.0)
        high = daily_insolation_kwh_m2(0.0, elevation_km=4.0)
        assert high > low

    def test_equinox_insolation_is_physically_plausible(self):
        """Equatorial noon-average insolation is a few kWh/m^2 per sol."""
        assert 2.0 < daily_insolation_kwh_m2(0.0, solar_longitude_deg=180.0) < 6.0

    def test_specific_yield_penalises_latitude(self):
        equator = array_specific_yield_kwh_m2_sol(0.0)
        arcadia = array_specific_yield_kwh_m2_sol(46.7)
        assert arcadia < equator
        # An array at Arcadia's latitude delivers roughly half to two thirds of
        # an equatorial one, which is the cost driver of a polar settlement.
        assert 0.4 < arcadia / equator < 0.8


class TestNightFraction:
    def test_half_the_sol_is_dark_at_equinox(self):
        assert night_fraction(0.0, 180.0) == pytest.approx(0.5, abs=1e-6)

    def test_polar_night_is_total(self):
        assert night_fraction(85.0, 270.0) == pytest.approx(1.0)

    def test_polar_day_has_no_darkness(self):
        assert night_fraction(85.0, 90.0) == pytest.approx(0.0)


class TestIsruEnergy:
    def test_dry_ore_costs_more_energy_per_litre(self):
        rich = isru_energy_per_kg_water(25.0)
        poor = isru_energy_per_kg_water(1.0)
        assert poor > rich

    def test_cost_scales_with_processed_rock_mass(self):
        """Halving the grade roughly doubles the bulk handling term."""
        assert isru_energy_per_kg_water(1.0) / isru_energy_per_kg_water(2.0) > 1.5

    def test_never_below_the_latent_heat_of_sublimation(self):
        # Even at 100 wt% ice, the water still has to be sublimated.
        assert isru_energy_per_kg_water(100.0) > 1.0

    def test_monotonic_in_grade(self):
        grades = np.linspace(0.5, 40.0, 60)
        energies = isru_energy_per_kg_water(grades)
        assert np.all(np.diff(energies) < 0)

    def test_clips_absurd_grades_without_dividing_by_zero(self):
        assert np.isfinite(isru_energy_per_kg_water(0.0))


class TestSettlementDemand:
    def test_zero_population_needs_nothing(self):
        demand = settlement_demand(0, include_propellant=False)
        assert demand.water_makeup_kg == 0
        assert demand.energy_total_kwh == 0

    def test_negative_population_rejected(self):
        with pytest.raises(ValueError):
            settlement_demand(-5)

    def test_demand_scales_with_crew(self):
        small = settlement_demand(10, include_propellant=False)
        large = settlement_demand(100, include_propellant=False)
        assert large.water_makeup_kg == pytest.approx(
            10 * small.water_makeup_kg, rel=1e-9
        )

    def test_tighter_recycling_reduces_makeup_water(self):
        leaky = settlement_demand(100, water_loop_closure=0.80,
                                  include_propellant=False)
        tight = settlement_demand(100, water_loop_closure=0.98,
                                  include_propellant=False)
        assert tight.water_makeup_kg < leaky.water_makeup_kg

    def test_propellant_dominates_crew_water_demand(self):
        """The reason a Mars base is sited on ice is propellant, not drinking."""
        demand = settlement_demand(100)
        assert demand.water_propellant_kg > 5 * demand.water_life_support_kg

    def test_return_capability_has_a_floor_of_one_vehicle(self):
        assert settlement_demand(1).return_flights_per_synod == 1.0

    def test_more_crew_needs_more_vehicles(self):
        assert (
            settlement_demand(500, crew_per_return_flight=50).return_flights_per_synod
            > settlement_demand(50, crew_per_return_flight=50).return_flights_per_synod
        )

    def test_dry_ore_raises_the_energy_bill(self):
        rich = settlement_demand(100, ore_grade_wt_pct=25.0)
        poor = settlement_demand(100, ore_grade_wt_pct=1.0)
        assert poor.energy_total_kwh > rich.energy_total_kwh

    def test_energy_breakdown_sums_to_the_total(self):
        demand = settlement_demand(250, ore_grade_wt_pct=8.0)
        assert sum(demand.energy_breakdown_kwh.values()) == pytest.approx(
            demand.energy_total_kwh
        )

    def test_water_breakdown_sums_to_the_total(self):
        demand = settlement_demand(250, ore_grade_wt_pct=8.0)
        assert sum(demand.water_breakdown_kg.values()) == pytest.approx(
            demand.water_makeup_kg
        )

    def test_per_person_demand_is_in_a_believable_range(self):
        """A crew member needs a few kilowatts, not a few watts or a megawatt."""
        demand = settlement_demand(100, ore_grade_wt_pct=10.0,
                                   include_propellant=False)
        kw_per_person = demand.energy_total_kwh / 100 / 24.66
        assert 1.0 < kw_per_person < 20.0

    def test_electrolysis_feedstock_respects_stoichiometry(self):
        """Water into the cell is 9/8 of the oxygen out of it."""
        demand = settlement_demand(100, water_loop_closure=1.0,
                                   include_propellant=False)
        assert demand.water_makeup_kg == pytest.approx(
            demand.oxygen_kg * 9 / 8, rel=1e-9
        )
