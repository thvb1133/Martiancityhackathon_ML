"""Tests for the settlement sizing and ranking simulation."""

from __future__ import annotations

from dataclasses import replace

import pandas as pd
import pytest

from marswater import constants as C
from marswater.pipeline import run_pipeline
from marswater.simulate import (
    SettlementConfig,
    dust_storm_resilience,
    landability,
    max_supportable_population,
    minimum_fission_units,
    mission_architecture_comparison,
    population_sweep,
    rank_sites,
    size_infrastructure,
)


def make_site(**overrides) -> pd.Series:
    site = {
        "name": "test site",
        "latitude_deg": 40.0,
        "longitude_deg": 0.0,
        "elevation_km": -3.0,
        "slope_deg": 3.0,
        "rock_abundance": 0.08,
        "predicted_weh_lower_wt_pct": 10.0,
    }
    site.update(overrides)
    return pd.Series(site)


@pytest.fixture(scope="module")
def pipeline():
    return run_pipeline(random_state=0, include_grid=False, n_survey_samples=900)


@pytest.fixture
def config():
    return SettlementConfig()


class TestLandability:
    def test_flat_low_rock_terrain_is_landable(self):
        assert landability(make_site())[0] is True

    def test_steep_terrain_is_rejected(self):
        landable, note = landability(make_site(slope_deg=25.0))
        assert landable is False
        assert "slope" in note

    def test_boulder_fields_are_rejected(self):
        landable, note = landability(make_site(rock_abundance=0.45))
        assert landable is False
        assert "rock" in note


class TestInfrastructureSizing:
    def test_zero_population_rejected(self, config):
        with pytest.raises(ValueError):
            size_infrastructure(make_site(), 0, config)

    def test_dry_ground_needs_more_rock_moved(self, config):
        wet = size_infrastructure(make_site(predicted_weh_lower_wt_pct=25.0),
                                  100, config)
        dry = size_infrastructure(make_site(predicted_weh_lower_wt_pct=1.0),
                                  100, config)
        assert dry.regolith_kg_per_sol > 10 * wet.regolith_kg_per_sol
        assert dry.excavator_units > wet.excavator_units

    def test_dry_ground_costs_more_landed_mass(self, config):
        wet = size_infrastructure(make_site(predicted_weh_lower_wt_pct=25.0),
                                  100, config)
        dry = size_infrastructure(make_site(predicted_weh_lower_wt_pct=2.0),
                                  100, config)
        assert dry.total_mass_kg > wet.total_mass_kg

    def test_high_latitude_needs_more_array(self, config):
        equatorial = size_infrastructure(make_site(latitude_deg=5.0), 100, config)
        polar = size_infrastructure(make_site(latitude_deg=60.0), 100, config)
        assert polar.pv_area_m2 > equatorial.pv_area_m2

    def test_reactors_displace_array_area(self):
        site = make_site()
        few = size_infrastructure(site, 100, SettlementConfig(fission_units=1))
        many = size_infrastructure(site, 100, SettlementConfig(fission_units=40))
        assert many.pv_area_m2 < few.pv_area_m2

    def test_enough_reactors_remove_the_array_entirely(self):
        infra = size_infrastructure(make_site(), 20,
                                    SettlementConfig(fission_units=300))
        assert infra.pv_area_m2 == 0.0
        assert infra.battery_capacity_kwh == 0.0

    def test_mass_breakdown_sums_to_the_total(self, config):
        infra = size_infrastructure(make_site(), 100, config)
        assert sum(infra.mass_breakdown_kg.values()) == pytest.approx(
            infra.total_mass_kg
        )

    def test_power_and_water_masses_partition_the_total(self, config):
        infra = size_infrastructure(make_site(), 100, config)
        assert (
            infra.power_infrastructure_mass_kg + infra.water_infrastructure_mass_kg
        ) == pytest.approx(infra.total_mass_kg)

    def test_launch_count_uses_the_payload_capacity(self, config):
        infra = size_infrastructure(make_site(), 100, config)
        assert infra.launches == pytest.approx(
            infra.total_mass_kg / C.STARSHIP_PAYLOAD_KG
        )

    def test_demand_grows_with_crew(self, config):
        small = size_infrastructure(make_site(), 50, config)
        large = size_infrastructure(make_site(), 500, config)
        assert large.energy_demand_kwh_per_sol > small.energy_demand_kwh_per_sol
        assert large.total_mass_kg > small.total_mass_kg

    def test_unlandable_terrain_is_infeasible_at_any_size(self, config):
        infra = size_infrastructure(make_site(slope_deg=30.0), 10, config)
        assert infra.feasible is False
        assert "slope" in infra.limiting_factor

    def test_very_dry_ground_exceeds_the_mining_fleet_limit(self, config):
        infra = size_infrastructure(make_site(predicted_weh_lower_wt_pct=0.5),
                                    2000, config)
        assert infra.feasible is False
        assert "mining fleet" in infra.limiting_factor

    def test_propellant_dominates_water_demand_when_enabled(self, config):
        with_return = size_infrastructure(make_site(), 100, config)
        one_way = size_infrastructure(
            make_site(), 100, replace(config, include_propellant=False)
        )
        assert with_return.water_makeup_kg_per_sol > (
            5 * one_way.water_makeup_kg_per_sol
        )
        assert one_way.water_propellant_kg_per_sol == 0.0

    def test_dust_storms_require_more_collector_area(self):
        site = make_site()
        clear = size_infrastructure(site, 100, SettlementConfig())
        storm = size_infrastructure(
            site, 100, SettlementConfig(optical_depth=C.TAU_GLOBAL_STORM)
        )
        assert storm.pv_area_m2 > clear.pv_area_m2


