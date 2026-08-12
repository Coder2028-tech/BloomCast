import numpy as np
import pandas as pd

PRED_CSV   = "all_predictions.csv"   
TIER_EDGES = [10, 20, 40]
TIER_NAMES = ["Safe", "Watch", "Warning", "Danger"]


def to_tier(vals):
    return np.digitize(np.asarray(vals, dtype=float), TIER_EDGES)


def confusion(y_true_t, y_pred_t, k=4):
    m = np.zeros((k, k), dtype=int)
    for t, p in zip(y_true_t, y_pred_t):
        m[t, p] += 1
    return m


def main():
    df = pd.read_csv(PRED_CSV)
    need = {"model", "y_true", "y_pred"}
    missing = need - set(df.columns)
    if missing:
        raise SystemExit(f"{PRED_CSV} is missing columns: {missing}")

    rows = []
    for model, g in df.groupby("model"):
        yt = g["y_true"].to_numpy(dtype=float)
        yp = g["y_pred"].to_numpy(dtype=float)
        rmse = np.sqrt(np.mean((yt - yp) ** 2))
        tt, tp = to_tier(yt), to_tier(yp)
        acc = np.mean(tt == tp)
        adj = np.mean(np.abs(tt - tp) <= 1)
        rows.append({"model": model, "n": len(g),
                     "rmse_ugL": round(float(rmse), 3),
                     "tier_acc": round(float(acc), 3),
                     "within_1_tier": round(float(adj), 3)})

    table = pd.DataFrame(rows).sort_values("tier_acc", ascending=False)
    print(table.to_string(index=False))
    table.to_csv("model_comparison.csv", index=False)

    for model, g in df.groupby("model"):
        tt = to_tier(g["y_true"].to_numpy(dtype=float))
        tp = to_tier(g["y_pred"].to_numpy(dtype=float))
        cm = confusion(tt, tp)
        print(f"\n{model} — confusion (rows=true, cols=pred)")
        print("            " + "".join(f"{n:>9}" for n in TIER_NAMES))
        for i, name in enumerate(TIER_NAMES):
            print(f"  {name:<9}" + "".join(f"{cm[i, j]:>9}" for j in range(4)))
        danger_true = cm[3].sum()
        if danger_true:
            print(f"  Danger recall: {cm[3,3]}/{danger_true} = {cm[3,3]/danger_true:.2f}")


if __name__ == "__main__":
    main()