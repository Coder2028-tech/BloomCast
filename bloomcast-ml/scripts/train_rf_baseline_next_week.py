"""Train the corrected next-week RF baseline before adding remote-sensing inputs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

FEATURES = ["past_chl_a", "past_chl_a_previous", "temp", "phosphorus"]
TARGET = "target_chl_a_next_week"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data/training_lake_date.csv")
    parser.add_argument("--held-out-lake", default="Lake Hopatcong")
    parser.add_argument("--model-out", default="models/rf_next_week_baseline.pkl")
    parser.add_argument("--results-out", default="results/rf_next_week_baseline.json")
    args = parser.parse_args()
    frame = pd.read_csv(args.data).dropna(subset=FEATURES + [TARGET])
    train, test = frame[frame.lake != args.held_out_lake], frame[frame.lake == args.held_out_lake]
    if train.empty or test.empty:
        raise ValueError(f"Insufficient train/test rows for held-out lake {args.held_out_lake!r}")
    model = RandomForestRegressor(n_estimators=500, max_depth=8, min_samples_leaf=2,
                                  random_state=42, n_jobs=-1).fit(train[FEATURES], train[TARGET])
    predicted = model.predict(test[FEATURES])
    results = {
        "model": "RandomForest_next_week_baseline", "held_out_lake": args.held_out_lake,
        "features": FEATURES, "n_train": int(len(train)), "n_test": int(len(test)),
        "rmse": float(np.sqrt(mean_squared_error(test[TARGET], predicted))),
        "mae": float(mean_absolute_error(test[TARGET], predicted)),
        "r2": float(r2_score(test[TARGET], predicted)) if len(test) >= 2 else None,
        "feature_importance": dict(zip(FEATURES, model.feature_importances_.tolist())),
    }
    model_out = Path(args.model_out); model_out.parent.mkdir(parents=True, exist_ok=True)
    results_out = Path(args.results_out); results_out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_out)
    results_out.write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
