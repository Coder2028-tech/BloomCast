import pandas as pd

DATA_PATH = "data/tabular_features.csv"
FEATURES = ["chl_a", "temp", "phosphorus"]
SEQ_LENGTHS = [2, 3, 4]


def count_sequences(df: pd.DataFrame, seq_len: int) -> tuple[int, dict]:
    total = 0
    per_lake = {}
    for lake, group in df.groupby("lake"):
        g = group.sort_values("date").reset_index(drop=True)
        g = g.dropna(subset=FEATURES).reset_index(drop=True)
        count = 0
        for i in range(len(g) - seq_len):
            target = g.loc[i + seq_len, "chl_a"]
            if pd.notna(target):
                count += 1
        if count > 0:
            per_lake[lake] = count
        total += count
    return total, per_lake


def main():
    df = pd.read_csv(DATA_PATH, parse_dates=["date"])

    print("How many usable LSTM sequences exist, by sequence length:\n")
    for seq_len in SEQ_LENGTHS:
        total, per_lake = count_sequences(df, seq_len)
        print(f"=== sequence length {seq_len} → {total} total sequences "
              f"across {len(per_lake)} lakes ===")
        for lake, count in sorted(per_lake.items(), key=lambda x: -x[1]):
            print(f"    {lake:28s} {count}")
        print()

    print("Interpretation guide:")
    print("  - Deep learning usually wants hundreds+ of sequences to work well.")
    print("  - If totals are in the low dozens, an LSTM likely won't beat the")
    print("    RF baseline - which is itself a valid finding to report.")


if __name__ == "__main__":
    main()