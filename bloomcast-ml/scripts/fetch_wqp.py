from __future__ import annotations

import io
import time
from pathlib import Path

import pandas as pd
import requests

BASE_URL = "https://www.waterqualitydata.us/data/Result/search"
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

YEARS = list(range(2015, 2026))

STATE_FIPS = ["34"]

OUT_DIR = Path("data/wqp_states")
FINAL_OUT = Path("data/tabular_features.csv")

SITE_COL = "MonitoringLocationIdentifier"
NAME_COL = "MonitoringLocationName"
DATE_COL = "ActivityStartDate"
VALUE_COL = "ResultMeasureValue"

MAX_RETRIES = 4
RETRY_BACKOFF_SECONDS = 10
BETWEEN_CALLS_SECONDS = 0.3
REQUEST_TIMEOUT = 180


def _fetch_year(statecode, characteristic_name, year):
    params = {
        "statecode": f"US:{statecode}",
        "siteType": SITE_TYPES,
        "characteristicName": characteristic_name,
        "startDateLo": f"01-01-{year}",
        "startDateHi": f"12-31-{year}",
        "mimeType": "csv",
        "zip": "no",
    }
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(BASE_URL, params=params, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            wait = RETRY_BACKOFF_SECONDS * attempt
            print(f"      [retry {attempt}/{MAX_RETRIES}] {characteristic_name} {year}: {e} -> {wait}s")
            time.sleep(wait)
            continue
        if not resp.text.strip():
            return pd.DataFrame()
        try:
            return pd.read_csv(io.StringIO(resp.text), low_memory=False)
        except pd.errors.EmptyDataError:
            return pd.DataFrame()
    print(f"      [give up] {characteristic_name} {year} for US:{statecode}")
    return pd.DataFrame()


def fetch_state_characteristic(statecode, characteristic_names):
    frames = []
    for name in characteristic_names:
        for year in YEARS:
            df = _fetch_year(statecode, name, year)
            if not df.empty:
                needed = [SITE_COL, DATE_COL, VALUE_COL]
                if all(col in df.columns for col in needed):
                    cols = [SITE_COL, DATE_COL, VALUE_COL]
                    if NAME_COL in df.columns:
                        cols.insert(1, NAME_COL)
                    frames.append(df[cols])
                    print(f"      {name} {year}: {len(df)} rows")
            time.sleep(BETWEEN_CALLS_SECONDS)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def build_state_data(statecode):
    print(f"\n=== US:{statecode} ===")
    feature_frames = []
    for feature, char_names in CHARACTERISTICS.items():
        print(f"  {feature} ...")
        raw = fetch_state_characteristic(statecode, char_names)
        if raw.empty:
            print(f"    no {feature} data")
            continue
        keep = raw.rename(columns={
            SITE_COL: "lake", NAME_COL: "lake_name",
            DATE_COL: "date", VALUE_COL: feature,
        })
        keep["date"] = pd.to_datetime(keep["date"], errors="coerce")
        keep[feature] = pd.to_numeric(keep[feature], errors="coerce")
        keep = keep.dropna(subset=["date", feature, "lake"])
        agg = {feature: "mean"}
        if "lake_name" in keep.columns:
            agg["lake_name"] = "first"
        keep = keep.groupby(["lake", "date"], as_index=False).agg(agg)
        print(f"    -> {len(keep)} site-date rows for {feature}")
        feature_frames.append(keep)
    if not feature_frames:
        print(f"  WARNING: no data for US:{statecode}")
        return pd.DataFrame()
    merged = feature_frames[0]
    for frame in feature_frames[1:]:
        merged = merged.merge(frame, on=["lake", "date"], how="outer", suffixes=("", "_dup"))
        if "lake_name_dup" in merged.columns:
            merged["lake_name"] = merged["lake_name"].fillna(merged["lake_name_dup"])
            merged = merged.drop(columns=["lake_name_dup"])
    for feature in CHARACTERISTICS:
        if feature not in merged.columns:
            merged[feature] = pd.NA
    merged = merged.dropna(how="all", subset=list(CHARACTERISTICS.keys()))
    ordered = ["lake", "date"] + list(CHARACTERISTICS.keys())
    if "lake_name" in merged.columns:
        ordered.append("lake_name")
    return merged[ordered].sort_values(["lake", "date"]).reset_index(drop=True)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for statecode in STATE_FIPS:
        checkpoint = OUT_DIR / f"state_{statecode}.csv"
        if checkpoint.exists():
            print(f"US:{statecode} already done, skipping")
            continue
        state_df = build_state_data(statecode)
        state_df.to_csv(checkpoint, index=False)
        print(f"  wrote {len(state_df)} rows -> {checkpoint}")
    parts = []
    for checkpoint in sorted(OUT_DIR.glob("state_*.csv")):
        part = pd.read_csv(checkpoint, parse_dates=["date"])
        if not part.empty:
            parts.append(part)
    if not parts:
        print("\nNo data pulled. Nothing written.")
        return
    national = pd.concat(parts, ignore_index=True).sort_values(["lake", "date"])
    FINAL_OUT.parent.mkdir(parents=True, exist_ok=True)
    national.to_csv(FINAL_OUT, index=False)
    print(f"\nSaved {len(national)} rows / {national['lake'].nunique()} sites -> {FINAL_OUT}")
    print("\nNon-null per feature:")
    print(national[list(CHARACTERISTICS.keys())].notna().sum())
    print(f"States with data: {len(parts)} / {len(STATE_FIPS)}")


if __name__ == "__main__":
    main()
