from __future__ import annotations

import argparse
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .lakes import (
    DEFAULT_STATIONS,
    DEFAULT_TARGET_LAKES,
    build_lake_targets,
    load_lake_names,
    load_or_build_targets,
    load_station_points,
    normalize_name,
    write_targets_csv,
)
from .nldas import NldasProduct, download_nldas_range, earthdata_session, open_nldas_dataset, opendap_urls
from .sentinel2 import download_sentinel2_batch, download_sentinel2_pass_dates


LOCAL_ENV_KEYS = {
    "EARTHDATA_USERNAME",
    "EARTHDATA_PASSWORD",
    "SH_CLIENT_ID",
    "SH_CLIENT_SECRET",
    "SH_BASE_URL",
    "SH_TOKEN_URL",
}


def main(argv: Optional[list[str]] = None) -> int:
    load_env_file(override=True)
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except RuntimeError as exc:
        parser.exit(2, f"error: {exc}\n")


def load_env_file(path: Path | str = ".env", override: bool = False) -> None:
    path = Path(path)
    if not path.exists():
        return

    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()

        key, value = line.split("=", 1)
        key = key.strip()
        if key not in LOCAL_ENV_KEYS:
            continue
        value = parse_env_value(value)
        if value and (override or key not in os.environ):
            os.environ[key] = value


def parse_env_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    comment_start = value.find(" #")
    if comment_start != -1:
        value = value[:comment_start].rstrip()
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BloomCast NJ data pipeline commands.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    targets = subparsers.add_parser("targets", help="Build a lake target coordinate CSV from station metadata.")
    add_target_source_args(targets)
    targets.add_argument("--out", default="data/processed/lake_targets.csv", help="Output CSV path.")
    targets.set_defaults(func=run_targets)

    nldas = subparsers.add_parser("nldas", help="Download NASA GES DISC NLDAS-2 hourly forcing files.")
    nldas.add_argument("--start", required=True, help="Start date or hour, e.g. 2024-06-01 or 2024-06-01T00.")
    nldas.add_argument("--end", required=True, help="End date or hour. Date-only values include the full day.")
    nldas.add_argument("--out-dir", default="data/raw/nldas", help="Directory for downloaded NLDAS files.")
    nldas.add_argument("--username", default=os.getenv("EARTHDATA_USERNAME"), help="NASA Earthdata username.")
    nldas.add_argument("--password", default=os.getenv("EARTHDATA_PASSWORD"), help="NASA Earthdata password.")
    nldas.add_argument("--overwrite", action="store_true", help="Re-download files that already exist.")
    nldas.add_argument("--print-opendap", action="store_true", help="Print matching OPeNDAP URLs instead of downloading.")
    nldas.add_argument("--open", action="store_true", help="Open the downloaded files with xarray after downloading.")
    nldas.add_argument("--engine", default="netcdf4", help="xarray engine for --open, usually netcdf4 for NLDAS v2.0.")
    nldas.set_defaults(func=run_nldas)

    sentinel = subparsers.add_parser("sentinel2", help="Download Sentinel-2 L2A imagery for target lakes.")
    add_target_source_args(sentinel)
    sentinel.add_argument("--targets-csv", help="Optional reviewed target CSV with name/latitude/longitude columns.")
    sentinel.add_argument("--start", help="Start date for range-mosaic mode, e.g. 2024-06-01.")
    sentinel.add_argument("--end", help="End date for range-mosaic mode, e.g. 2024-06-15.")
    sentinel.add_argument("--out-dir", default="data/raw/sentinel2", help="Directory for Sentinel Hub responses.")
    sentinel.add_argument("--buffer-km", type=float, default=1.5, help="Buffer around each lake centroid.")
    sentinel.add_argument("--resolution-m", type=int, default=10, help="Output pixel resolution in meters.")
    sentinel.add_argument("--max-cloud-cover", type=float, default=0.4, help="Maximum cloud fraction passed to Sentinel Hub.")
    sentinel.add_argument("--limit", type=int, help="Limit number of target lakes, useful for smoke tests.")
    sentinel.add_argument("--dry-run", action="store_true", help="Write a planned manifest without Sentinel Hub credentials.")
    sentinel.add_argument("--lake", action="append", help="Limit to a named lake. Repeat for multiple lakes.")
    sentinel.add_argument("--pass-date", action="append", help="Sentinel-2 acquisition/pass date, YYYY-MM-DD. Repeat for multiple dates.")
    sentinel.set_defaults(func=run_sentinel2)

    return parser


