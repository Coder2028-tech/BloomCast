# BloomCast NJ

BloomCast NJ is a multimodal machine learning system that forecasts harmful algal bloom (HAB) risk in New Jersey lakes 7 days in advance, delivered through a public-facing web app. The project combines tabular water quality data, satellite imagery, and atmospheric data to predict bloom risk, and is being developed for both the **Congressional App Challenge (CAC)** and **TNJSF/ISEF** science fair competitions.

## Target Lakes

| Lake | Role |
|---|---|
| **Lake Hopatcong** | Primary bloom site (training data) |
| **Budd Lake** | Secondary bloom site |
| **Round Valley Reservoir** | Low-bloom control / held-out spatial generalization test |

## Project Structure

```
BloomCast/
├── bloomcast-ml/       # Data pipelines, feature engineering, model training
│   ├── scripts/
│   ├── data/
│   ├── models/
│   └── results/
├── bloomcast-api/      # FastAPI backend serving model predictions
└── bloomcast-app/      # React frontend (zip code -> risk forecast)
```

## Current Approach

- **Baseline model:** Random Forest predicting next-sample chlorophyll-a from lagged chlorophyll-a, water temperature, and phosphorus. Trained on Lake Hopatcong, evaluated on Round Valley Reservoir as a held-out spatial generalization test.
- **Planned multimodal model:** ConvLSTM architecture combining satellite imagery (Sentinel-2, via NDCI) and atmospheric data (NLDAS-2) with tabular water quality records.
- **Field sampling:** Three rounds of in-person sampling (mid-July, mid-August, mid-September) at all three lakes to supplement gaps in public monitoring data.

### Known Data Limitations

- Public water quality records (EPA Water Quality Portal) are sparse for these lakes, especially for Budd Lake, which currently has too few temporally-aligned measurements to build complete feature rows.
- Nitrogen data returned zero usable rows across all three lakes across all name variants queried via EPA WQP.
- These gaps motivate the multimodal approach (imagery + atmospheric data) rather than relying on tabular water quality records alone, and are part of why field sampling is a core part of the project rather than a supplementary add-on.

## Contributors

- **Riya Vazirani Laheja** — ML baseline/modeling, React/FastAPI web application, field sampling
- **[Partner name]** — Data engineering: NLDAS-2 atmospheric pipeline, Sentinel-2 satellite imagery pipeline

## Dependencies

**ML pipeline** (`bloomcast-ml`) — conda environment `bloomcast`:
- Python, pandas, scikit-learn, requests
- See `environment.yml` / `requirements.txt` for the full list

**Backend** (`bloomcast-api`):
- FastAPI, uvicorn, joblib, scikit-learn

**Frontend** (`bloomcast-app`):
- React, Vite, Tailwind CSS v4

## Data Sources

- [EPA Water Quality Portal](https://www.waterqualitydata.us/) — chlorophyll-a, temperature, nutrient measurements
- [NJ DEP HAB Dashboard](https://njhabs.org/) — official bloom status/tier labels
- NASA Earthdata / Sentinel Hub — satellite imagery (Sentinel-2)
- Field sampling — in-person chlorophyll-a, temperature, and phosphorus readings at all three lakes

## Running Locally

**ML pipeline:**
```bash
cd bloomcast-ml
conda activate bloomcast
python scripts/fetch_wqp_data.py       # pull latest water quality data
python scripts/train_baseline.py       # train + evaluate the RF baseline
```

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

## License

TBD