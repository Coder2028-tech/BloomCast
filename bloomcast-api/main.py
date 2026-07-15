import json
from pathlib import Path

import joblib
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="BloomCast NJ API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_headers=["*"],
)

MODEL_PATH = Path(__file__).parent / "model" / "rf_baseline.pkl"
LAKE_STATE_PATH = Path(__file__).parent / "model" / "latest_lake_state.json"

rf_model = joblib.load(MODEL_PATH)
with open(LAKE_STATE_PATH) as f:
    LAKE_STATE = json.load(f)

FEATURE_ORDER = ["chl_a_lag1", "chl_a_lag2", "temp_lag1", "temp_lag2", "phosphorus"]


ZIP_TO_LAKE = {
    "07849": "Lake Hopatcong",
    "07801": "Lake Hopatcong",
    "07836": "Lake Hopatcong",
    "07828": "Budd Lake",
    "08833": "Round Valley Reservoir",
    "08822": "Round Valley Reservoir",
}


def classify_risk(chl_a_prediction: float) -> str:
    """Very rough chlorophyll-a -> risk-category thresholds.

    THESE NUMBERS ARE PLACEHOLDERS. NJ DEP's actual HAB guidance uses
    cyanobacteria CELL DENSITY (cells/mL), not chlorophyll-a directly - the
    known scientific tension flagged in the project notes. Before using
    this for anything beyond an MVP demo, these thresholds need real
    justification (e.g. from NJ DEP HAB guidance documents or published
    chl-a/cyanobacteria correlation studies), and ideally should be
    calibrated per-lake rather than as one global cutoff.
    """
    if chl_a_prediction < 10:
        return "Safe"
    elif chl_a_prediction < 20:
        return "Watch"
    elif chl_a_prediction < 40:
        return "Warning"
    else:
        return "Danger"


@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": rf_model is not None}


@app.get("/forecast/{zip_code}")
def forecast(zip_code: str):
    lake = ZIP_TO_LAKE.get(zip_code)

    if lake is None:
        return {
            "zip_code": zip_code,
            "error": "This zip code isn't mapped to one of our monitored lakes yet.",
        }

    lake_features = LAKE_STATE.get(lake)
    if lake_features is None:
        return {
            "zip_code": zip_code,
            "lake_name": lake,
            "error": f"Not enough recent data available for {lake} to make a forecast yet.",
        }

    X = [[lake_features[col] for col in FEATURE_ORDER]]
    prediction = float(rf_model.predict(X)[0])
    risk_level = classify_risk(prediction)

    return {
        "zip_code": zip_code,
        "lake_name": lake,
        "risk_level": risk_level,
        "predicted_chl_a": round(prediction, 2),
        "data_as_of": lake_features["as_of_date"],
        "valid_for_days": 7,
    }