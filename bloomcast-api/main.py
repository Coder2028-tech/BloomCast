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

rf_model = joblib.load(MODEL_PATH)
with open(LAKE_STATE_PATH) as f:
    LAKE_STATE = json.load(f)

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