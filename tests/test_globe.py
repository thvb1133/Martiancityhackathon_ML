"""Tests for the 3D views.

The point of these is that the geometry is *derived*, not drawn. A pretty
figure that does not respond to the model's prediction would be decoration, so
the tests assert that the mine grows when the ground gets drier and that the
base grows when the crew does.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from marswater import constants as C
from marswater.globe import (
    MARS_RADIUS_KM,
    settlement_plan,
    water_globe,
)
from marswater.pipeline import run_pipeline
from marswater.simulate import SettlementConfig, rank_sites, size_infrastructure


@pytest.fixture(scope="module")
def pipeline():
    return run_pipeline(random_state=0, include_grid=True, n_survey_samples=900)


@pytest.fixture(scope="module")
def config():
    return SettlementConfig()


@pytest.fixture(scope="module")
def ranked(pipeline, config):
    return rank_sites(pipeline.named_sites, config, 100)


@pytest.fixture(scope="module")
def best_site(pipeline, ranked):
    name = ranked[ranked["feasible"]].iloc[0]["name"]
    return pipeline.named_sites[pipeline.named_sites["name"] == name].iloc[0]


def plan_for(site, population, config, grade=None):
    if grade is not None:
        site = site.copy()
        site["predicted_weh_lower_wt_pct"] = grade
    infra = size_infrastructure(site, population, config)
    return settlement_plan(infra, "test site")


class TestGlobe:
    def test_builds_a_surface_and_site_pins(self, pipeline, ranked):
        figure = water_globe(pipeline.grid, ranked)
        assert len(figure.data) == 3  # surface, pin stems, pin heads

    def test_surface_is_a_closed_sphere(self, pipeline, ranked):
        """The seam must be closed and the poles capped, or the globe has holes."""
        surface = water_globe(pipeline.grid, ranked).data[0]
        radii = np.sqrt(
            np.asarray(surface.x) ** 2
            + np.asarray(surface.y) ** 2
            + np.asarray(surface.z) ** 2
        )
        assert radii.min() > 0.9 * MARS_RADIUS_KM
        # A capped sphere reaches both poles.
        assert np.asarray(surface.z).max() > 0.95 * MARS_RADIUS_KM
        assert np.asarray(surface.z).min() < -0.95 * MARS_RADIUS_KM

    def test_no_exaggeration_gives_a_perfect_sphere(self, pipeline, ranked):
        surface = water_globe(
            pipeline.grid, ranked, elevation_exaggeration=0.0
        ).data[0]
        radii = np.sqrt(
            np.asarray(surface.x) ** 2
            + np.asarray(surface.y) ** 2
            + np.asarray(surface.z) ** 2
        )
        assert np.allclose(radii, MARS_RADIUS_KM, rtol=1e-6)

    def test_exaggeration_produces_relief(self, pipeline, ranked):
        flat = water_globe(pipeline.grid, ranked, elevation_exaggeration=0.0).data[0]
        relief = water_globe(pipeline.grid, ranked, elevation_exaggeration=60.0).data[0]

        def spread(surface):
            radii = np.sqrt(
                np.asarray(surface.x) ** 2
                + np.asarray(surface.y) ** 2
                + np.asarray(surface.z) ** 2
            )
            return radii.max() - radii.min()

        assert spread(relief) > spread(flat)

    def test_surface_colour_is_the_prediction(self, pipeline, ranked):
        surface = water_globe(pipeline.grid, ranked).data[0]
        colours = np.asarray(surface.surfacecolor)
        assert np.isfinite(colours).all()
        assert colours.min() >= 0.0
        assert colours.max() == pytest.approx(
            pipeline.grid["predicted_weh_wt_pct"].max(), rel=0.05
        )

    def test_works_without_site_overlay(self, pipeline):
        assert len(water_globe(pipeline.grid).data) == 1

    def test_pin_colour_marks_viability(self, pipeline, ranked):
        pins = water_globe(pipeline.grid, ranked).data[2]
        colours = list(pins.marker.color)
        assert len(colours) == len(ranked)
        for colour, feasible in zip(colours, ranked["feasible"]):
            assert (colour == "#46f08a") is bool(feasible)


class TestSettlementPlan:
    def test_builds_a_scene(self, best_site, config):
        figure, derived = plan_for(best_site, 100, config)
        # Ground, panel rows, domes, reactors, pit, plant, excavators.
        assert len(figure.data) > 10
        assert derived["array_area_m2"] > 0

    def test_dry_ground_digs_a_bigger_mine(self, best_site, config):
        """The single most important visual: the pit is the ML output."""
        _, wet = plan_for(best_site, 100, config, grade=25.0)
        _, dry = plan_for(best_site, 100, config, grade=2.0)
        assert dry["pit_radius_m"] > 1.5 * wet["pit_radius_m"]

    def test_bigger_crew_needs_more_domes(self, best_site, config):
        _, small = plan_for(best_site, 60, config)
        _, large = plan_for(best_site, 1000, config)
        assert large["domes_needed"] > small["domes_needed"]

    def test_bigger_crew_needs_a_bigger_array(self, best_site, config):
        _, small = plan_for(best_site, 60, config)
        _, large = plan_for(best_site, 1000, config)
        assert large["array_side_m"] > small["array_side_m"]

    def test_array_footprint_matches_the_sizing_result(self, best_site, config):
        infra = size_infrastructure(best_site, 100, config)
        _, derived = settlement_plan(infra, "test site")
        assert derived["array_area_m2"] == pytest.approx(infra.pv_area_m2)
        assert derived["array_side_m"] == pytest.approx(np.sqrt(infra.pv_area_m2))

    def test_domes_are_sized_from_pressurised_volume(self, best_site, config):
        _, derived = plan_for(best_site, 1000, config)
        implied = derived["domes_needed"] * derived["crew_per_dome"]
        assert implied >= 1000

    def test_pit_volume_matches_a_launch_window_of_excavation(
        self, best_site, config
    ):
        infra = size_infrastructure(best_site, 100, config)
        _, derived = settlement_plan(infra, "test site")
        expected = infra.regolith_kg_per_sol / 1600.0 * C.SYNOD_SOLS
        assert derived["excavated_m3_per_synod"] == pytest.approx(expected)

    def test_drawn_geometry_is_capped_for_rendering(self, best_site, config):
        """A 4,000-person base must not try to draw hundreds of domes."""
        _, derived = plan_for(best_site, 4000, config)
        assert derived["domes_drawn"] <= 28
        assert derived["domes_drawn"] <= derived["domes_needed"]
        assert derived["panel_rows_drawn"] <= 22

    def test_plan_survives_the_smallest_crew(self, best_site, config):
        figure, derived = plan_for(best_site, 1, config)
        assert len(figure.data) > 5
        assert derived["domes_needed"] >= 1

    def test_reactor_count_follows_the_configuration(self, best_site):
        infra = size_infrastructure(
            best_site, 100, SettlementConfig(fission_units=7)
        )
        assert infra.fission_units == 7
        assert settlement_plan(infra, "test site")[0] is not None
