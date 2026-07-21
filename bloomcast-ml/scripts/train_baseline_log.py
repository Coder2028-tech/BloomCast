import json

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, r2_score

DATA_PATH = "data/tabular_features.csv"
MODEL_OUT = "models/rf_baseline_log.pkl"
RESULTS_OUT = "results/rf_baseline_log_results.json"
HELD_OUT_LAKE = "Round Valley Reservoir"
N_LAGS = 2

FEATURE_COLS = [
    "chl_a_lag1", "chl_a_lag2",
    "temp_lag1", "temp_lag2",
    "phosphorus",
]

LOG_COLS = ["chl_a", "phosphorus"]


def add_lag_features(df: pd.DataFrame, n_lags: int = N_LAGS) -> pd.DataFrame:
    df = df.copy()
    for lag in range(1, n_lags + 1):
        df[f"chl_a_lag{lag}"] = df.groupby("lake")["chl_a"].shift(lag)
        df[f"temp_lag{lag}"] = df.groupby("lake")["temp"].shift(lag)
    df["target_chl_a_next"] = df.groupby("lake")["chl_a"].shift(-1)
    return df


def main():
    df = pd.read_csv(DATA_PATH, parse_dates=["date"])
    df = df.sort_values(["lake", "date"])

    for col in LOG_COLS:
        df[col] = np.log1p(df[col])

    df = add_lag_features(df)
    df = df.dropna()

    print("Rows per lake after cleaning:")
    print(df.groupby("lake").size())
    print()

    train_df = df[df["lake"] != HELD_OUT_LAKE]
    test_df = df[df["lake"] == HELD_OUT_LAKE]

    if test_df.empty:
        raise ValueError(f"No rows for held-out lake '{HELD_OUT_LAKE}'.")

    X_train, y_train = train_df[FEATURE_COLS], train_df["target_chl_a_next"]
    X_test, y_test_log = test_df[FEATURE_COLS], test_df["target_chl_a_next"]

    rf = RandomForestRegressor(n_estimators=300, max_depth=8, random_state=42)
    rf.fit(X_train, y_train)
    joblib.dump(rf, MODEL_OUT)

    preds_log = rf.predict(X_test)
    preds = np.expm1(preds_log)
    y_test = np.expm1(y_test_log)

    rmse = float(np.sqrt(mean_squared_error(y_test, preds)))
    r2 = float(r2_score(y_test, preds))

    print("Held-out lake predictions (real units, actual vs predicted):")
    for actual, predicted in zip(y_test, preds):
        print(f"  actual {actual:8.2f}   predicted {predicted:8.2f}")

    print(f"\nRMSE: {rmse:.3f} | R2: {r2:.3f}")

    results = {
        "model": "RandomForest_log",
        "target_transform": "log1p",
        "held_out_lake": HELD_OUT_LAKE,
        "train_lakes": sorted(train_df["lake"].unique().tolist()),
        "rmse": rmse,
        "r2": r2,
        "n_train": int(len(train_df)),
        "n_test": int(len(test_df)),
        "feature_importance": dict(
            zip(FEATURE_COLS, rf.feature_importances_.tolist())
        ),
    }
    with open(RESULTS_OUT, "w") as f:
        json.dump(results, f, indent=2)

    print(f"Saved model   -> {MODEL_OUT}")
    print(f"Saved results -> {RESULTS_OUT}")


if __name__ == "__main__":
    main()