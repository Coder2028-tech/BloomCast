import numpy as np
import pandas as pd
 
CSV_PATH   = "data/tabular_features.csv"
LAKE_COL   = "lake"
TARGET_COL = "target_chl_a_next"     
PERSIST_COL = "chl_a_lag1"           
N_LAGS     = 2
TIER_EDGES = [10, 20, 40]
TIER_NAMES = ["Safe", "Watch", "Warning", "Danger"]

def add_lag_features(df, n_lags=N_LAGS):
    df = df.copy()
    for lag in range(1, n_lags + 1):
        df[f"chl_a_lag{lag}"] = df.groupby("lake")["chl_a"].shift(lag)
        df[f"temp_lag{lag}"] = df.groupby("lake")["temp"].shift(lag)
    df["target_chl_a_next"] = df.groupby("lake")["chl_a"].shift(-1)
    return df
 
def to_tier(vals):
    return np.digitize(np.asarray(vals, dtype=float), TIER_EDGES)
 
def main():
    df = pd.read_csv(CSV_PATH, parse_dates=["date"]).sort_values(["lake", "date"])
    df = add_lag_features(df)
    df = df.dropna(subset=[PERSIST_COL, TARGET_COL]).reset_index(drop=True)
    y_true = df[TARGET_COL].to_numpy(dtype=float)
    y_pred = df[PERSIST_COL].to_numpy(dtype=float)   
    rmse = np.sqrt(np.mean((y_true - y_pred) ** 2))
    tt, tp = to_tier(y_true), to_tier(y_pred)
    tier_acc = np.mean(tt == tp)
    print(f"  rows: {len(df)}")
    print(f"  RMSE          = {rmse:.3f} ug/L")
    print(f"  tier accuracy = {tier_acc:.3f}")
    k = 4
    cm = np.zeros((k, k), dtype=int)
    for t, p in zip(tt, tp):
        cm[t, p] += 1
    print("\n  confusion (rows=true, cols=pred)")
    print("            " + "".join(f"{n:>9}" for n in TIER_NAMES))
    for i, name in enumerate(TIER_NAMES):
        print(f"    {name:<9}" + "".join(f"{cm[i, j]:>9}" for j in range(4)))
    danger_true = cm[3].sum()
    if danger_true:
        print(f"  Danger recall: {cm[3,3]}/{danger_true} = {cm[3,3]/danger_true:.2f}")
    
    print(f"RMSE {rmse:.2f}, tier_acc {tier_acc:.3f}, rows {len(df)}")

if __name__ == "__main__":
    main()