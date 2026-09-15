"""FastAPI service exposing the Martian habitat risk classifier.

Endpoints:
- ``GET  /``            -> the single-page UI
- ``GET  /api/health``  -> liveness + whether the model is loaded
- ``GET  /api/schema``  -> feature schema used to render the form
- ``POST /api/predict`` -> risk prediction for a set of sensor readings
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .config import CLASS_LABELS, FEATURES, FEATURE_NAMES
from .model import ModelNotTrainedError, predict

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Martian Habitat Risk Classifier", version="0.1.0")


class SensorReading(BaseModel):
    oxygen_pct: float = Field(..., description="Oxygen concentration (%)")
    co2_ppm: float = Field(..., description="CO2 concentration (ppm)")
    temp_c: float = Field(..., description="Cabin temperature (C)")
    pressure_kpa: float = Field(..., description="Habitat pressure (kPa)")
    water_reserve_pct: float = Field(..., description="Water reserve (%)")
    power_output_kw: float = Field(..., description="Power output (kW)")
    dust_storm_index: float = Field(..., ge=0, le=10, description="Dust storm severity 0-10")


class Prediction(BaseModel):
    risk: str
    confidence: float
    probabilities: dict[str, float]


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict:
    try:
        from .model import load_model

        load_model()
        model_loaded = True
    except ModelNotTrainedError:
        model_loaded = False
    return {"status": "ok", "model_loaded": model_loaded}


@app.get("/api/schema")
def schema() -> dict:
    return {"features": FEATURES, "classes": CLASS_LABELS}


@app.post("/api/predict", response_model=Prediction)
def predict_risk(reading: SensorReading) -> Prediction:
    try:
        result = predict({name: getattr(reading, name) for name in FEATURE_NAMES})
    except ModelNotTrainedError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return Prediction(**result)
