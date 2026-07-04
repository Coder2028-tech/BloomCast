import io
import time

import pandas as pd
import requests

BASE_URL = "https://www.waterqualitydata.us/data/Result/search"

LAKES = {
    "Lake Hopatcong": {"lat": 40.9370, "long": -74.6560, "radius": 3},
    "Round Valley Reservoir": {"lat": 40.6176, "long": -74.8263, "radius": 3},
    "Budd Lake": {"lat": 40.8659, "long": -74.7407, "radius": 2},
}

SITE_TYPES = ["Lake, Reservoir, Impoundment"]

CHARACTERISTICS = {
    "chl_a": ["Chlorophyll a"],
    "temp": ["Temperature, water"],
    "phosphorus": [
        "Phosphorus",
        "Total Phosphorus, mixed forms",
        "Phosphate-phosphorus",
        "Orthophosphate",
    ],
}

START_DATE = "01-01-2015"  # mm-dd-yyyy, adjust as needed
END_DATE = "12-31-2025"


def fetch_one_name(lat: float, long: float, radius: float, characteristic_name: str) -> pd.DataFrame:
    params = {
        "lat": lat,
        "long": long,
        "within": radius,
        "siteType": SITE_TYPES,
        "characteristicName": characteristic_name,
        "startDateLo": START_DATE,
        "startDateHi": END_DATE,
        "mimeType": "csv",
        "zip": "no",
    }
    try:
        resp = requests.get(BASE_URL, params=params, timeout=60)
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print(f"    [skip] '{characteristic_name}': {e}")
        return pd.DataFrame()
    except requests.exceptions.RequestException as e:
        print(f"    [skip] '{characteristic_name}': network error - {e}")
        return pd.DataFrame()

    if not resp.text.strip():
        return pd.DataFrame()
    try:
        df = pd.read_csv(io.StringIO(resp.text))
    except pd.errors.EmptyDataError:
        return pd.DataFrame()
    return df


def fetch_characteristic(lat: float, long: float, radius: float, characteristic_names: list[str]) -> pd.DataFrame:
    frames = []
    for name in characteristic_names:
        df = fetch_one_name(lat, long, radius, name)
        if not df.empty:
            frames.append(df)
        time.sleep(0.5)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def build_lake_data(lake: str, lat: float, long: float, radius: float) -> pd.DataFrame:
    print(f"\n--- {lake} (within {radius} mi of {lat}, {long}) ---")
    frames = []
    for feature, char_names in CHARACTERISTICS.items():
        print(f"  querying {feature} ...")
        df = fetch_characteristic(lat, long, radius, char_names)
        if df.empty:
            print(f"    no data")
            continue
        # WQP result columns: ActivityStartDate, ResultMeasureValue, etc.
        keep = df[["ActivityStartDate", "ResultMeasureValue"]].copy()
        keep = keep.rename(columns={
            "ActivityStartDate": "date",
            "ResultMeasureValue": feature,
        })
        keep["date"] = pd.to_datetime(keep["date"], errors="coerce")
        keep[feature] = pd.to_numeric(keep[feature], errors="coerce")
        keep = keep.dropna()
        # collapse same-day duplicates (multiple stations/depths per day)
        keep = keep.groupby("date")[feature].mean().to_frame()
        print(f"    got {len(keep)} rows")
        frames.append(keep)

    if not frames:
        print(f"  WARNING: no data found for {lake} at all.")
        return pd.DataFrame()

    combined = pd.concat(frames, axis=1)
    combined = combined.sort_index()

    for feature in CHARACTERISTICS:
        if feature not in combined.columns:
            combined[feature] = pd.NA
    combined = combined.dropna(how="all", subset=list(CHARACTERISTICS.keys()))

    combined["lake"] = lake
    return combined.reset_index()

def main():
    all_lakes = []
    for lake, coords in LAKES.items():
        lake_df = build_lake_data(lake, coords["lat"], coords["long"], coords["radius"])
        if not lake_df.empty:
            all_lakes.append(lake_df)

    if not all_lakes:
        print("\nNo data retrieved for any lake. Check site IDs and try again.")
        return

    final = pd.concat(all_lakes, ignore_index=True)
    final = final[["lake", "date", "chl_a", "temp", "phosphorus"]]
    final = final.sort_values(["lake", "date"])

    out_path = "data/tabular_features.csv"
    final.to_csv(out_path, index=False)
    print(f"\nSaved {len(final)} rows -> {out_path}")
    print("\nRows per lake:")
    print(final.groupby("lake").size())
    print("\nNon-null counts per feature (check for gaps!):")
    print(final[["chl_a", "temp", "phosphorus"]].notna().sum())


if __name__ == "__main__":
    main()
