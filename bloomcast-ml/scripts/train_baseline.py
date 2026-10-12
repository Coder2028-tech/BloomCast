import json
import os

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, r2_score

DATA_PATH = "data/wqp_states/state_34.csv"      # New Jersey only (FIPS 34)
MODEL_OUT = "models/rf_baseline.pkl"
RESULTS_OUT = "results/rf_baseline_results.json"
N_LAGS = 2

FEATURE_COLS = [
    "chl_a_lag1", "chl_a_lag2",
    "temp_lag1", "temp_lag2",
    "phosphorus",
]


def add_lag_features(df, n_lags=N_LAGS):
    df = df.copy()
    for lag in range(1, n_lags + 1):
        df[f"chl_a_lag{lag}"] = df.groupby("lake")["chl_a"].shift(lag)
        df[f"temp_lag{lag}"] = df.groupby("lake")["temp"].shift(lag)
    df["target_chl_a_next"] = df.groupby("lake")["chl_a"].shift(-1)
    return df


def main():
    df = pd.read_csv(DATA_PATH, parse_dates=["date"]).sort_values(["lake", "date"])

    df = add_lag_features(df)
    df = df.dropna(subset=FEATURE_COLS + ["target_chl_a_next"])

    print(f"NJ rows after building features: {len(df)}  |  NJ sites: {df['lake'].nunique()}\n")

    # Quick sanity check: hold out the NJ site with the most data
    held_out = df.groupby("lake").size().idxmax()
    print(f"Hold-out site for quick check: {held_out}\n")

    train_df = df[df["lake"] != held_out]
    test_df = df[df["lake"] == held_out]

    X_train, y_train = train_df[FEATURE_COLS], train_df["target_chl_a_next"]
    X_test, y_test = test_df[FEATURE_COLS], test_df["target_chl_a_next"]

    rf = RandomForestRegressor(n_estimators=300, max_depth=8, random_state=42)
    rf.fit(X_train, y_train)

    os.makedirs(os.path.dirname(MODEL_OUT), exist_ok=True)
    joblib.dump(rf, MODEL_OUT)

    preds = rf.predict(X_test)
    rmse = float(np.sqrt(mean_squared_error(y_test, preds)))
    r2 = float(r2_score(y_test, preds))

    results = {
        "model": "RandomForest_baseline_NJ",
        "held_out_site": held_out,
        "rmse": rmse,
        "r2": r2,
        "n_train": int(len(train_df)),
        "n_test": int(len(test_df)),
        "n_sites": int(df["lake"].nunique()),
        "feature_importance": dict(zip(FEATURE_COLS, rf.feature_importances_.tolist())),
    }

    os.makedirs(os.path.dirname(RESULTS_OUT), exist_ok=True)
    with open(RESULTS_OUT, "w") as f:
        json.dump(results, f, indent=2)

    print(f"RMSE: {rmse:.3f} | R2: {r2:.3f}")
    print(f"Saved model  -> {MODEL_OUT}")
    print(f"Saved results -> {RESULTS_OUT}")

    top = max(results["feature_importance"], key=results["feature_importance"].get)
    if top == "chl_a_lag1" and results["feature_importance"][top] > 0.6:
        print(f"\n[NOTE] chl_a_lag1 dominates ({results['feature_importance'][top]:.2f}); "
              "model is close to a persistence baseline. Be upfront about this with judges.")


if __name__ == "__main__":
    main()