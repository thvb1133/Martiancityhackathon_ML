"""Synthetic dataset generation for the habitat risk classifier.

No external data is required: samples are drawn from plausible sensor ranges and
labelled with a transparent, rule-based risk score plus a little noise so the
model has to learn a real (non-trivial) decision boundary. Keeping the data
self-contained means the whole pipeline runs offline.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import CLASS_LABELS, FEATURE_NAMES, RANDOM_SEED


def _risk_score(row: dict) -> float:
    """Return a continuous danger score; higher means more dangerous."""
    score = 0.0
    # Oxygen too low or too high is dangerous (ideal ~21%).
    score += max(0.0, 19.0 - row["oxygen_pct"]) * 1.4
    score += max(0.0, row["oxygen_pct"] - 24.0) * 1.0
    # CO2 buildup.
    score += max(0.0, row["co2_ppm"] - 1000.0) / 900.0
    # Temperature deviation from a comfortable ~21C.
    score += abs(row["temp_c"] - 21.0) * 0.12
    # Low pressure.
    score += max(0.0, 95.0 - row["pressure_kpa"]) * 0.16
    # Depleting water reserves.
    score += max(0.0, 40.0 - row["water_reserve_pct"]) * 0.09
    # Insufficient power output.
    score += max(0.0, 20.0 - row["power_output_kw"]) * 0.22
    # Dust storms strain the whole habitat.
    score += row["dust_storm_index"] * 0.45
    return score


def _label(score: float) -> str:
    if score < 2.5:
        return "safe"
    if score < 6.0:
        return "warning"
    return "critical"


def generate_dataset(n_samples: int = 6000, seed: int = RANDOM_SEED) -> pd.DataFrame:
    """Generate a labelled DataFrame of synthetic habitat sensor readings."""
    rng = np.random.default_rng(seed)

    data = {
        "oxygen_pct": rng.normal(20.5, 3.0, n_samples).clip(5, 30),
        "co2_ppm": rng.gamma(2.0, 600.0, n_samples).clip(300, 20000),
        "temp_c": rng.normal(21.0, 8.0, n_samples).clip(-20, 45),
        "pressure_kpa": rng.normal(98.0, 9.0, n_samples).clip(40, 110),
        "water_reserve_pct": rng.uniform(0, 100, n_samples),
        "power_output_kw": rng.normal(28.0, 9.0, n_samples).clip(0, 50),
        "dust_storm_index": rng.uniform(0, 10, n_samples),
    }
    df = pd.DataFrame(data)

    scores = df.apply(lambda r: _risk_score(r), axis=1)
    # Add mild label noise so the boundary is not perfectly separable.
    noisy = scores + rng.normal(0.0, 0.4, n_samples)
    df["risk"] = [_label(s) for s in noisy]

    # Guarantee the categorical dtype covers every class in a stable order.
    df["risk"] = pd.Categorical(df["risk"], categories=CLASS_LABELS, ordered=True)
    return df[FEATURE_NAMES + ["risk"]]
