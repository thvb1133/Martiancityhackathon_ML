"""Tests for the dataset surrogate and the water-yield model."""

from __future__ import annotations

import numpy as np
import pytest

from marswater.dataset import (
    FEATURE_COLUMNS,
    TARGET_COLUMN,
    generate_features,
    labelled_survey,
    latent_water_content,
)
from marswater.model import WaterYieldModel
from marswater.sites import named_sites_frame, survey_grid, synthetic_elevation_km


@pytest.fixture(scope="module")
def survey():
    return labelled_survey(n_samples=900, seed=3)


@pytest.fixture(scope="module")
def trained(survey):
    return WaterYieldModel(random_state=3).fit(survey)


class TestSites:
    def test_named_sites_have_plausible_coordinates(self):
        frame = named_sites_frame()
        assert len(frame) >= 20
        assert frame["latitude_deg"].between(-90, 90).all()
        assert frame["longitude_deg"].between(-180, 360).all()
        # Mars' surface spans roughly -8 km (Hellas) to +21 km (Olympus Mons).
        assert frame["elevation_km"].between(-9, 22).all()

    def test_site_names_are_unique(self):
        names = named_sites_frame()["name"]
        assert names.is_unique

    def test_synthetic_topography_reproduces_the_dichotomy(self):
        northern_plain = synthetic_elevation_km(45.0, 0.0)
        southern_highland = synthetic_elevation_km(-40.0, 180.0)
        assert northern_plain < southern_highland

    def test_synthetic_topography_reproduces_tharsis(self):
        assert synthetic_elevation_km(2.0, -100.0) > synthetic_elevation_km(2.0, 0.0)

    def test_grid_covers_both_hemispheres(self):
        grid = survey_grid()
        assert grid["latitude_deg"].min() < -60
        assert grid["latitude_deg"].max() > 60
        assert len(grid) > 500


class TestFeatures:
    def test_missing_columns_raise(self):
        import pandas as pd

        with pytest.raises(KeyError):
            generate_features(pd.DataFrame({"latitude_deg": [0.0]}))

    def test_all_feature_columns_are_produced(self):
        featured = generate_features(named_sites_frame(), seed=1)
        for column in FEATURE_COLUMNS:
            assert column in featured, column
            assert featured[column].notna().all()

    def test_features_stay_in_physical_ranges(self):
        featured = generate_features(survey_grid(), seed=1)
        assert featured["albedo"].between(0.0, 1.0).all()
        assert featured["thermal_inertia"].between(20, 900).all()
        assert featured["slope_deg"].between(0, 90).all()
        assert featured["rock_abundance"].between(0, 1).all()
        assert featured["summer_peak_temp_k"].between(140, 320).all()
        assert featured["mantling_unit_index"].between(0, 1).all()

    def test_generation_is_reproducible(self):
        a = generate_features(named_sites_frame(), seed=5)
        b = generate_features(named_sites_frame(), seed=5)
        assert np.allclose(a["thermal_inertia"], b["thermal_inertia"])

    def test_different_seeds_give_different_observables(self):
        a = generate_features(named_sites_frame(), seed=5)
        b = generate_features(named_sites_frame(), seed=6)
        assert not np.allclose(a["thermal_inertia"], b["thermal_inertia"])


class TestLatentWaterField:
    def test_high_latitudes_are_wetter_than_the_equator(self):
        """Shallow ground ice is stable poleward of about 50 degrees."""
        featured = generate_features(survey_grid(), seed=2)
        water = latent_water_content(featured)
        polar = water[featured["abs_latitude_deg"] > 55].mean()
        equatorial = water[featured["abs_latitude_deg"] < 15].mean()
        assert polar > 3 * equatorial

    def test_water_content_stays_in_range(self):
        featured = generate_features(survey_grid(), seed=2)
        water = latent_water_content(featured)
        assert water.min() >= 0.5
        assert water.max() <= 60.0

    def test_geology_matters_at_fixed_latitude(self):
        """Latitude alone cannot explain the field; the mantling unit also does."""
        import pandas as pd

        base = pd.DataFrame({
            "abs_latitude_deg": [42.0, 42.0],
            "elevation_km": [-3.5, -3.5],
            "thermal_inertia": [300.0, 300.0],
            "albedo": [0.20, 0.20],
            "mantling_unit_index": [0.05, 0.95],
        })
        dry, wet = latent_water_content(base)
        assert wet > dry * 1.5


class TestSurvey:
    def test_survey_has_features_and_labels(self, survey):
        assert len(survey) == 900
        assert TARGET_COLUMN in survey
        assert survey[TARGET_COLUMN].notna().all()
        assert (survey[TARGET_COLUMN] > 0).all()

    def test_labels_track_the_latent_field_but_are_noisy(self, survey):
        truth = survey["latent_truth_wt_pct"]
        observed = survey[TARGET_COLUMN]
        assert np.corrcoef(truth, observed)[0, 1] > 0.9
        assert not np.allclose(truth, observed)


class TestWaterYieldModel:
    def test_predicting_before_fitting_raises(self):
        with pytest.raises(RuntimeError):
            WaterYieldModel().predict(generate_features(named_sites_frame()))

    def test_recovers_the_latent_relationship(self, trained):
        """The model has to learn the stability field it is never shown."""
        assert trained.report.test_r2 > 0.80

    def test_beats_a_mean_baseline_decisively(self, trained):
        assert trained.report.test_r2 > trained.report.mean_baseline_test_r2 + 0.5

    def test_beats_a_linear_baseline(self, trained):
        """The latitude-geology interaction is not linearly representable."""
        assert trained.report.test_r2 > trained.report.ridge_test_r2

    def test_cross_validation_agrees_with_the_held_out_score(self, trained):
        assert abs(trained.report.cv_r2_mean - trained.report.test_r2) < 0.15

    def test_latitude_is_the_leading_predictor(self, trained):
        leading = next(iter(trained.report.feature_importance))
        assert leading == "abs_latitude_deg"

    def test_predictions_are_non_negative(self, trained):
        predictions = trained.predict(generate_features(named_sites_frame(), seed=9))
        assert (predictions > 0).all()

    def test_uncertainty_bounds_bracket_the_prediction(self, trained):
        sites = generate_features(named_sites_frame(), seed=9)
        bounds = trained.predict_with_uncertainty(sites)
        assert (bounds["predicted_weh_lower_wt_pct"]
                <= bounds["predicted_weh_wt_pct"]).all()
        assert (bounds["predicted_weh_wt_pct"]
                <= bounds["predicted_weh_upper_wt_pct"]).all()

    def test_lower_bound_is_floored_at_a_physical_minimum(self, trained):
        sites = generate_features(survey_grid(), seed=9)
        bounds = trained.predict_with_uncertainty(sites)
        assert bounds["predicted_weh_lower_wt_pct"].min() >= 0.5

    def test_wet_sites_are_predicted_wetter_than_dry_ones(self, trained):
        sites = generate_features(survey_grid(), seed=11)
        predictions = trained.predict(sites)
        polar = predictions[sites["abs_latitude_deg"].to_numpy() > 55].mean()
        equatorial = predictions[sites["abs_latitude_deg"].to_numpy() < 15].mean()
        assert polar > equatorial
