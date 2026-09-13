import os

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

CSV_PATH      = "data/tabular_features.csv"
LAKE_COL      = "lake"
TARGET_COL    = "chl_a"                
DROP_COLS     = ["lake", "date", "chla"]
MIN_TEST_ROWS = 5                    
TIER_EDGES    = [10, 20, 40]
RANDOM_STATE  = 42
OUTPUT_DIR = "results"


def to_tier(vals):
    return np.digitize(np.asarray(vals, dtype=float), TIER_EDGES)


def rmse(y_true, y_pred):
    return float(np.sqrt(np.mean((np.asarray(y_true) - np.asarray(y_pred)) ** 2)))


def tier_acc(y_true, y_pred):
    return float(np.mean(to_tier(y_true) == to_tier(y_pred)))


def train_and_predict(train_df, test_df, feat_cols):
    X_tr = train_df[feat_cols].to_numpy(dtype=float)
    X_te = test_df[feat_cols].to_numpy(dtype=float)
    y_tr = np.log1p(train_df[TARGET_COL].to_numpy(dtype=float))

    model = RandomForestRegressor(n_estimators=400, random_state=RANDOM_STATE)
    model.fit(X_tr, y_tr)
    return np.expm1(model.predict(X_te))

pred_rows = []

def main():
    df = pd.read_csv(CSV_PATH).dropna(subset=[TARGET_COL, LAKE_COL])
    feat_cols = [c for c in df.columns if c not in DROP_COLS]
    df = df.dropna(subset=feat_cols).reset_index(drop=True)

    counts = df.groupby(LAKE_COL).size().sort_values(ascending=False)
    print("Usable rows per lake after dropping NaN features:")
    for lake, n in counts.items():
        flag = "" if n >= MIN_TEST_ROWS else "  <-- too sparse, skipped as fold"
        print(f"  {lake:<28} {n:>4}{flag}")
    viable = counts[counts >= MIN_TEST_ROWS].index.tolist()
    print(f"\n{len(viable)} of {len(counts)} lakes are viable test folds "
          f"(>= {MIN_TEST_ROWS} rows)\n")

    rows = []
    for lake in viable:
        test_df  = df[df[LAKE_COL] == lake]
        train_df = df[df[LAKE_COL] != lake]
        preds = train_and_predict(train_df, test_df, feat_cols)
        y_true = test_df[TARGET_COL].to_numpy(dtype=float)
        for yt, yp in zip(y_true, preds):
            pred_rows.append({"model": "rf_baseline", "lake": lake, "y_true": yt, "y_pred": yp})
        r, a = rmse(y_true, preds), tier_acc(y_true, preds)
        rows.append({"lake": lake, "n": len(test_df), "rmse": r, "tier_acc": a})
        print(f"  held out {lake:<24} n={len(test_df):>3}  "
              f"RMSE={r:6.3f}  tier_acc={a:.3f}")

    res = pd.DataFrame(rows)
    print(f"  RMSE      mean +/- std : {res.rmse.mean():.3f} +/- {res.rmse.std():.3f}")
    print(f"  tier acc  mean +/- std : {res.tier_acc.mean():.3f} +/- {res.tier_acc.std():.3f}")
    print(f"  best / worst lake RMSE : {res.rmse.min():.3f} ({res.loc[res.rmse.idxmin(),'lake']})"
          f"  /  {res.rmse.max():.3f} ({res.loc[res.rmse.idxmax(),'lake']})")
    import os
    pd.DataFrame(pred_rows).to_csv("all_predictions.csv", index=False)
    print(f"all_predictions.csv with {len(pred_rows)} rows")
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    res.to_csv(os.path.join(OUTPUT_DIR, "lolo_results.csv"), index=False)

if __name__ == "__main__":
    main()