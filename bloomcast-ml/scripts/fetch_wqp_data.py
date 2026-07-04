"""
BloomCast NJ - build tabular_features.csv from the EPA/USGS Water Quality Portal (WQP)

Run this yourself (needs internet access) from inside bloomcast-ml, with your
`bloomcast` conda env active:

    conda activate bloomcast
    pip install requests pandas   # if not already installed
    python scripts/fetch_wqp_data.py

WHAT THIS DOES
--------------
Queries the public WQP Result-search REST API for chlorophyll-a, water
temperature, total nitrogen, and total phosphorus at your three lakes, then
reshapes everything into one long-format CSV:

    lake, date, chl_a, temp, nitrogen, phosphorus

WQP REST docs: https://www.waterqualitydata.us/webservices_documentation/

IMPORTANT - CHECK THE OUTPUT
------------------------------
1. This version searches by lat/long + radius instead of guessing exact
   site IDs, so it should catch every relevant lake/reservoir station
   nearby - but the lake center coordinates below are approximate. If a
   lake still comes back thin, try increasing its "radius" value in the
   LAKES dict below, or double-check the coordinates against a map.

2. SITE_TYPES is restricted to "Lake, Reservoir, Impoundment" so a radius
   search doesn't accidentally pull in nearby streams/tributaries. If a
   lake still comes back empty, it may be worth removing that filter to
   see what's actually nearby (some agencies may classify sites
   differently).

3. Not every site will have every characteristic (esp. nitrogen/phosphorus
   sub-types vary: "Nitrogen", "Total Nitrogen", "Phosphorus", "Phosphate-
   phosphorus", etc.) - the script tries several common variants but check
   the printed row counts to see what's actually available.
"""

import io
import time

import pandas as pd
import requests

BASE_URL = "https://www.waterqualitydata.us/data/Result/search"

# ---- Lake center coordinates + search radius (miles) ----
# Coordinates are approximate lake centers/main basins. Widen RADIUS_MILES
# if a lake still comes back with too little data.
LAKES = {
    "Lake Hopatcong": {"lat": 40.9370, "long": -74.6560, "radius": 3},
    "Round Valley Reservoir": {"lat": 40.6176, "long": -74.8263, "radius": 3},
    "Budd Lake": {"lat": 40.8659, "long": -74.7407, "radius": 2},
}

# Restrict to actual lake/reservoir sites so a radius search doesn't pull in
# nearby streams/tributaries by accident.
SITE_TYPES = ["Lake, Reservoir, Impoundment"]

# ---- Characteristic name variants to try for each feature ----
CHARACTERISTICS = {
    "chl_a": ["Chlorophyll a"],
    "temp": ["Temperature, water"],
    "phosphorus": [
        "Phosphorus",
        "Total Phosphorus, mixed forms",
        "Phosphate-phosphorus",
        "Orthophosphate",
    ],
    # nitrogen dropped: confirmed 0 rows across all 3 lakes and multiple
    # name variants when queried via WQP. If you want to revisit this,
    # the Lake Hopatcong Commission's own annual water quality reports
    # (PDF) do report ammonia-N directly - would need manual extraction.
}

START_DATE = "01-01-2015"  # mm-dd-yyyy, adjust as needed
END_DATE = "12-31-2025"


def fetch_one_name(lat: float, long: float, radius: float, characteristic_name: str) -> pd.DataFrame:
    """Query WQP for a lat/long + radius search + a SINGLE characteristic
    name. Never raises - prints a warning and returns an empty frame on any
    failure so one bad name can't kill the whole run."""
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
    """Try each characteristic name variant separately, concatenate whatever
    comes back. This way one invalid name doesn't block a valid one."""
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

    # merge all features on their ACTUAL sample dates - do NOT force onto an
    # artificial weekly grid. Real field sampling for these lakes is roughly
    # monthly during the growing season, so a weekly grid would manufacture
    # thousands of empty rows that were never going to have data anyway.
    combined = pd.concat(frames, axis=1)
    combined = combined.sort_index()

    # make sure every expected feature column exists, even if this lake had
    # zero data for one of them (e.g. no nitrogen readings at all)
    for feature in CHARACTERISTICS:
        if feature not in combined.columns:
            combined[feature] = pd.NA

    # drop rows where every feature is missing (shouldn't happen much since
    # we merge on real dates, but just in case)
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