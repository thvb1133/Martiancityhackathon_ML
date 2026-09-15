"""Load the trained pipeline and expose a typed prediction helper."""

from __future__ import annotations

from functools import lru_cache

import joblib
import pandas as pd

from .config import FEATURE_NAMES, MODEL_PATH


class ModelNotTrainedError(RuntimeError):
    """Raised when a prediction is requested before the model is trained."""


@lru_cache(maxsize=1)
def load_model() -> dict:
    if not MODEL_PATH.exists():
        raise ModelNotTrainedError(
            f"Model artifact not found at {MODEL_PATH}. "
            "Run `python -m src.martian.train` first."
        )
    return joblib.load(MODEL_PATH)


def predict(features: dict) -> dict:
    """Return the predicted risk label and per-class probabilities.

    ``features`` must contain every key in :data:`FEATURE_NAMES`.
    """
    bundle = load_model()
    pipeline = bundle["pipeline"]
    classes = list(pipeline.named_steps["clf"].classes_)

    row = pd.DataFrame([[float(features[name]) for name in FEATURE_NAMES]], columns=FEATURE_NAMES)
    label = str(pipeline.predict(row)[0])
    proba = pipeline.predict_proba(row)[0]
    probabilities = {cls: round(float(p), 4) for cls, p in zip(classes, proba)}

    return {
        "risk": label,
        "confidence": probabilities[label],
        "probabilities": probabilities,
    }
