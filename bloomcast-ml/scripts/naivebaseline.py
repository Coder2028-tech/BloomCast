
import numpy as np
import pandas as pd

CSV_PATH   = "data/tabular_features.csv"   
LAKE_COL   = "lake"                   
TARGET_COL = "chl_a"                 
TIER_EDGES = [10, 20, 40]


def to_tier(vals):
    return np.digitize(np.asarray(vals, dtype=float), TIER_EDGES)


def rmse(y_true, y_pred):
    return float(np.sqrt(np.mean((np.asarray(y_true) - np.asarray(y_pred)) ** 2)))


def tier_acc(y_true, y_pred):
    return float(np.mean(to_tier(y_true) == to_tier(y_pred)))


def main():
    df = pd.read_csv(CSV_PATH).dropna(subset=[TARGET_COL, LAKE_COL])
    y = df[TARGET_COL].to_numpy(dtype=float)
    print(f"Loaded {len(df)} rows across {df[LAKE_COL].nunique()} lakes\n")

    global_med = np.median(y)
    g_pred = np.full_like(y, global_med)
    print("Global-median baseline")
    print(f"  predict {global_med:.2f} ug/L for everything")
    print(f"  RMSE          = {rmse(y, g_pred):.3f} ug/L")
    print(f"  tier accuracy = {tier_acc(y, g_pred):.3f}\n")

    lake_med = df.groupby(LAKE_COL)[TARGET_COL].transform("median").to_numpy()
    print("Per-lake-median baseline")
    print("  predict each lake's own median")
    print(f"  RMSE          = {rmse(y, lake_med):.3f} ug/L")
    print(f"  tier accuracy = {tier_acc(y, lake_med):.3f}\n")

    print("Read this as: your model only earns its keep if it beats the")
    print("per-lake-median row above. That's the honest floor for a forecaster.")


if __name__ == "__main__":
    main()