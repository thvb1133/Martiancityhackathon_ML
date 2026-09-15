"""End-to-end tests for the data, training, model, and API layers."""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.martian.app import app
from src.martian.config import CLASS_LABELS, FEATURE_NAMES
from src.martian.data import generate_dataset
from src.martian.model import load_model, predict

client = TestClient(app)

SAFE_READING = {
    "oxygen_pct": 21.0,
    "co2_ppm": 700.0,
    "temp_c": 21.0,
    "pressure_kpa": 101.0,
    "water_reserve_pct": 85.0,
    "power_output_kw": 32.0,
    "dust_storm_index": 1.0,
}

CRITICAL_READING = {
    "oxygen_pct": 12.0,
    "co2_ppm": 9000.0,
    "temp_c": -10.0,
    "pressure_kpa": 60.0,
    "water_reserve_pct": 8.0,
    "power_output_kw": 5.0,
    "dust_storm_index": 9.0,
}


def test_dataset_shape_and_labels():
    df = generate_dataset(n_samples=500)
    assert list(df.columns) == FEATURE_NAMES + ["risk"]
    assert len(df) == 500
    assert set(df["risk"].astype(str).unique()).issubset(set(CLASS_LABELS))


def test_model_artifact_loads():
    bundle = load_model()
    assert bundle["features"] == FEATURE_NAMES


def test_predict_safe_vs_critical():
    safe = predict(SAFE_READING)
    critical = predict(CRITICAL_READING)
    assert safe["risk"] == "safe"
    assert critical["risk"] == "critical"
    assert abs(sum(safe["probabilities"].values()) - 1.0) < 1e-6


def test_health_endpoint():
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["model_loaded"] is True


def test_predict_endpoint():
    res = client.post("/api/predict", json=CRITICAL_READING)
    assert res.status_code == 200
    body = res.json()
    assert body["risk"] in CLASS_LABELS
    assert body["risk"] == "critical"