class TestPopulationCeiling:
    def test_ceiling_is_a_real_boundary(self, config):
        site = make_site()
        ceiling, _ = max_supportable_population(site, config)
        assert size_infrastructure(site, ceiling, config).feasible
        assert not size_infrastructure(site, ceiling + 1, config).feasible

    def test_unlandable_site_supports_nobody(self, config):
        ceiling, note = max_supportable_population(
            make_site(rock_abundance=0.5), config
        )
        assert ceiling == 0
        assert "rock" in note

    def test_wetter_ground_raises_the_ceiling(self, config):
        wet, _ = max_supportable_population(
            make_site(predicted_weh_lower_wt_pct=25.0), config
        )
        dry, _ = max_supportable_population(
            make_site(predicted_weh_lower_wt_pct=1.5), config
        )
        assert wet > dry

    def test_more_reactors_raise_the_ceiling(self):
        site = make_site()
        few, _ = max_supportable_population(site, SettlementConfig(fission_units=2))
        many, _ = max_supportable_population(site, SettlementConfig(fission_units=60))
        assert many >= few


class TestPrescription:
    def test_more_reactors_reopen_a_power_limited_site(self):
        site = make_site(predicted_weh_lower_wt_pct=25.0)
        config = SettlementConfig(fission_units=1)
        ceiling, _ = max_supportable_population(site, config)
        target = ceiling + 50
        assert not size_infrastructure(site, target, config).feasible
        needed = minimum_fission_units(site, target, config)
        assert needed is not None
        assert size_infrastructure(
            site, target, replace(config, fission_units=needed)
        ).feasible

    def test_power_cannot_fix_a_mining_limited_site(self):
        site = make_site(predicted_weh_lower_wt_pct=0.5)
        assert minimum_fission_units(site, 5000, SettlementConfig()) is None


