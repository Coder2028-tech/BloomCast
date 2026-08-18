# BloomCast NJ

BloomCast NJ is a machine learning system that forecasts harmful algal bloom (HAB) risk in New Jersey lakes, delivered through a public-facing web app. A user enters a NJ zip code or lake name and gets a risk forecast (Safe / Watch / Warning / Danger) for the nearest monitored lake, along with the water-quality drivers behind that forecast.

The project is being developed for the **Congressional App Challenge (CAC)** and the **Terra NJ STEM Fair / ISEF** science fair track.

## What it does

- **Input:** a NJ zip code (mapped to the nearest monitored lake by distance) or a lake name.
- **Output:** a predicted chlorophyll-a level, classified into a risk tier, plus the recent water-quality values driving the prediction and the date that data is from.
- **Risk tiers** (chlorophyll-a, µg/L), based on WHO / NJDEP guidance:
  - Safe < 10 · Watch 10–20 · Warning 20–40 · Danger > 40

## Live app

- Frontend (Vercel): ⚠️ add your Vercel URL
- API (Render): https://bloomcast-oaco.onrender.com

## Model

- **Baseline:** Random Forest predicting next-observation chlorophyll-a from lagged chlorophyll-a, water temperature, and phosphorus.
- **Target framing:** the model predicts the *next available observation*, not a fixed 7-day-ahead forecast — public monitoring is sampled irregularly, so a fixed horizon would misrepresent what the model does.
- **Evaluation:** leave-one-lake-out cross-validation across ⚠️17 lakes to test spatial generalization, plus a persistence baseline for comparison.
- ⚠️ Add your headline numbers here (e.g. LOLO tier accuracy, RMSE vs. persistence) — only ones you can explain.

## Coverage

The app forecasts for the NJ lakes that have usable water-quality records in the EPA Water Quality Portal. Zip codes are matched to the nearest monitored lake within 15 miles; beyond that, the app reports no local coverage rather than pointing users to a distant lake.

## Project structure

```
BloomCast/
├── bloomcast-ml/    # Data pipelines, feature engineering, model training
├── bloomcast-api/   # FastAPI backend serving model predictions
└── bloomcast-app/   # React frontend (zip / lake name -> risk forecast + map)
```

## Tech stack

- **Frontend:** React, Vite, Tailwind CSS v4, React Router, React-Leaflet / Leaflet (lake map). Deployed on Vercel.
- **Backend:** FastAPI, uvicorn, scikit-learn, joblib. Deployed on Render.
- **ML:** Python, pandas, scikit-learn (conda env `bloomcast`).

## Data sources

- [EPA Water Quality Portal](https://www.waterqualitydata.us/) — chlorophyll-a, temperature, nutrient measurements
- [NJ DEP HAB Dashboard](https://njhabs.org/) — official bloom status / tier labels
- Zip code coordinates — [SimpleMaps US Zips](https://simplemaps.com/data/us-zips)
- ⚠️ List any others you actually use (Sentinel-2, NLDAS-2, field sampling) — only if they're part of what's built

## Known data limitations

- Public water-quality records are sparse for some lakes, and sampling is irregular, so some lakes' most recent data is several years old. The app surfaces the data date on each forecast so this is visible rather than hidden.
- ⚠️ Add any other honest caveats (e.g. specific lakes with thin data).

## Running locally

**Backend:**
```bash
cd bloomcast-api
source .venv/bin/activate
uvicorn main:app --reload
```

**Frontend:**
```bash
cd bloomcast-app
npm install
npm run dev
```

**ML pipeline:**
```bash
cd bloomcast-ml
conda activate bloomcast
python scripts/fetch_wqp_data.py
python scripts/train_baseline.py
```

## Contributors

- **Riya Vazirani Laheja** — ML modeling, React/FastAPI web application
- **Madhubala Mohanakrishnan** — Data engineering (data pipelines, satellite/atmospheric ETL)

## License
TBD
