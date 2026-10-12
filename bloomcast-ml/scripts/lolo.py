import os
import numpy as np, pandas as pd
from sklearn.ensemble import RandomForestRegressor

DATA = "data/wqp_states/state_34.csv"
BASE = ["chl_a_lag1", "chl_a_lag2", "temp_lag1", "temp_lag2", "phosphorus"]
MIN_ROWS, SEED = 5, 42
tier = lambda v: np.digitize(np.asarray(v, float), [10, 20, 40])
rmse = lambda a, b: float(np.sqrt(np.mean((np.asarray(a, float) - np.asarray(b, float)) ** 2)))

def add_lags(df):
    df = df.copy()
    for l in (1, 2):
        df[f"chl_a_lag{l}"] = df.groupby("lake")["chl_a"].shift(l)
        df[f"temp_lag{l}"] = df.groupby("lake")["temp"].shift(l)
    df["y"] = df.groupby("lake")["chl_a"].shift(-1)
    return df

df = pd.read_csv(DATA, parse_dates=["date"]).sort_values(["lake", "date"])
df = add_lags(df).dropna(subset=BASE + ["y", "chl_a"])
counts = df.groupby("lake").size()
folds = counts[counts >= MIN_ROWS].index.to_numpy()

ym, pm, yp = [], [], []
for lake in folds:
    te, tr = df[df.lake == lake], df[df.lake != lake]
    m = RandomForestRegressor(n_estimators=300, max_depth=8, random_state=SEED, n_jobs=-1)
    m.fit(tr[BASE], tr["y"])
    ym.extend(te["y"].tolist())
    pm.extend(m.predict(te[BASE]).tolist())
    yp.extend(te["chl_a"].tolist())

ym, pm, yp = np.array(ym), np.array(pm), np.array(yp)
print(f"model       RMSE={rmse(ym, pm):.3f}  tier={np.mean(tier(ym) == tier(pm)):.3f}")
print(f"persistence RMSE={rmse(ym, yp):.3f}  tier={np.mean(tier(ym) == tier(yp)):.3f}")

os.makedirs("results", exist_ok=True)
pd.DataFrame({"y_true": ym, "y_pred": pm}).to_csv("results/lolo_nj_preds.csv", index=False)
print(f"wrote results/lolo_nj_preds.csv with {len(ym)} rows")