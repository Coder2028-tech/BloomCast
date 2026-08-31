import csv
import json
import math
from pathlib import Path
import os
import joblib
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from db import engine
from sqlalchemy import text
from fastapi import Header, HTTPException, Depends
from pydantic import BaseModel
from db import SessionLocal
from models import User, Post
from auth import hash_password, verify_password, create_token, get_user_id_from_token

app = FastAPI(title="BloomCast NJ API")
from models import create_tables


def require_user(authorization: str | None = Header(default=None)) -> int:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not logged in")
    token = authorization.split(" ", 1)[1]
    user_id = get_user_id_from_token(token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user_id

class NewPost(BaseModel):
    lake_name: str
    body: str

create_tables()
print("Tables were created")

@app.post("/posts")
def create_post(post: NewPost, user_id: int = Depends(require_user)):
    """Create a post. Requires login. Starts unapproved (moderation gate)."""
    lake = post.lake_name.strip()
    body = post.body.strip()
    if not lake:
        raise HTTPException(status_code=400, detail="Please enter a lake name")
    if len(lake) > 120:
        raise HTTPException(status_code=400, detail="Lake name too long")
    if not body:
        raise HTTPException(status_code=400, detail="Post can't be empty")
    if len(body) > 1000:
        raise HTTPException(status_code=400, detail="Post too long (max 1000 chars)")
 
    db = SessionLocal()
    try:
        new = Post(user_id=user_id, lake_name=lake, body=body, approved=False)
        db.add(new)
        db.commit()
        db.refresh(new)
        return {"success": True, "id": new.id,
                "message": "Submitted! Your post will appear once reviewed."}
    finally:
        db.close()
 
 
@app.get("/posts")
def list_posts(lake: str | None = None):
    """Public feed: only APPROVED posts. Optionally filter by lake."""
    db = SessionLocal()
    try:
        q = db.query(Post, User).join(User, Post.user_id == User.id).filter(Post.approved == True)
        if lake:
            q = q.filter(Post.lake_name == lake.strip())
        q = q.order_by(Post.created_at.desc())
        results = []
        for post, user in q.all():
            results.append({
                "id": post.id,
                "username": user.username,
                "lake_name": post.lake_name,
                "body": post.body,
                "created_at": post.created_at.isoformat(),
            })
        return {"posts": results}
    finally:
        db.close()
  
def require_admin(x_admin_key: str | None = Header(default=None)):
    if not ADMIN_KEY or x_admin_key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Admin access required")
 
 
@app.get("/posts/pending")
def pending_posts(x_admin_key: str | None = Header(default=None)):
    require_admin(x_admin_key)
    db = SessionLocal()
    try:
        q = (db.query(Post, User).join(User, Post.user_id == User.id)
             .filter(Post.approved == False).order_by(Post.created_at.desc()))
        return {"pending": [
            {"id": p.id, "username": u.username, "lake_name": p.lake_name,
             "body": p.body, "created_at": p.created_at.isoformat()}
            for p, u in q.all()
        ]}
    finally:
        db.close()
 
 
@app.post("/posts/{post_id}/approve")
def approve_post(post_id: int, x_admin_key: str | None = Header(default=None)):
    require_admin(x_admin_key)
    db = SessionLocal()
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")
        post.approved = True
        db.commit()
        return {"success": True, "id": post_id, "approved": True}
    finally:
        db.close()
 
 
@app.delete("/posts/{post_id}")
def delete_post(post_id: int, x_admin_key: str | None = Header(default=None)):
    require_admin(x_admin_key)
    db = SessionLocal()
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")
        db.delete(post)
        db.commit()
        return {"success": True, "deleted": post_id}
    finally:
        db.close()

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

ADMIN_KEY = os.getenv("ADMIN_KEY")

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