def add_target_source_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--target-lakes", default=str(DEFAULT_TARGET_LAKES), help="Lake-name CSV or Markdown table.")
    parser.add_argument("--stations", default=str(DEFAULT_STATIONS), help="Station metadata CSV with coordinates.")


def run_targets(args: argparse.Namespace) -> int:
    lake_names = load_lake_names(args.target_lakes)
    station_points = load_station_points(args.stations)
    targets = build_lake_targets(lake_names, station_points)
    write_targets_csv(targets, args.out)
    missing = [target.name for target in targets if not target.has_coordinates]
    print(f"Wrote {len(targets)} targets to {args.out}")
    if missing:
        print(f"Missing coordinates for {len(missing)} lake(s): {', '.join(missing)}")
    return 0


def run_nldas(args: argparse.Namespace) -> int:
    start = parse_datetime_arg(args.start, is_end=False)
    end = parse_datetime_arg(args.end, is_end=True)
    product = NldasProduct()

    if args.print_opendap:
        for url in opendap_urls(start, end, product=product):
            print(url)
        return 0

    session = earthdata_session(username=args.username, password=args.password)
    paths = download_nldas_range(
        start=start,
        end=end,
        out_dir=args.out_dir,
        product=product,
        session=session,
        overwrite=args.overwrite,
    )
    print(f"Downloaded or reused {len(paths)} NLDAS file(s) under {args.out_dir}")

    if args.open:
        dataset = open_nldas_dataset(paths, engine=args.engine)
        print(dataset)
    return 0


def run_sentinel2(args: argparse.Namespace) -> int:
    targets = load_or_build_targets(
        target_lakes_path=args.target_lakes,
        stations_path=args.stations,
        target_csv_path=args.targets_csv,
    )
    if args.lake:
        requested = {normalize_name(lake) for lake in args.lake}
        filtered_targets = []
        found = set()
        for target in targets:
            target_keys = {normalize_name(target.name), normalize_name(target.slug)}
            if target_keys & requested:
                filtered_targets.append(target)
                found.update(target_keys & requested)
        targets = filtered_targets
        missing = sorted(requested - found)
        if missing:
            raise SystemExit(f"No target coordinates found for requested lake(s): {', '.join(missing)}")

    if args.pass_date:
        if args.limit is not None:
            targets = targets[: args.limit]
        results = download_sentinel2_pass_dates(
            targets=targets,
            pass_dates=args.pass_date,
            out_dir=args.out_dir,
            buffer_km=args.buffer_km,
            resolution_m=args.resolution_m,
            max_cloud_cover=args.max_cloud_cover,
            dry_run=args.dry_run,
        )
    else:
        if not args.start or not args.end:
            raise SystemExit("Range-mosaic mode requires --start and --end. Pass-date mode requires --pass-date.")
        results = download_sentinel2_batch(
            targets=targets,
            start=args.start,
            end=args.end,
            out_dir=args.out_dir,
            buffer_km=args.buffer_km,
            resolution_m=args.resolution_m,
            max_cloud_cover=args.max_cloud_cover,
            limit=args.limit,
            dry_run=args.dry_run,
        )
    skipped = sum(1 for result in results if result.skipped)
    mode = "planned" if args.dry_run else "processed"
    print(f"{mode.title()} {len(results)} Sentinel-2 target(s); skipped {skipped}. Manifest: {Path(args.out_dir) / 'manifest.csv'}")
    return 0


def parse_datetime_arg(value: str, is_end: bool) -> datetime:
    if len(value) == 10:
        parsed = datetime.strptime(value, "%Y-%m-%d")
        return parsed + timedelta(hours=23) if is_end else parsed
    return datetime.fromisoformat(value)


if __name__ == "__main__":
    raise SystemExit(main())
