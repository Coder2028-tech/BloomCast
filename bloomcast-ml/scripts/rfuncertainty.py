import numpy as np
import pandas as pd
import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

MODEL_PATH = "models/rf_baseline.pkl"
CSV_PATH   = "data/tabular_features.csv"
LAKE_COL   = "lake"
TARGET_COL = "target_chl_a_next"    
N_LAGS     = 2
FEATURES   = ["chl_a_lag1", "chl_a_lag2", "temp_lag1", "temp_lag2", "phosphorus"]
LOG_TARGET = False                
N_SHOW     = 30
OUT_PLOT   = "results/rf_uncertainty.png"
OUT_CSV    = "results/rf_uncertainty.csv"


def add_lag_features(df, n_lags=N_LAGS):
    df = df.copy()
    for lag in range(1, n_lags + 1):
        df[f"chl_a_lag{lag}"] = df.groupby("lake")["chl_a"].shift(lag)
        df[f"temp_lag{lag}"] = df.groupby("lake")["temp"].shift(lag)
    df["target_chl_a_next"] = df.groupby("lake")["chl_a"].shift(-1)
    return df


def main():
    import os
    os.makedirs("results", exist_ok=True)

    model = joblib.load(MODEL_PATH)
    if not hasattr(model, "estimators_"):
        raise SystemExit("Loaded object has no estimators_ — is this a RandomForest?")

    df = pd.read_csv(CSV_PATH, parse_dates=["date"]).sort_values(["lake", "date"])
    df = add_lag_features(df)
    df = df.dropna(subset=FEATURES + [TARGET_COL]).reset_index(drop=True)

    X = df[FEATURES].to_numpy(dtype=float)
    y = df[TARGET_COL].to_numpy(dtype=float)
    print(f"rows after lag-building: {len(df)}")

    tree_preds = np.stack([t.predict(X) for t in model.estimators_])
    if LOG_TARGET:
        tree_preds = np.expm1(tree_preds)

    mean_pred = tree_preds.mean(axis=0)
    std_pred  = tree_preds.std(axis=0)

    out = pd.DataFrame({
        LAKE_COL: df[LAKE_COL],
        "y_true": y,
        "pred":   mean_pred,
        "std":    std_pred,
        "lo":     np.clip(mean_pred - 1.96 * std_pred, 0, None),
        "hi":     mean_pred + 1.96 * std_pred,
    })
    out.to_csv(OUT_CSV, index=False)

    covered = np.mean((y >= out.lo) & (y <= out.hi))
    print(f"mean model spread (std): {std_pred.mean():.2f} ug/L")
    print(f"true value inside +/-1.96*std band: {covered:.1%} of rows")

    sub = out.head(N_SHOW).reset_index(drop=True)
    plt.figure(figsize=(11, 5))
    plt.errorbar(range(len(sub)), sub.pred, yerr=1.96 * sub["std"],
                 fmt="o", capsize=3, label="pred +/- 1.96 std")
    plt.scatter(range(len(sub)), sub.y_true, marker="x", s=60, label="true")
    plt.xlabel(f"row (first {N_SHOW})")
    plt.ylabel("chl-a (ug/L)")
    plt.title("RF prediction vs truth with per-tree spread")
    plt.legend()
    plt.tight_layout()
    plt.savefig(OUT_PLOT, dpi=130)
    print(f"wrote {OUT_CSV} and {OUT_PLOT}")


if __name__ == "__main__":
    main()