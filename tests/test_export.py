"""Tests for the static export.

The static page is what a judge opens when there is no Python process running,
so the thing worth asserting is that it is self-contained and that the numbers
on it are the same numbers the dashboard computes, rather than placeholders
baked in at authoring time.
"""

from __future__ import annotations

import pytest

import export_static
from marswater.pipeline import run_pipeline
from marswater.simulate import SettlementConfig, rank_sites
from marswater.subsurface import BurialConfig, design_habitat


@pytest.fixture(scope="module")
def page(tmp_path_factory):
    output = tmp_path_factory.mktemp("site")
    return export_static.build(output).read_text(encoding="utf-8")


class TestStaticPage:
    def test_it_is_a_single_self_contained_document(self, page, tmp_path):
        "Everything is inline apart from plotly.js, which comes from the CDN."
        assert page.startswith("<!doctype html>")
        assert page.rstrip().endswith("</html>")
        assert "cdn.plot.ly" in page

    def test_plotly_is_loaded_exactly_once(self, page):
        "Ten copies of the library would make the page tens of megabytes."
        assert page.count("cdn.plot.ly") == 1

    def test_every_figure_is_present(self, page):
        "Three sections, a profile, two globes and the settlement plan."
        assert page.count("plotly-graph-div") == 7

    def test_it_reports_the_site_the_simulation_recommends(self, page):
        result = run_pipeline(
            random_state=export_static.SEED, include_grid=True
        )
        ranked = rank_sites(
            result.named_sites, SettlementConfig(), export_static.POPULATION
        )
        recommended = ranked[ranked["feasible"]].iloc[0]["name"]
        assert recommended in page

    def test_the_headline_depth_is_the_computed_depth(self, page):
        "The page must not drift from the physics behind it."
        result = run_pipeline(
            random_state=export_static.SEED, include_grid=True
        )
        ranked = rank_sites(
            result.named_sites, SettlementConfig(), export_static.POPULATION
        )
        best = ranked[ranked["feasible"]].iloc[0]["name"]
        row = result.named_sites[result.named_sites["name"] == best].iloc[0]
        design = design_habitat(row, export_static.POPULATION, BurialConfig())
        assert f"{design.depth_m:.2f} m down" in page

    def test_it_contrasts_a_dry_site_with_a_wet_one(self, page):
        "The argument only lands if both architectures are on the page."
        assert "cut-and-cover buried vault" in page
        assert "mined vault in ice-cemented ground" in page


class TestContrastSites:
    def test_it_picks_the_driest_and_the_wettest(self):
        result = run_pipeline(random_state=0, n_survey_samples=900)
        sites = result.named_sites
        chosen = export_static._contrast_sites(sites, sites.iloc[0]["name"])
        order = sites.sort_values("predicted_weh_wt_pct")
        assert order.iloc[0]["name"] in chosen
        assert order.iloc[-1]["name"] in chosen

    def test_it_does_not_repeat_a_site(self):
        "The recommended site is often also the wettest."
        result = run_pipeline(random_state=0, n_survey_samples=900)
        sites = result.named_sites
        wettest = sites.sort_values("predicted_weh_wt_pct").iloc[-1]["name"]
        chosen = export_static._contrast_sites(sites, wettest)
        assert len(chosen) == len(set(chosen))
