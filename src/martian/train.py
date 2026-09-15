"""Train the habitat risk classifier and persist it to ``models/``.

Run with: ``python -m src.martian.train``

The script is deterministic (fixed seed) and idempotent: re-running it simply
regenerates the same artifact, which makes it safe to call from the environment
``install`` phase.
"""

from __future__ import annotations

import time

import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .config import CLASS_LABELS, FEATURE_NAMES, MODEL_PATH, MODELS_DIR, RANDOM_SEED
from .data import generate_dataset


def build_pipeline() -> Pipeline:
    return Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            (
                "clf",
                RandomForestClassifier(
                    n_estimators=200,
                    max_depth=12,
                    random_state=RANDOM_SEED,
                    n_jobs=-1,
                ),
            ),
        ]
    )


def train() -> dict:
    df = generate_dataset()
    X = df[FEATURE_NAMES]
    y = df["risk"].astype(str)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_SEED, stratify=y
    )

    pipeline = build_pipeline()
    start = time.perf_counter()
    pipeline.fit(X_train, y_train)
    elapsed = time.perf_counter() - start

    preds = pipeline.predict(X_test)
    accuracy = accuracy_score(y_test, preds)

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {"pipeline": pipeline, "features": FEATURE_NAMES, "classes": CLASS_LABELS},
        MODEL_PATH,
    )

    print(f"Trained on {len(X_train)} samples in {elapsed:.2f}s")
    print(f"Holdout accuracy: {accuracy:.3f}")
    print(classification_report(y_test, preds, labels=CLASS_LABELS, zero_division=0))
    print(f"Saved model -> {MODEL_PATH}")

    return {"accuracy": accuracy, "model_path": str(MODEL_PATH)}


if __name__ == "__main__":
    train()
