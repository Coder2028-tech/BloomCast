from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


KEYS = ["lake", "date"]


def _read(path: str | Path | None, prefix: str = "") -> pd.DataFrame | None:
    if not path:
        return None
    frame = pd.read_csv(path, parse_dates=["date"])
    required = set(KEYS)
    if not required.issubset(frame.columns):
        raise ValueError(f"{path} must contain columns: {sorted(required)}")
    if prefix:
        frame = frame.rename(columns={c: f"{prefix}{c}" for c in frame.columns if c not in KEYS})
    return frame.sort_values(KEYS)


def _next_week_targets(group: pd.DataFrame, horizon_days: int, tolerance_days: int) -> pd.DataFrame:
    group = group.sort_values("date").copy()
    dates = group["date"].to_numpy(dtype="datetime64[ns]")
    values = group["chl_a"].to_numpy(dtype=float)
    targets = np.full(len(group), np.nan)
    target_dates = np.full(len(group), np.datetime64("NaT"), dtype="datetime64[ns]")
    gaps = np.full(len(group), np.nan)
    for index, date in enumerate(dates):
        day_gaps = (dates - date).astype("timedelta64[D]").astype(int)
        candidates = np.where(
            (day_gaps >= horizon_days - tolerance_days)
            & (day_gaps <= horizon_days + tolerance_days)
            & np.isfinite(values)
        )[0]
        if len(candidates):
            chosen = candidates[np.argmin(np.abs(day_gaps[candidates] - horizon_days))]
            targets[index] = values[chosen]
            target_dates[index] = dates[chosen]
            gaps[index] = day_gaps[chosen]
    group["target_chl_a_next_week"] = targets
    group["target_date"] = target_dates
    group["target_gap_days"] = gaps
    return group


def _weather_windows(observations: pd.DataFrame, weather: pd.DataFrame, days: int = 7) -> pd.DataFrame:
    feature_cols = [c for c in weather.columns if c not in KEYS]
    rows: list[dict] = []
    weather_groups = {lake: g.set_index("date") for lake, g in weather.groupby("lake")}
    for row in observations[KEYS].itertuples(index=False):
        subset = weather_groups.get(row.lake)
        values = {"lake": row.lake, "date": row.date, "nldas_days": 0, "nldas_hours": 0}
        if subset is not None:
            window = subset.loc[row.date - pd.Timedelta(days=days - 1):row.date]
            values["nldas_days"] = int(len(window))
            for col in feature_cols:
                numeric = pd.to_numeric(window[col], errors="coerce")
                if col == "nldas_hours":
                    values[col] = float(numeric.sum(min_count=1))
                else:
                    values[col] = float(numeric.sum(min_count=1)) if "precip" in col or "rain" in col else float(numeric.mean())
        rows.append(values)
    return pd.DataFrame(rows)


def _merge_satellite_asof(rows: pd.DataFrame, satellite: pd.DataFrame, tolerance_days: int = 14) -> pd.DataFrame:
    pieces = []
    for lake, left in rows.groupby("lake", sort=False):
        right = satellite[satellite["lake"] == lake].drop(columns="lake").sort_values("date")
        if right.empty:
            pieces.append(left)
            continue
        right = right.rename(columns={"date": "satellite_date"})
        merged = pd.merge_asof(
            left.sort_values("date"), right, left_on="date", right_on="satellite_date",
            direction="backward", tolerance=pd.Timedelta(days=tolerance_days),
        )
        pieces.append(merged)
    return pd.concat(pieces, ignore_index=True) if pieces else rows


def build_training_dataset(
    observations: pd.DataFrame,
    weather: pd.DataFrame | None = None,
    satellite: pd.DataFrame | None = None,
    land_use: pd.DataFrame | None = None,
    horizon_days: int = 7,
    tolerance_days: int = 3,
) -> pd.DataFrame:
    required = {"lake", "date", "chl_a"}
    if not required.issubset(observations.columns):
        raise ValueError(f"observations must contain {sorted(required)}")
    observations = observations.sort_values(KEYS).copy()
    observations["chl_a"] = pd.to_numeric(observations["chl_a"], errors="coerce")
    observations["past_chl_a"] = observations["chl_a"]
    observations["past_chl_a_previous"] = observations.groupby("lake")["chl_a"].shift(1)
    rows = pd.concat(
        [
            _next_week_targets(group, horizon_days=horizon_days, tolerance_days=tolerance_days)
            for _, group in observations.groupby("lake", sort=False)
        ],
        ignore_index=True,
    )

    if weather is not None:
        rows = rows.merge(_weather_windows(rows, weather), on=KEYS, how="left")
    if satellite is not None:
        rows = _merge_satellite_asof(rows, satellite)
    if land_use is not None:
        land = land_use.drop(columns=["date"], errors="ignore").drop_duplicates("lake")
        rows = rows.merge(land, on="lake", how="left")

    # A seven-day feature window is valid only with all 168 hourly inputs.
    rows["has_weather"] = rows.get("nldas_hours", pd.Series(0, index=rows.index)).fillna(0).ge(168)
    rows["has_satellite"] = rows.filter(regex=r"^satellite_").notna().any(axis=1)
    rows["has_land_use"] = rows.filter(regex=r"^land_").notna().any(axis=1)
    return rows[rows["target_chl_a_next_week"].notna() & rows["past_chl_a"].notna()].reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--observations", default="data/tabular_features.csv")
    parser.add_argument("--weather")
    parser.add_argument("--satellite")
    parser.add_argument("--land-use")
    parser.add_argument("--out", default="data/training_lake_date.csv")
    parser.add_argument("--coverage-out", default="results/training_data_coverage.json")
    parser.add_argument("--nldas-ranges-out", default="data/nldas_required_ranges.csv")
    parser.add_argument("--horizon-days", type=int, default=7)
    parser.add_argument("--tolerance-days", type=int, default=3)
    args = parser.parse_args()
    observations = _read(args.observations)
    dataset = build_training_dataset(
        observations,
        weather=_read(args.weather, "nldas_"),
        satellite=_read(args.satellite, "satellite_"),
        land_use=_read(args.land_use, "land_"),
        horizon_days=args.horizon_days,
        tolerance_days=args.tolerance_days,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(out, index=False)
    coverage = {
        "rows": int(len(dataset)),
        "lakes": int(dataset["lake"].nunique()),
        "date_min": None if dataset.empty else str(dataset["date"].min().date()),
        "date_max": None if dataset.empty else str(dataset["date"].max().date()),
        "rows_with_weather": int(dataset["has_weather"].sum()),
        "rows_with_satellite": int(dataset["has_satellite"].sum()),
        "rows_with_land_use": int(dataset["has_land_use"].sum()),
    }
    coverage_out = Path(args.coverage_out)
    coverage_out.parent.mkdir(parents=True, exist_ok=True)
    coverage_out.write_text(json.dumps(coverage, indent=2) + "\n")
    required_ranges = dataset[["lake", "date"]].drop_duplicates().copy()
    required_ranges["start"] = required_ranges["date"] - pd.Timedelta(days=6)
    required_ranges["end"] = required_ranges["date"]
    ranges_out = Path(args.nldas_ranges_out)
    ranges_out.parent.mkdir(parents=True, exist_ok=True)
    required_ranges[["lake", "start", "end"]].to_csv(ranges_out, index=False)
    print(f"Wrote {len(dataset)} leakage-safe lake-date rows to {out}")
    print(dataset[["has_weather", "has_satellite", "has_land_use"]].sum().to_string())


if __name__ == "__main__":
    main()