class TestRanking:
    def test_ranking_orders_by_landed_mass(self, pipeline, config):
        ranked = rank_sites(pipeline.named_sites, config, 100)
        feasible = ranked[ranked["feasible"]]
        assert feasible["landed_mass_t"].is_monotonic_increasing

    def test_infeasible_sites_are_listed_last(self, pipeline, config):
        ranked = rank_sites(pipeline.named_sites, config, 100)
        if (~ranked["feasible"]).any():
            last_feasible = ranked["feasible"].to_numpy().nonzero()[0].max()
            first_infeasible = (~ranked["feasible"]).to_numpy().nonzero()[0].min()
            assert last_feasible < first_infeasible

    def test_every_site_is_scored_exactly_once(self, pipeline, config):
        ranked = rank_sites(pipeline.named_sites, config, 100)
        assert len(ranked) == len(pipeline.named_sites)
        assert ranked["name"].is_unique

    def test_top_site_is_water_rich(self, pipeline, config):
        """With propellant production on, the winner has to sit on ice."""
        ranked = rank_sites(pipeline.named_sites, config, 100)
        best = ranked[ranked["feasible"]].iloc[0]
        assert best["water_grade_wt_pct"] > 10.0

    def test_ranking_changes_when_propellant_is_dropped(self, pipeline, config):
        """The water prediction has to be load bearing, not decorative."""
        with_return = rank_sites(pipeline.named_sites, config, 100)
        one_way = rank_sites(
            pipeline.named_sites, replace(config, include_propellant=False), 100
        )
        assert list(with_return["name"]) != list(one_way["name"])


class TestSweepsAndScenarios:
    def test_viability_shrinks_as_the_city_grows(self, pipeline, config):
        sweep = population_sweep(pipeline.named_sites, config,
                                 populations=(20, 500, 4000))
        assert sweep["sites_viable"].is_monotonic_decreasing
        assert sweep["sites_viable"].iloc[0] > sweep["sites_viable"].iloc[-1]

    def test_sweep_reports_every_requested_population(self, pipeline, config):
        populations = (50, 200, 800)
        sweep = population_sweep(pipeline.named_sites, config, populations)
        assert list(sweep["population"]) == list(populations)

    def test_architecture_comparison_returns_both_cases(self, pipeline, config):
        comparison = mission_architecture_comparison(
            pipeline.named_sites, config, 100
        )
        assert len(comparison) == 2
        assert comparison["water_t_per_sol"].iloc[1] > (
            comparison["water_t_per_sol"].iloc[0]
        )

    def test_return_capability_shortens_the_shortlist(self, pipeline, config):
        comparison = mission_architecture_comparison(
            pipeline.named_sites, config, 100
        )
        assert comparison["sites_viable"].iloc[1] < (
            comparison["sites_viable"].iloc[0]
        )

    def test_storms_reduce_capacity_monotonically(self, pipeline, config):
        site = pipeline.named_sites.iloc[0]
        storms = dust_storm_resilience(site, config, 50)
        assert len(storms) == 3
        assert storms["specific_yield_kwh_m2_sol"].is_monotonic_decreasing
        assert storms["max_population"].is_monotonic_decreasing


class TestPipeline:
    def test_pipeline_predicts_for_every_named_site(self, pipeline):
        assert len(pipeline.named_sites) >= 20
        assert pipeline.named_sites["predicted_weh_wt_pct"].notna().all()

    def test_pipeline_predictions_track_the_hidden_truth(self, pipeline):
        """Sanity check that scoring unseen sites is not producing noise."""
        correlation = pipeline.named_sites[
            ["predicted_weh_wt_pct", "latent_truth_wt_pct"]
        ].corr().iloc[0, 1]
        assert correlation > 0.75

    def test_pipeline_is_reproducible(self):
        a = run_pipeline(random_state=1, include_grid=False, n_survey_samples=600)
        b = run_pipeline(random_state=1, include_grid=False, n_survey_samples=600)
        assert a.named_sites["predicted_weh_wt_pct"].equals(
            b.named_sites["predicted_weh_wt_pct"]
        )
