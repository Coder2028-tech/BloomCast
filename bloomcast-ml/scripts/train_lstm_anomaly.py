import json

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import mean_squared_error, r2_score

DATA_PATH = "data/tabular_features.csv"
MODEL_OUT = "models/lstm_anomaly.pt"
RESULTS_OUT = "results/lstm_anomaly_results.json"
HELD_OUT_LAKE = "Round Valley Reservoir"

SEQ_LEN = 3
HIDDEN_SIZE = 32
MAX_EPOCHS = 1000
LEARNING_RATE = 0.01
PATIENCE = 60
VAL_FRACTION = 0.2
SEED = 42


FEATURE_COLS = [
    "chl_a_anom",     
    "temp",
    "phos_anom",      
    "month_cos",
    "days_gap",
]

torch.manual_seed(SEED)
np.random.seed(SEED)


def classify_risk(chl_a: float) -> str:
    if chl_a < 10:
        return "Safe"
    elif chl_a < 20:
        return "Watch"
    elif chl_a < 40:
        return "Warning"
    return "Danger"


def prepare(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    df = df.sort_values(["lake", "date"]).copy()
    df["log_chl"] = np.log1p(df["chl_a"])
    df["log_phos"] = np.log1p(df["phosphorus"])

    baselines = {}
    for lake, g in df.groupby("lake"):
        baselines[lake] = {
            "chl": float(g["log_chl"].median(skipna=True)),
            "phos": float(g["log_phos"].median(skipna=True)),
        }

    df["chl_base"] = df["lake"].map(lambda l: baselines[l]["chl"])
    df["phos_base"] = df["lake"].map(lambda l: baselines[l]["phos"])
    df["chl_a_anom"] = df["log_chl"] - df["chl_base"]
    df["phos_anom"] = df["log_phos"] - df["phos_base"]

    month = df["date"].dt.month
    df["month_sin"] = np.sin(2 * np.pi * month / 12)
    df["month_cos"] = np.cos(2 * np.pi * month / 12)

    df["days_gap"] = df.groupby("lake")["date"].diff().dt.days.fillna(0)
    df["days_gap"] = np.log1p(df["days_gap"])

    return df, baselines


def build_sequences(df: pd.DataFrame):
    X, y, lakes, bases = [], [], [], []
    needed = FEATURE_COLS + ["chl_a_anom", "chl_base"]
    for lake, group in df.groupby("lake"):
        g = group.dropna(subset=needed).reset_index(drop=True)
        for i in range(len(g) - SEQ_LEN):
            target = g.loc[i + SEQ_LEN, "chl_a_anom"]
            if pd.isna(target):
                continue
            X.append(g.loc[i:i + SEQ_LEN - 1, FEATURE_COLS].to_numpy(dtype=np.float32))
            y.append(np.float32(target))
            lakes.append(lake)
            bases.append(np.float32(g.loc[i + SEQ_LEN, "chl_base"]))
    return np.array(X), np.array(y), np.array(lakes), np.array(bases)


class LSTMForecaster(nn.Module):
    def __init__(self, n_features: int, hidden_size: int = HIDDEN_SIZE):
        super().__init__()
        self.lstm = nn.LSTM(n_features, hidden_size, batch_first=True)
        self.head = nn.Linear(hidden_size, 1)

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.head(out[:, -1, :]).squeeze(-1)


def main():
    raw = pd.read_csv(DATA_PATH, parse_dates=["date"])
    df, baselines = prepare(raw)

    X, y_anom, lakes, bases = build_sequences(df)
    print(f"Built {len(X)} sequences of length {SEQ_LEN} "
          f"across {len(set(lakes))} lakes\n")

    train_mask = lakes != HELD_OUT_LAKE
    test_mask = lakes == HELD_OUT_LAKE
    if test_mask.sum() == 0:
        raise ValueError(f"No sequences for held-out lake '{HELD_OUT_LAKE}'.")

    X_all, y_all = X[train_mask], y_anom[train_mask]
    X_test, y_test_anom = X[test_mask], y_anom[test_mask]
    base_test = bases[test_mask]

    rng = np.random.default_rng(SEED)
    order = rng.permutation(len(X_all))
    n_val = max(1, int(len(order) * VAL_FRACTION))
    val_idx, tr_idx = order[:n_val], order[n_val:]
    X_train, y_train = X_all[tr_idx], y_all[tr_idx]
    X_val, y_val = X_all[val_idx], y_all[val_idx]

    print(f"Train: {len(X_train)} | Val: {len(X_val)} | Test: {len(X_test)} "
          f"(held out: {HELD_OUT_LAKE})\n")

    mean = X_train.reshape(-1, len(FEATURE_COLS)).mean(axis=0)
    std = X_train.reshape(-1, len(FEATURE_COLS)).std(axis=0)
    std[std == 0] = 1.0
    norm = lambda a: (a - mean) / std

    Xtr = torch.tensor(norm(X_train))
    ytr = torch.tensor(y_train)
    Xva = torch.tensor(norm(X_val))
    yva = torch.tensor(y_val)
    Xte = torch.tensor(norm(X_test))

    model = LSTMForecaster(n_features=len(FEATURE_COLS))
    optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)
    loss_fn = nn.MSELoss()

    best_val, best_state, since_improve, stopped_at = float("inf"), None, 0, MAX_EPOCHS
    for epoch in range(1, MAX_EPOCHS + 1):
        model.train()
        optimizer.zero_grad()
        loss = loss_fn(model(Xtr), ytr)
        loss.backward()
        optimizer.step()

        model.eval()
        with torch.no_grad():
            val_loss = loss_fn(model(Xva), yva).item()

        if val_loss < best_val - 1e-5:
            best_val, since_improve = val_loss, 0
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
        else:
            since_improve += 1

        if epoch % 100 == 0 or epoch == 1:
            print(f"  epoch {epoch:4d}  train {loss.item():.4f}  val {val_loss:.4f}")

        if since_improve >= PATIENCE:
            stopped_at = epoch
            print(f"\nEarly stopping at epoch {epoch}")
            break

    if best_state is not None:
        model.load_state_dict(best_state)

    model.eval()
    with torch.no_grad():
        pred_anom = model(Xte).numpy()

    preds = np.expm1(pred_anom + base_test)
    y_test = np.expm1(y_test_anom + base_test)

    rmse = float(np.sqrt(mean_squared_error(y_test, preds)))
    r2 = float(r2_score(y_test, preds)) if len(y_test) > 1 else float("nan")

    actual_tiers = [classify_risk(v) for v in y_test]
    pred_tiers = [classify_risk(v) for v in preds]
    correct = sum(a == p for a, p in zip(actual_tiers, pred_tiers))
    tier_acc = correct / len(actual_tiers)

    print("\nHeld-out lake predictions (real ug/L):")
    print(f"{'actual':>10} {'predicted':>10}   {'actual tier':>12} {'pred tier':>10}  ok")
    for a, p, at, pt in zip(y_test, preds, actual_tiers, pred_tiers):
        mark = "yes" if at == pt else "NO"
        print(f"{a:10.2f} {p:10.2f}   {at:>12} {pt:>10}  {mark}")

    print(f"\nRMSE: {rmse:.3f} | R2: {r2:.3f}")
    print(f"Risk-tier accuracy: {correct}/{len(actual_tiers)} = {tier_acc:.0%}")
    print(f"Best val loss: {best_val:.4f} (stopped at epoch {stopped_at})")

    torch.save(model.state_dict(), MODEL_OUT)

    results = {
        "model": "LSTM_per_lake_anomaly",
        "approach": "predict deviation from each lake's own log-median baseline",
        "extra_features": ["month_sin", "month_cos", "days_gap"],
        "seq_len": SEQ_LEN,
        "hidden_size": HIDDEN_SIZE,
        "epochs_trained": stopped_at,
        "best_val_loss": float(best_val),
        "held_out_lake": HELD_OUT_LAKE,
        "n_train_sequences": int(len(X_train)),
        "n_val_sequences": int(len(X_val)),
        "n_test_sequences": int(len(X_test)),
        "rmse": rmse,
        "r2": r2,
        "risk_tier_accuracy": tier_acc,
        "caveat": ("Held-out lake's own historical baseline is used at "
                   "prediction time, so this tests generalization of bloom "
                   "DYNAMICS, not zero-shot prediction for an unmonitored lake."),
    }
    with open(RESULTS_OUT, "w") as f:
        json.dump(results, f, indent=2)

    print(f"Saved model   -> {MODEL_OUT}")
    print(f"Saved results -> {RESULTS_OUT}")


if __name__ == "__main__":
    main()