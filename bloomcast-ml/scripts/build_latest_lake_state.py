import json

import pandas as pd

DATA_PATH = "data/tabular_features.csv"
OUT_PATH = "data/latest_lake_state.json"


def main():
    df = pd.read_csv(DATA_PATH, parse_dates=["date"])
    df = df.sort_values(["lake", "date"])

    state = {}
    for lake, group in df.groupby("lake"):
        chl_a_series = group["chl_a"].dropna()
        temp_series = group["temp"].dropna()
        phos_series = group["phosphorus"].dropna()

        if len(chl_a_series) < 2 or len(temp_series) < 2 or len(phos_series) < 1:
            print(f"[skip] {lake}: not enough history to build a feature row "
                  f"(chl_a={len(chl_a_series)}, temp={len(temp_series)}, "
                  f"phosphorus={len(phos_series)})")
            continue

        state[lake] = {
            "chl_a_lag1": float(chl_a_series.iloc[-1]),
            "chl_a_lag2": float(chl_a_series.iloc[-2]),
            "temp_lag1": float(temp_series.iloc[-1]),
            "temp_lag2": float(temp_series.iloc[-2]),
            "phosphorus": float(phos_series.iloc[-1]),
            "as_of_date": str(group["date"].max().date()),
        }
        print(f"[ok] {lake}: latest state as of {state[lake]['as_of_date']}")

    with open(OUT_PATH, "w") as f:
        json.dump(state, f, indent=2)

    print(f"\nSaved lookup for {len(state)} lake(s) -> {OUT_PATH}")
    if len(state) < 3:
        print("NOTE: not all 3 lakes have enough data for a live prediction "
              "yet. Lakes missing from this file will need a fallback "
              "response in the API (e.g. 'insufficient data').")


if __name__ == "__main__":
    main()