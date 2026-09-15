"""End-to-end pipeline: train the model, score the sites, rank the outcomes."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .dataset import generate_features, labelled_survey, latent_water_content
from .model import ModelReport, WaterYieldModel
from .simulate import SettlementConfig, rank_sites
from .sites import named_sites_frame, survey_grid


@dataclass
class PipelineResult:
    model: WaterYieldModel
    report: ModelReport
    named_sites: pd.DataFrame
    grid: pd.DataFrame

    def ranking(
        self, config: SettlementConfig, target_population: int
    ) -> pd.DataFrame:
        return rank_sites(self.named_sites, config, target_population)


def run_pipeline(
    random_state: int = 0,
    include_grid: bool = True,
    n_survey_samples: int = 4200,
) -> PipelineResult:
    """Train on the survey, then predict water yield for every candidate site.

    The named sites and the display grid are featurised with different random
    seeds from the training survey, so nothing the model is scored on was seen
    during training.
    """
    survey = labelled_survey(n_samples=n_survey_samples, seed=random_state + 42)
    model = WaterYieldModel(random_state=random_state).fit(survey)

    named = generate_features(named_sites_frame(), seed=random_state + 101)
    named = pd.concat(
        [named, model.predict_with_uncertainty(named)], axis=1
    )
    named["latent_truth_wt_pct"] = latent_water_content(named)

    grid = pd.DataFrame()
    if include_grid:
        grid = generate_features(survey_grid(seed=random_state + 7), seed=random_state + 202)
        grid = pd.concat([grid, model.predict_with_uncertainty(grid)], axis=1)
        grid["latent_truth_wt_pct"] = latent_water_content(grid)

    assert model.report is not None
    return PipelineResult(
        model=model, report=model.report, named_sites=named, grid=grid
    )
