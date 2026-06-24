from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="BloomCast NJ API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/forecast/{zip_code}")
def forecast(zip_code: str):
    return {
        "zip_code": zip_code,
        "lake": None,
        "risk": "Safe",
        "valid_for_days": 7,
    }
