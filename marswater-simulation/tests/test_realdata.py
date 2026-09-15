"""Tests for the real-data adapter.

These are the tests that back the feasibility claim. It is easy to write
"real data could be swapped in" in a README; these assert that a survey loaded
from a file actually trains the model, and that a genuine georeferenced raster
is sampled at the right coordinates.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from marswater.dataset import TARGET_COLUMN, labelled_survey
from marswater.model import WaterYieldModel
from marswater.realdata import (
    REQUIRED_TRAINING_COLUMNS,
    SurveyValidationError,
    describe_expected_schema,
    load_survey,
    sample_rasters,
    validate_survey,
)

rasterio = pytest.importorskip("rasterio")


@pytest.fixture(scope="module")
def survey():
    return labelled_survey(n_samples=700, seed=17)


@pytest.fixture
def survey_csv(tmp_path, survey):
    path = tmp_path / "survey.csv"
    survey[list(REQUIRED_TRAINING_COLUMNS)].to_csv(path, index=False)
    return path


class TestValidation:
    def test_a_good_survey_passes(self, survey):
        report = validate_survey(survey)
        assert report.ok, report.problems()
        assert "usable" in str(report)

    def test_missing_columns_are_all_reported_at_once(self, survey):
        report = validate_survey(survey.drop(columns=["albedo", "slope_deg"]))
        assert not report.ok
        assert set(report.missing_columns) == {"albedo", "slope_deg"}

    def test_non_numeric_columns_are_caught(self, survey):
        broken = survey.copy()
        broken["albedo"] = "bright"
        assert "albedo" in validate_survey(broken).non_numeric_columns

    def test_empty_columns_are_caught(self, survey):
        broken = survey.copy()
        broken["thermal_inertia"] = np.nan
        assert "thermal_inertia" in validate_survey(broken).all_null_columns

    def test_unit_errors_are_caught(self, survey):
        """Albedo given as a percentage is the classic real-data mistake."""
        broken = survey.copy()
        broken["albedo"] = broken["albedo"] * 100.0
        report = validate_survey(broken)
        assert not report.ok
        assert "albedo" in report.out_of_range
        assert any("check units" in problem for problem in report.problems())

    def test_null_counts_are_reported(self, survey):
        partial = survey.copy()
        partial.loc[partial.index[:5], "albedo"] = np.nan
        assert validate_survey(partial).null_counts["albedo"] == 5

    def test_schema_description_covers_every_required_column(self):
        schema = describe_expected_schema()
        assert set(schema["column"]) == set(REQUIRED_TRAINING_COLUMNS)
        assert (schema["role"] == "label").sum() == 1


class TestLoadSurvey:
    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_survey(tmp_path / "absent.csv")

    def test_round_trips_through_csv(self, survey_csv, survey):
        loaded = load_survey(survey_csv)
        assert len(loaded) == len(survey)
        for column in REQUIRED_TRAINING_COLUMNS:
            assert column in loaded

    def test_round_trips_through_parquet(self, tmp_path, survey):
        pytest.importorskip("pyarrow")
        path = tmp_path / "survey.parquet"
        survey[list(REQUIRED_TRAINING_COLUMNS)].to_parquet(path, index=False)
        assert len(load_survey(path)) == len(survey)

    def test_absolute_latitude_is_derived_when_absent(self, tmp_path, survey):
        path = tmp_path / "signed.csv"
        frame = survey[list(REQUIRED_TRAINING_COLUMNS)].copy()
        frame["latitude_deg"] = -frame["abs_latitude_deg"]
        frame = frame.drop(columns=["abs_latitude_deg"])
        frame.to_csv(path, index=False)
        loaded = load_survey(path)
        assert (loaded["abs_latitude_deg"] >= 0).all()

    def test_a_bad_survey_raises_with_the_reason(self, tmp_path, survey):
        path = tmp_path / "bad.csv"
        survey.drop(columns=["albedo"]).to_csv(path, index=False)
        with pytest.raises(SurveyValidationError, match="albedo"):
            load_survey(path)

    def test_incomplete_rows_are_dropped(self, tmp_path, survey):
        path = tmp_path / "holes.csv"
        frame = survey[list(REQUIRED_TRAINING_COLUMNS)].copy()
        frame.loc[frame.index[:10], "thermal_inertia"] = np.nan
        frame.to_csv(path, index=False)
        assert len(load_survey(path)) == len(frame) - 10

    def test_a_survey_where_every_row_has_a_hole_raises(self, tmp_path, survey):
        """No column is entirely empty, but no row is complete either."""
        path = tmp_path / "allholes.csv"
        frame = survey[list(REQUIRED_TRAINING_COLUMNS)].copy()
        even, odd = frame.index[::2], frame.index[1::2]
        frame.loc[even, "albedo"] = np.nan
        frame.loc[odd, "slope_deg"] = np.nan
        frame.to_csv(path, index=False)
        assert validate_survey(frame).ok  # the schema itself is fine
        with pytest.raises(SurveyValidationError, match="missing value"):
            load_survey(path)


class TestDeploymentPath:
    def test_a_file_loaded_survey_trains_the_model(self, survey_csv):
        """The feasibility claim, asserted rather than described.

        This is the exact call the project would make against real Odyssey and
        TES products: load from disk, hand it to the same estimator, and every
        downstream stage is untouched.
        """
        loaded = load_survey(survey_csv)
        model = WaterYieldModel(random_state=0).fit(loaded)
        assert model.report is not None
        assert model.report.test_r2 > 0.7
        assert model.report.test_r2 > model.report.mean_baseline_test_r2

    def test_the_model_scores_sites_from_a_loaded_survey(self, survey_csv):
        loaded = load_survey(survey_csv)
        model = WaterYieldModel(random_state=0).fit(loaded)
        predictions = model.predict(loaded.head(20))
        assert len(predictions) == 20
        assert np.isfinite(predictions).all()


def write_test_raster(path, values, west=-180.0, north=90.0, resolution=1.0,
                      nodata=None):
    """Write a small global GeoTIFF in plate carrée, as MOLA products are."""
    from rasterio.transform import from_origin

    height, width = values.shape
    with rasterio.open(
        path, "w", driver="GTiff", height=height, width=width, count=1,
        dtype="float32", crs="EPSG:4326",
        transform=from_origin(west, north, resolution, resolution),
        nodata=nodata,
    ) as dataset:
        dataset.write(values.astype("float32"), 1)
    return path


class TestRasterSampling:
    @pytest.fixture
    def ramp_raster(self, tmp_path):
        """A raster whose value equals its column index, so sampling is checkable."""
        values = np.tile(np.arange(360, dtype="float32"), (180, 1))
        return write_test_raster(tmp_path / "ramp.tif", values)

    def test_samples_at_the_right_longitude(self, ramp_raster):
        points = pd.DataFrame(
            {"latitude_deg": [0.0, 0.0, 0.0], "longitude_deg": [-180.0, -90.0, 90.0]}
        )
        sampled = sample_rasters(points, {"ramp": ramp_raster})
        # Column index equals longitude + 180 for a 1-degree global grid.
        assert sampled["ramp"].tolist() == [0.0, 90.0, 270.0]

    def test_zero_to_360_convention_is_honoured(self, tmp_path, ramp_raster):
        """A 0..360 raster and a -180..180 raster need opposite wrapping.

        Getting this wrong samples the far side of the planet and still
        returns a plausible-looking number, which is why the convention is a
        required argument rather than an inference.
        """
        values = np.tile(np.arange(360, dtype="float32"), (180, 1))
        eastward = write_test_raster(tmp_path / "east.tif", values, west=0.0)

        point = pd.DataFrame({"latitude_deg": [0.0], "longitude_deg": [270.0]})
        signed = sample_rasters(point, {"ramp": ramp_raster})
        unsigned = sample_rasters(
            point, {"ramp": eastward}, longitude_convention="0-360"
        )
        # 270 E is -90 E, which is column 90 of a raster starting at -180.
        assert signed["ramp"].iloc[0] == 90.0
        # The same place is column 270 of a raster starting at 0.
        assert unsigned["ramp"].iloc[0] == 270.0

    def test_samples_several_rasters_at_once(self, tmp_path, ramp_raster):
        flat = write_test_raster(
            tmp_path / "flat.tif", np.full((180, 360), 7.0, dtype="float32")
        )
        points = pd.DataFrame({"latitude_deg": [10.0], "longitude_deg": [20.0]})
        sampled = sample_rasters(points, {"ramp": ramp_raster, "flat": flat})
        assert sampled["flat"].iloc[0] == 7.0
        assert sampled["ramp"].iloc[0] == 200.0

    def test_nodata_becomes_nan(self, tmp_path):
        values = np.full((180, 360), -9999.0, dtype="float32")
        raster = write_test_raster(
            tmp_path / "nodata.tif", values, nodata=-9999.0
        )
        points = pd.DataFrame({"latitude_deg": [0.0], "longitude_deg": [0.0]})
        sampled = sample_rasters(points, {"weh": raster})
        assert np.isnan(sampled["weh"].iloc[0])

    def test_original_points_are_preserved(self, ramp_raster):
        points = pd.DataFrame(
            {"name": ["Arcadia"], "latitude_deg": [46.7], "longitude_deg": [-168.0]}
        )
        sampled = sample_rasters(points, {"ramp": ramp_raster})
        assert sampled["name"].iloc[0] == "Arcadia"
        assert sampled["latitude_deg"].iloc[0] == 46.7

    def test_missing_coordinates_raise(self, ramp_raster):
        with pytest.raises(KeyError):
            sample_rasters(pd.DataFrame({"lat": [0.0]}), {"ramp": ramp_raster})

    def test_missing_raster_file_raises(self, tmp_path):
        points = pd.DataFrame({"latitude_deg": [0.0], "longitude_deg": [0.0]})
        with pytest.raises(FileNotFoundError):
            sample_rasters(points, {"weh": tmp_path / "absent.tif"})

    def test_bad_longitude_convention_raises(self, ramp_raster):
        points = pd.DataFrame({"latitude_deg": [0.0], "longitude_deg": [0.0]})
        with pytest.raises(ValueError, match="longitude_convention"):
            sample_rasters(points, {"ramp": ramp_raster},
                           longitude_convention="degrees")

    def test_real_sites_can_be_populated_from_rasters(self, tmp_path):
        """End to end: the named sites, featurised from georeferenced files."""
        from marswater.sites import named_sites_frame

        weh = write_test_raster(
            tmp_path / "weh.tif",
            np.tile(np.linspace(0, 30, 180, dtype="float32")[:, None], (1, 360)),
        )
        sampled = sample_rasters(named_sites_frame(), {TARGET_COLUMN: weh})
        assert len(sampled) == len(named_sites_frame())
        assert sampled[TARGET_COLUMN].notna().all()
        # The ramp increases southward, so southern sites read higher.
        northern = sampled[sampled["latitude_deg"] > 30][TARGET_COLUMN].mean()
        southern = sampled[sampled["latitude_deg"] < -30][TARGET_COLUMN].mean()
        assert southern > northern
