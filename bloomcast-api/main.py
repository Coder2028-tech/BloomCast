import csv
import json
from pathlib import Path

import joblib
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="BloomCast NJ API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

MODEL_PATH = Path(__file__).parent / "model" / "rf_baseline.pkl"
LAKE_STATE_PATH = Path(__file__).parent / "model" / "latest_lake_state.json"
LAKE_TARGETS_PATH = Path(__file__).parent / "model" / "lake_targets.csv"

rf_model = joblib.load(MODEL_PATH)
with open(LAKE_STATE_PATH) as f:
    LAKE_STATE = json.load(f)

LAKE_COORDS = {}
with open(LAKE_TARGETS_PATH, newline="") as f:
    for row in csv.DictReader(f):
        lat = row.get("latitude", "").strip()
        lon = row.get("longitude", "").strip()
        if lat and lon:
            LAKE_COORDS[row["name"]] = {"lat": float(lat), "long": float(lon)}

FEATURE_ORDER = ["chl_a_lag1", "chl_a_lag2", "temp_lag1", "temp_lag2", "phosphorus"]


ZIP_TO_LAKE = {
    "07849": "Lake Hopatcong",
    "07843": "Lake Hopatcong",
    "07850": "Lake Hopatcong",
    "07874": "Lake Hopatcong",
    "07857": "Lake Hopatcong",
    "07852": "Lake Hopatcong",
    "07828": "Budd Lake",
    "07836": "Budd Lake",
    "08833": "Round Valley Reservoir",
    "08801": "Round Valley Reservoir",
    "08809": "Round Valley Reservoir",
}


def classify_risk(chl_a_prediction: float) -> str:
    if chl_a_prediction < 10:
        return "Safe"
    elif chl_a_prediction < 20:
        return "Watch"
    elif chl_a_prediction < 40:
        return "Warning"
    else:
        return "Danger"


def predict_for_lake(lake: str):
    """Return (risk_level, predicted_chl_a) for a lake, or (None, None) if
    there isn't enough data in LAKE_STATE to make a prediction."""
    lake_features = LAKE_STATE.get(lake)
    if lake_features is None:
        return None, None
    X = [[lake_features[col] for col in FEATURE_ORDER]]
    prediction = float(rf_model.predict(X)[0])
    return classify_risk(prediction), round(prediction, 2)


@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": rf_model is not None}


@app.get("/lakes")
def lakes():
    """Return every lake that has coordinates, with its current risk level.
    Lakes without enough data to forecast are flagged has_data=False so the
    frontend can render them gray ('insufficient data') instead of implying
    a confident forecast."""
    result = []
    for lake, coords in LAKE_COORDS.items():
        risk_level, predicted = predict_for_lake(lake)
        has_data = risk_level is not None
        lake_features = LAKE_STATE.get(lake, {})
        result.append({
            "lake_name": lake,
            "lat": coords["lat"],
            "long": coords["long"],
            "has_data": has_data,
            "risk_level": risk_level,          
            "predicted_chl_a": predicted,      
            "data_as_of": lake_features.get("as_of_date"),
        })
    return {"lakes": result}


@app.get("/forecast/{zip_code}")
def forecast(zip_code: str):
    lake = ZIP_TO_LAKE.get(zip_code)

    if lake is None:
        return {
            "zip_code": zip_code,
            "error": "No local lakes in your area covered as of now.",
        }

    risk_level, predicted = predict_for_lake(lake)
    if risk_level is None:
        return {
            "zip_code": zip_code,
            "lake_name": lake,
            "error": f"Not enough recent data available for {lake} to make a forecast yet.",
        }

    lake_features = LAKE_STATE.get(lake, {})
    return {
        "zip_code": zip_code,
        "lake_name": lake,
        "risk_level": risk_level,
        "predicted_chl_a": predicted,
        "data_as_of": lake_features.get("as_of_date"),
        "valid_for_days": 7,
    }