from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr


def extract_features(raw_dir: str | Path, targets_csv: str | Path) -> pd.DataFrame:
    targets = pd.read_csv(targets_csv).dropna(subset=["latitude", "longitude"])
    records = []
    for path in sorted(Path(raw_dir).rglob("*.nc*")):
        with xr.open_dataset(path) as ds:
            timestamp = pd.Timestamp(ds["time"].values[0])
            for target in targets.itertuples(index=False):
                point = ds.sel(lat=float(target.latitude), lon=float(target.longitude), method="nearest").isel(time=0)
                east, north = float(point["Wind_E"]), float(point["Wind_N"])
                records.append({
                    "lake": target.name, "date": timestamp.normalize(), "timestamp": timestamp,
                    "air_temp_c": float(point["Tair"]) - 273.15,
                    "specific_humidity": float(point["Qair"]),
                    "surface_pressure_pa": float(point["PSurf"]),
                    "wind_speed_ms": float(np.hypot(east, north)),
                    "precip_kg_m2": float(point["Rainf"]),
                    "shortwave_wm2": float(point["SWdown"]),
                    "longwave_wm2": float(point["LWdown"]),
                    "cape_jkg": float(point["CAPE"]),
                })
    hourly = pd.DataFrame(records)
    if hourly.empty:
        return hourly
    sums = hourly.groupby(["lake", "date"], as_index=False)["precip_kg_m2"].sum()
    means = hourly.groupby(["lake", "date"], as_index=False)[
        ["air_temp_c", "specific_humidity", "surface_pressure_pa", "wind_speed_ms",
         "shortwave_wm2", "longwave_wm2", "cape_jkg"]
    ].mean()
    counts = hourly.groupby(["lake", "date"]).size().rename("hours").reset_index()
    return means.merge(sums, on=["lake", "date"]).merge(counts, on=["lake", "date"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", required=True)
    parser.add_argument("--targets", default="data/lake_targets.csv")
    parser.add_argument("--out", default="data/nldas_daily_features.csv")
    args = parser.parse_args()
    result = extract_features(args.raw_dir, args.targets)
    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(out, index=False)
    print(f"Wrote {len(result)} lake-day NLDAS rows to {out}")


if __name__ == "__main__":
    main()
