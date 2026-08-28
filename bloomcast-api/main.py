import csv
import json
import math
from pathlib import Path
import os
import joblib
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from db import engine
from sqlalchemy import text
from fastapi import Header, HTTPException
from pydantic import BaseModel
from db import SessionLocal
from models import User
from auth import hash_password, verify_password, create_token, get_user_id_from_token

app = FastAPI(title="BloomCast NJ API")
from models import create_tables

create_tables()
print("Tables were created")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class SignupBody(BaseModel):
    username: str
    password: str
 
class LoginBody(BaseModel):
    username: str
    password: str

def require_user(authorization: str | None = Header(default=None)) -> int:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not logged in")
    token = authorization.split(" ", 1)[1]
    user_id = get_user_id_from_token(token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user_id

@app.post("/signup")
def signup(body: SignupBody):
    username = body.username.strip()
    password = body.password
    if not username or not password:
        raise HTTPException(status_code=400, detail="Username and password required")
 
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            raise HTTPException(status_code=400, detail="Username already taken")
        user = User(username=username, password_hash=hash_password(password))
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_token(user.id)
        return {"token": token, "username": user.username}
    finally:
        db.close()

def hash_password(password: str) -> str:
    return pwd_context.hash(password[:72])

def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password[:72], password_hash)

@app.post("/login")
def login(body: LoginBody):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == body.username.strip()).first()
        if not user or not verify_password(body.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid username or password")
        token = create_token(user.id)
        return {"token": token, "username": user.username}
    finally:
        db.close()

ZIP_COORDS_PATH = Path(__file__).parent / "model" / "uszips.csv"

ZIP_COORDS = {}
with open(ZIP_COORDS_PATH, newline="") as f:
    for row in csv.DictReader(f):
        z = row["zip"]
        if z.startswith("07") or z.startswith("08"):
            ZIP_COORDS[z] = (float(row["lat"]), float(row["lng"]))

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
def _band(value, bands):
    for upper, label in bands:
        if upper is None or value < upper:
            return label
    return bands[-1][1]

CHL_BANDS  = [(10, "low"), (20, "elevated"), (40, "high"), (None, "very high")]
TEMP_BANDS = [(15, "cool"), (22, "moderate"), (28, "warm"), (None, "very warm")]
PHOS_BANDS = [(0.02, "low"), (0.05, "moderate"), (None, "high")]

def build_drivers(state: dict) -> list[dict]:
    drivers = []
    chl = state.get("chl_a_lag1")
    if chl is not None:
        drivers.append({"label": "Recent chlorophyll-a", "value": f"{chl:.1f} µg/L", "note": _band(chl, CHL_BANDS)})
    temp = state.get("temp_lag1")
    if temp is not None:
        drivers.append({"label": "Water temperature", "value": f"{temp:.1f}°C", "note": _band(temp, TEMP_BANDS)})
    phos = state.get("phosphorus")
    if phos is not None:
        drivers.append({"label": "Phosphorus", "value": f"{phos:.3f} mg/L", "note": _band(phos, PHOS_BANDS)})
    return drivers

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
        "drivers": build_drivers(lake_features),
    }
def find_lake_by_name(query: str):
    q = query.strip().lower()
    for lake in LAKE_STATE:
        if lake.lower() == q:
            return lake
    matches = [lake for lake in LAKE_STATE if q in lake.lower()]
    if len(matches) == 1:
        return matches[0]
    else:
        return None

def build_forecast(lake, zip_code=None):
    risk_level, predicted = predict_for_lake(lake)
    if risk_level is None:
        resp = {"lake_name": lake,
                "error": f"Not enough recent data available for {lake} to make a forecast yet."}
    else:
        lake_features = LAKE_STATE.get(lake, {})
        resp = {
            "lake_name": lake,
            "risk_level": risk_level,
            "predicted_chl_a": predicted,
            "data_as_of": lake_features.get("as_of_date"),
            "valid_for_days": 7,
            "drivers": build_drivers(lake_features),
        }
    if zip_code is not None:
        resp["zip_code"] = zip_code
    return resp

@app.get("/forecast/{zip_code}")
def forecast(zip_code: str):
    lake, distance = nearest_lake(zip_code)
    if lake is None:
        return {"zip_code": zip_code,
                "error": "No monitored lakes within 15 miles of your area yet."}
    resp = build_forecast(lake, zip_code=zip_code)
    resp["distance_miles"] = distance
    return resp


@app.get("/lake/{lake_name}")
def forecast_by_name(lake_name: str):
    lake = find_lake_by_name(lake_name)
    if lake is None:
        return {"error": f"No lake matching '{lake_name}'. Try the full lake name."}
    return build_forecast(lake)

def _haversine_miles(lat1, lon1, lat2, lon2):
    R = 3958.8 
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))

def nearest_lake(zip_code: str, max_miles: float = 15.0):
    if zip_code not in ZIP_COORDS:
        return None, None
    zlat, zlon = ZIP_COORDS[zip_code]
    best, best_dist = None, None
    for lake, c in LAKE_COORDS.items():
        if lake not in LAKE_STATE:
            continue
        d = _haversine_miles(zlat, zlon, c["lat"], c["long"])
        if best_dist is None or d < best_dist:
            best, best_dist = lake, d
    if best_dist is not None and best_dist <= max_miles:
        return best, round(best_dist, 1)
    return None, None