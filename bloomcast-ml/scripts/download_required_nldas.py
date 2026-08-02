"""Checkpointed downloader for the NLDAS windows required by training labels."""
from __future__ import annotations

import argparse
import os
from datetime import datetime
from pathlib import Path

import pandas as pd

from .nldas import NldasProduct, download_file, earthdata_session, iter_hours


def load_env(path: str | Path) -> None:
    path = Path(path)
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def required_hours(ranges_csv: str | Path) -> list[datetime]:
    ranges = pd.read_csv(ranges_csv, parse_dates=["start", "end"])
    hours = set()
    for row in ranges.itertuples(index=False):
        hours.update(iter_hours(row.start.to_pydatetime(), row.end.to_pydatetime().replace(hour=23)))
    return sorted(hours)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ranges", default="data/nldas_required_ranges.csv")
    parser.add_argument("--out-dir", default="data/raw/nldas")
    parser.add_argument("--env", default="../.env")
    parser.add_argument("--max-files", type=int)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    load_env(args.env)
    product = NldasProduct()
    hours = required_hours(args.ranges)
    pending = [ts for ts in hours if not product.local_path(ts, args.out_dir).exists()]
    selected = pending[:args.max_files] if args.max_files is not None else pending
    print(f"required={len(hours)} existing={len(hours)-len(pending)} pending={len(pending)} selected={len(selected)}")
    if args.dry_run:
        if selected:
            print(product.url(selected[0]))
            print(product.url(selected[-1]))
        return
    session = earthdata_session()
    for index, timestamp in enumerate(selected, 1):
        download_file(product.url(timestamp), product.local_path(timestamp, args.out_dir), session)
        if index == 1 or index % 24 == 0 or index == len(selected):
            print(f"downloaded {index}/{len(selected)} through {timestamp:%Y-%m-%dT%H}:00")


if __name__ == "__main__":
    main()
