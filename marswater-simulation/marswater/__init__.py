"""MARSWATER -- water-driven site selection and resilience planning for Mars.

One machine-learning model predicts subsurface water yield from orbital
observables. Everything after that is deterministic physics: solar insolation,
in-situ resource extraction energy, closed-loop life support demand, and the
crew size a site can actually sustain.
"""

from .model import WaterYieldModel, train_default_model
from .pipeline import PipelineResult, run_pipeline
from .simulate import (
    Infrastructure,
    SettlementConfig,
    dust_storm_resilience,
    max_supportable_population,
    minimum_fission_units,
    mission_architecture_comparison,
    population_sweep,
    rank_sites,
    size_infrastructure,
)

__version__ = "1.0.0"

__all__ = [
    "Infrastructure",
    "PipelineResult",
    "SettlementConfig",
    "WaterYieldModel",
    "dust_storm_resilience",
    "max_supportable_population",
    "minimum_fission_units",
    "mission_architecture_comparison",
    "population_sweep",
    "rank_sites",
    "run_pipeline",
    "size_infrastructure",
    "train_default_model",
]
