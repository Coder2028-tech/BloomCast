import json

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.metrics import mean_squared_error, r2_score

DATA_PATH = "data/tabular_features.csv"
MODEL_OUT = "models/lstm_log.pt"
RESULTS_OUT = "results/lstm_log_results.json"
HELD_OUT_LAKE = "Round Valley Reservoir"

FEATURES = ["chl_a", "temp", "phosphorus"]
LOG_COLS = ["chl_a", "phosphorus"]
SEQ_LEN = 3
HIDDEN_SIZE = 32
MAX_EPOCHS = 1000
LEARNING_RATE = 0.01
PATIENCE = 50           
VAL_FRACTION = 0.2
SEED = 42

torch.manual_seed(SEED)
np.random.seed(SEED)


def build_sequences(df: pd.DataFrame):
    X_list, y_list, lake_list = [], [], []
    for lake, group in df.groupby("lake"):
        g = group.sort_values("date").dropna(subset=FEATURES).reset_index(drop=True)
        for i in range(len(g) - SEQ_LEN):
            target = g.loc[i + SEQ_LEN, "chl_a"]
            if pd.isna(target):
                continue
            window = g.loc[i:i + SEQ_LEN - 1, FEATURES].to_numpy(dtype=np.float32)
            X_list.append(window)
            y_list.append(np.float32(target))
            lake_list.append(lake)
    return np.array(X_list), np.array(y_list), np.array(lake_list)


class LSTMForecaster(nn.Module):
    def __init__(self, n_features: int, hidden_size: int = HIDDEN_SIZE):
        super().__init__()
        self.lstm = nn.LSTM(n_features, hidden_size, batch_first=True)
        self.head = nn.Linear(hidden_size, 1)

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.head(out[:, -1, :]).squeeze(-1)


def main():
    df = pd.read_csv(DATA_PATH, parse_dates=["date"])

    for col in LOG_COLS:
        df[col] = np.log1p(df[col])

    X, y_log, lakes = build_sequences(df)
    print(f"Built {len(X)} sequences of length {SEQ_LEN}\n")

    train_mask = lakes != HELD_OUT_LAKE
    test_mask = lakes == HELD_OUT_LAKE
    if test_mask.sum() == 0:
        raise ValueError(f"No sequences for held-out lake '{HELD_OUT_LAKE}'.")

    X_all_train, y_all_train = X[train_mask], y_log[train_mask]
    X_test, y_test_log = X[test_mask], y_log[test_mask]

    # carve a validation slice out of the training data (shuffled)
    rng = np.random.default_rng(SEED)
    order = rng.permutation(len(X_all_train))
    n_val = max(1, int(len(order) * VAL_FRACTION))
    val_idx, train_idx = order[:n_val], order[n_val:]

    X_train, y_train = X_all_train[train_idx], y_all_train[train_idx]
    X_val, y_val = X_all_train[val_idx], y_all_train[val_idx]

    print(f"Train: {len(X_train)} | Val: {len(X_val)} | Test: {len(X_test)} "
          f"(held out: {HELD_OUT_LAKE})\n")

    mean = X_train.reshape(-1, len(FEATURES)).mean(axis=0)
    std = X_train.reshape(-1, len(FEATURES)).std(axis=0)
    std[std == 0] = 1.0
    norm = lambda a: (a - mean) / std

    y_mean, y_std = y_train.mean(), y_train.std()
    if y_std == 0:
        y_std = 1.0

    Xtr = torch.tensor(norm(X_train))
    ytr = torch.tensor((y_train - y_mean) / y_std)
    Xva = torch.tensor(norm(X_val))
    yva = torch.tensor((y_val - y_mean) / y_std)
    Xte = torch.tensor(norm(X_test))

    model = LSTMForecaster(n_features=len(FEATURES))
    optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)
    loss_fn = nn.MSELoss()

    best_val = float("inf")
    best_state = None
    epochs_since_improve = 0
    stopped_at = MAX_EPOCHS

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
            best_val = val_loss
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
            epochs_since_improve = 0
        else:
            epochs_since_improve += 1

        if epoch % 50 == 0 or epoch == 1:
            print(f"  epoch {epoch:4d}  train {loss.item():.4f}  val {val_loss:.4f}")

        if epochs_since_improve >= PATIENCE:
            stopped_at = epoch
            print(f"\nEarly stopping at epoch {epoch} "
                  f"(no val improvement in {PATIENCE} epochs)")
            break

    if best_state is not None:
        model.load_state_dict(best_state)

    model.eval()
    with torch.no_grad():
        preds_n = model(Xte).numpy()

    preds_log = preds_n * y_std + y_mean
    preds = np.expm1(preds_log)
    y_test = np.expm1(y_test_log)

    rmse = float(np.sqrt(mean_squared_error(y_test, preds)))
    r2 = float(r2_score(y_test, preds)) if len(y_test) > 1 else float("nan")

    print("\nHeld-out lake predictions (real units, actual vs predicted):")
    for actual, predicted in zip(y_test, preds):
        print(f"  actual {actual:8.2f}   predicted {predicted:8.2f}")

    print(f"\nRMSE: {rmse:.3f} | R2: {r2:.3f}")
    print(f"Best validation loss: {best_val:.4f} (stopped at epoch {stopped_at})")

    torch.save(model.state_dict(), MODEL_OUT)

    results = {
        "model": "LSTM_log",
        "target_transform": "log1p",
        "seq_len": SEQ_LEN,
        "hidden_size": HIDDEN_SIZE,
        "epochs_trained": stopped_at,
        "early_stopping_patience": PATIENCE,
        "best_val_loss": float(best_val),
        "features": FEATURES,
        "held_out_lake": HELD_OUT_LAKE,
        "n_train_sequences": int(len(X_train)),
        "n_val_sequences": int(len(X_val)),
        "n_test_sequences": int(len(X_test)),
        "rmse": rmse,
        "r2": r2,
    }
    with open(RESULTS_OUT, "w") as f:
        json.dump(results, f, indent=2)

    print(f"Saved model   -> {MODEL_OUT}")
    print(f"Saved results -> {RESULTS_OUT}")


if __name__ == "__main__":
    main()