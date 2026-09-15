# Martian City Hackathon — ML

A small, self-contained machine-learning service that classifies the operational
**risk of a Martian habitat's life-support system** (`safe` / `warning` /
`critical`) from live sensor readings. It ships with synthetic data generation, a
scikit-learn training pipeline, a FastAPI backend, and a single-page UI — the
whole thing runs offline with no external datasets or services.

## Project layout

```
src/martian/
  config.py    # feature schema, class labels, artifact paths
  data.py      # synthetic, rule-based labelled dataset
  train.py     # trains a RandomForest pipeline -> models/risk_classifier.joblib
  model.py     # loads the artifact and runs predictions
  app.py       # FastAPI service (UI + JSON API)
  static/      # single-page front end
tests/         # pytest suite covering data, model, and API
```

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Train the model (writes models/risk_classifier.joblib)
python -m src.martian.train

# Run the API + UI on http://localhost:8000
uvicorn src.martian.app:app --host 0.0.0.0 --port 8000
```

Open http://localhost:8000, enter sensor readings, and click **Assess risk**.

## API

| Method | Path           | Description                              |
| ------ | -------------- | ---------------------------------------- |
| GET    | `/`            | Single-page UI                           |
| GET    | `/api/health`  | Liveness + whether the model is loaded   |
| GET    | `/api/schema`  | Feature schema used to render the form   |
| POST   | `/api/predict` | Risk prediction for a set of readings    |

Example:

```bash
curl -s -X POST http://localhost:8000/api/predict \
  -H 'Content-Type: application/json' \
  -d '{"oxygen_pct":12,"co2_ppm":9000,"temp_c":-10,"pressure_kpa":60,
       "water_reserve_pct":8,"power_output_kw":5,"dust_storm_index":9}'
```

## Tests

```bash
source .venv/bin/activate
python -m pytest -q
```

## Cloud Agent environment

`.cursor/environment.json` provisions the environment:

- **install** — creates a virtualenv, installs `requirements.txt`, and trains the
  model so the artifact is ready before the agent starts.
- **terminals.api** — serves the FastAPI app on port `8000`.
