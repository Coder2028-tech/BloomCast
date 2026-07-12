from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Iterator, Optional, Sequence

import requests

from .lakes import LakeTarget


GES_DISC_DATA_ROOT = "https://hydro1.gesdisc.eosdis.nasa.gov/data/NLDAS"
GES_DISC_OPENDAP_ROOT = "https://hydro1.gesdisc.eosdis.nasa.gov/opendap/NLDAS"


@dataclass(frozen=True)
class NldasProduct:
    short_name: str = "NLDAS_FORA0125_H"
    version: str = "002"
    extension: str = "grb"

    @property
    def collection(self) -> str:
        return f"{self.short_name}.{self.version}"

    def file_name(self, timestamp: datetime) -> str:
        return f"{self.short_name}.A{timestamp:%Y%m%d}.{timestamp:%H}00.{self.version}.{self.extension}"

    def url(self, timestamp: datetime, access: str = "data") -> str:
        root = GES_DISC_OPENDAP_ROOT if access == "opendap" else GES_DISC_DATA_ROOT
        return "/".join(
            [
                root.rstrip("/"),
                self.collection,
                f"{timestamp:%Y}",
                f"{timestamp:%j}",
                self.file_name(timestamp),
            ]
        )

    def local_path(self, timestamp: datetime, out_dir: Path | str) -> Path:
        out_dir = Path(out_dir)
        return out_dir / self.collection / f"{timestamp:%Y}" / f"{timestamp:%j}" / self.file_name(timestamp)


def earthdata_session(
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> requests.Session:
    username = username or os.getenv("EARTHDATA_USERNAME")
    password = password or os.getenv("EARTHDATA_PASSWORD")

    if bool(username) != bool(password):
        raise ValueError("Set both EARTHDATA_USERNAME and EARTHDATA_PASSWORD, or use a .netrc file.")

    session = requests.Session()
    session.headers.update({"User-Agent": "BloomCastNJ/0.1"})
    session.trust_env = True
    if username and password:
        session.auth = (username, password)
    return session


def iter_hours(start: datetime, end: datetime) -> Iterator[datetime]:
    if end < start:
        raise ValueError("end must be on or after start")

    current = start.replace(minute=0, second=0, microsecond=0)
    last = end.replace(minute=0, second=0, microsecond=0)
    while current <= last:
        yield current
        current += timedelta(hours=1)


def download_nldas_range(
    start: datetime,
    end: datetime,
    out_dir: Path | str,
    product: NldasProduct = NldasProduct(),
    session: Optional[requests.Session] = None,
    overwrite: bool = False,
) -> list[Path]:
    session = session or earthdata_session()
    downloaded: list[Path] = []
    for timestamp in iter_hours(start, end):
        url = product.url(timestamp)
        destination = product.local_path(timestamp, out_dir)
        download_file(url, destination, session=session, overwrite=overwrite)
        downloaded.append(destination)
    return downloaded


def download_file(
    url: str,
    destination: Path | str,
    session: requests.Session,
    overwrite: bool = False,
    chunk_size: int = 1024 * 1024,
) -> Path:
    destination = Path(destination)
    if destination.exists() and not overwrite:
        return destination

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = destination.with_suffix(destination.suffix + ".part")

    with session.get(url, stream=True, allow_redirects=True, timeout=120) as response:
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").lower()
        if "text/html" in content_type:
            raise RuntimeError(
                "NASA returned an HTML page instead of data. Check Earthdata credentials and data access approval."
            )

        with temporary_path.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    handle.write(chunk)

    temporary_path.replace(destination)
    return destination


def open_nldas_dataset(
    paths_or_urls: Sequence[Path | str],
    engine: str = "cfgrib",
    chunks: Optional[dict] = None,
):
    try:
        import xarray as xr
    except ImportError as exc:
        raise RuntimeError("Install xarray to open NLDAS data: pip install -r requirements.txt") from exc

    paths = [str(path) for path in paths_or_urls]
    kwargs = {"engine": engine, "combine": "by_coords", "chunks": chunks}
    if engine == "cfgrib":
        kwargs["backend_kwargs"] = {"indexpath": ""}
    return xr.open_mfdataset(paths, **kwargs)


def subset_dataset_to_targets(
    dataset,
    targets: Iterable[LakeTarget],
    padding_degrees: float = 0.25,
):
    targets_with_coordinates = [target for target in targets if target.has_coordinates]
    if not targets_with_coordinates:
        raise ValueError("No target coordinates are available for subsetting.")

    lat_name = _first_existing_coord(dataset, ["lat", "latitude", "y"])
    lon_name = _first_existing_coord(dataset, ["lon", "longitude", "x"])
    if not lat_name or not lon_name:
        raise ValueError("Could not find latitude/longitude coordinates in the dataset.")

    min_lat = min(float(target.latitude) for target in targets_with_coordinates) - padding_degrees
    max_lat = max(float(target.latitude) for target in targets_with_coordinates) + padding_degrees
    min_lon = min(float(target.longitude) for target in targets_with_coordinates) - padding_degrees
    max_lon = max(float(target.longitude) for target in targets_with_coordinates) + padding_degrees

    lon_values = dataset[lon_name]
    if float(lon_values.max()) > 180 and min_lon < 0:
        min_lon += 360
        max_lon += 360

    lat_values = dataset[lat_name]
    lat_slice = slice(max_lat, min_lat) if float(lat_values[0]) > float(lat_values[-1]) else slice(min_lat, max_lat)
    return dataset.sel({lat_name: lat_slice, lon_name: slice(min_lon, max_lon)})


def opendap_urls(
    start: datetime,
    end: datetime,
    product: NldasProduct = NldasProduct(),
) -> list[str]:
    return [product.url(timestamp, access="opendap") for timestamp in iter_hours(start, end)]


def _first_existing_coord(dataset, candidates: Sequence[str]) -> Optional[str]:
    for name in candidates:
        if name in dataset.coords or name in dataset.variables:
            return name
    return None
