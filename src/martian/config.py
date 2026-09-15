"""Shared configuration: feature schema, class labels, and artifact paths."""

from __future__ import annotations

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parents[1]
MODELS_DIR = PROJECT_ROOT / "models"
MODEL_PATH = MODELS_DIR / "risk_classifier.joblib"

RANDOM_SEED = 42

# Ordered list of the sensor features the model consumes. Each entry carries a
# human-friendly label, a plausible operating range, and a nominal default used
# to pre-fill the UI form.
FEATURES: list[dict] = [
    {"name": "oxygen_pct", "label": "Oxygen (%)", "min": 5.0, "max": 30.0, "default": 21.0},
    {"name": "co2_ppm", "label": "CO2 (ppm)", "min": 300.0, "max": 20000.0, "default": 800.0},
    {"name": "temp_c", "label": "Cabin temp (C)", "min": -20.0, "max": 45.0, "default": 21.0},
    {"name": "pressure_kpa", "label": "Pressure (kPa)", "min": 40.0, "max": 110.0, "default": 101.0},
    {"name": "water_reserve_pct", "label": "Water reserve (%)", "min": 0.0, "max": 100.0, "default": 75.0},
    {"name": "power_output_kw", "label": "Power output (kW)", "min": 0.0, "max": 50.0, "default": 30.0},
    {"name": "dust_storm_index", "label": "Dust storm index (0-10)", "min": 0.0, "max": 10.0, "default": 2.0},
]

FEATURE_NAMES: list[str] = [f["name"] for f in FEATURES]

# Risk classes, ordered from least to most severe.
CLASS_LABELS: list[str] = ["safe", "warning", "critical"]
