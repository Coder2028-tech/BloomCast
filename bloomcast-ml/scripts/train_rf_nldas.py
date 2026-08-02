"""Retrain and compare the RF baseline with NLDAS-2 weather features."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


BASE_FEATURES = ["past_chl_a", "past_chl_a_previous", "temp", "phosphorus"]


def _metrics(actual, predicted) -> dict:
    return {
        "rmse": float(np.sqrt(mean_squared_error(actual, predicted))),
        "mae": float(mean_absolute_error(actual, predicted)),
        "r2": float(r2_score(actual, predicted)) if len(actual) >= 2 else None,
    }


def train_comparison(dataset: pd.DataFrame, held_out_lake: str) -> tuple[dict, RandomForestRegressor]:
    nldas_features = sorted(c for c in dataset.columns if c.startswith("nldas_") and c not in {"nldas_hours", "nldas_days"})
    if not nldas_features:
        raise ValueError("No nldas_* feature columns found. Build the dataset with --weather first.")
    base_features = [c for c in BASE_FEATURES if c in dataset.columns]
    features = base_features + nldas_features
    # Same complete-case rows for both models makes the comparison fair.
    usable = dataset.dropna(subset=features + ["target_chl_a_next_week"]).copy()
    if "has_weather" in usable:
        usable = usable[usable["has_weather"].astype(bool)]
    train = usable[usable["lake"] != held_out_lake]
    test = usable[usable["lake"] == held_out_lake]
    if train.empty or test.empty:
        raise ValueError(
            f"Need complete NLDAS rows in both training lakes and held-out lake {held_out_lake!r}; "
            f"found train={len(train)}, test={len(test)}. Download historical NLDAS matching observation dates."
        )
    target = "target_chl_a_next_week"
    params = dict(n_estimators=500, max_depth=8, min_samples_leaf=2, random_state=42, n_jobs=-1)
    baseline = RandomForestRegressor(**params).fit(train[base_features], train[target])
    enhanced = RandomForestRegressor(**params).fit(train[features], train[target])
    baseline_metrics = _metrics(test[target], baseline.predict(test[base_features]))
    enhanced_metrics = _metrics(test[target], enhanced.predict(test[features]))
    results = {
        "comparison_protocol": "same complete-case rows; lake-held-out test; 7-day target",
        "held_out_lake": held_out_lake,
        "n_train": int(len(train)), "n_test": int(len(test)),
        "baseline_features": base_features, "nldas_features": nldas_features,
        "rf_baseline": baseline_metrics, "rf_nldas": enhanced_metrics,
        "delta_rmse": enhanced_metrics["rmse"] - baseline_metrics["rmse"],
        "feature_importance": dict(zip(features, enhanced.feature_importances_.tolist())),
    }
    return results, enhanced


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data/training_lake_date.csv")
    parser.add_argument("--held-out-lake", default="Lake Hopatcong")
    parser.add_argument("--model-out", default="models/rf_nldas.pkl")
    parser.add_argument("--results-out", default="results/rf_nldas_comparison.json")
    args = parser.parse_args()
    results, model = train_comparison(pd.read_csv(args.data, parse_dates=["date"]), args.held_out_lake)
    model_out = Path(args.model_out); model_out.parent.mkdir(parents=True, exist_ok=True)
    results_out = Path(args.results_out); results_out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_out)
    results_out.write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
