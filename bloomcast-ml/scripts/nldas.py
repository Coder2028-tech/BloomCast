"""NLDAS-2 URL construction and resilient NASA Earthdata downloads."""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator, Optional

import requests
from requests.adapters import HTTPAdapter


DATA_ROOT = "https://hydro1.gesdisc.eosdis.nasa.gov/data/NLDAS"
AUTH_HOST = "urs.earthdata.nasa.gov"
ALLOWED_AUTH_HOSTS = {AUTH_HOST, "hydro1.gesdisc.eosdis.nasa.gov", "data.gesdisc.earthdata.nasa.gov"}


class EarthdataSession(requests.Session):
    """Preserve Earthdata credentials only across NASA's known redirect hosts."""

    def rebuild_auth(self, prepared_request, response) -> None:
        original = requests.utils.urlparse(response.request.url).hostname
        redirect = requests.utils.urlparse(prepared_request.url).hostname
        if original in ALLOWED_AUTH_HOSTS and redirect in ALLOWED_AUTH_HOSTS:
            return
        super().rebuild_auth(prepared_request, response)


def earthdata_session(token: Optional[str] = None, username: Optional[str] = None,
                      password: Optional[str] = None) -> EarthdataSession:
    token = token or os.getenv("EARTHDATA_TOKEN")
    username = username or os.getenv("EARTHDATA_USERNAME")
    password = password or os.getenv("EARTHDATA_PASSWORD")
    if not token and bool(username) != bool(password):
        raise ValueError("Set EARTHDATA_TOKEN, or both EARTHDATA_USERNAME and EARTHDATA_PASSWORD.")
    session = EarthdataSession()
    session.trust_env = True  # permits .netrc when explicit credentials are absent
    session.headers.update({"User-Agent": "BloomCastNJ/0.2", "Accept": "application/x-netcdf,application/octet-stream"})
    if token:
        session.headers["Authorization"] = f"Bearer {token}"
    elif username and password:
        session.auth = (username, password)
    session.mount("https://", HTTPAdapter(pool_connections=4, pool_maxsize=4))
    return session


@dataclass(frozen=True)
class NldasProduct:
    short_name: str = "NLDAS_FORA0125_H"
    version: str = "2.0"
    file_version: str = "020"
    # GES DISC collection 2.0 currently serves these as .020.nc. The collection
    # version remains 2.0, while the filename version is the zero-padded 020.
    extension: str = "nc"

    @property
    def collection(self) -> str:
        return f"{self.short_name}.{self.version}"

    def file_name(self, timestamp: datetime) -> str:
        return f"{self.short_name}.A{timestamp:%Y%m%d}.{timestamp:%H}00.{self.file_version}.{self.extension}"

    def url(self, timestamp: datetime) -> str:
        return f"{DATA_ROOT}/{self.collection}/{timestamp:%Y}/{timestamp:%j}/{self.file_name(timestamp)}"

    def local_path(self, timestamp: datetime, out_dir: str | Path) -> Path:
        return Path(out_dir) / self.collection / f"{timestamp:%Y}" / f"{timestamp:%j}" / self.file_name(timestamp)


def iter_hours(start: datetime, end: datetime) -> Iterator[datetime]:
    current = start.replace(minute=0, second=0, microsecond=0)
    last = end.replace(minute=0, second=0, microsecond=0)
    while current <= last:
        yield current
        current += timedelta(hours=1)


def _looks_like_netcdf(path: Path) -> bool:
    if path.stat().st_size < 8:
        return False
    with path.open("rb") as handle:
        signature = handle.read(8)
    return signature.startswith(b"CDF") or signature == b"\x89HDF\r\n\x1a\n"


def download_file(url: str, destination: str | Path, session: requests.Session,
                  overwrite: bool = False, attempts: int = 5) -> Path:
    destination = Path(destination)
    if destination.exists() and not overwrite:
        if _looks_like_netcdf(destination):
            return destination
        raise RuntimeError(f"Existing file is not NetCDF: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            with session.get(url, stream=True, allow_redirects=True, timeout=(30, 180)) as response:
                if response.status_code in {401, 403}:
                    raise RuntimeError("Earthdata authorization failed. Generate a token and set EARTHDATA_TOKEN; do not commit it.")
                # GES DISC/CDN has occasionally returned transient 404s for known files.
                if response.status_code == 404 and attempt < attempts:
                    raise requests.HTTPError("Transient 404", response=response)
                response.raise_for_status()
                content_type = response.headers.get("content-type", "").lower()
                if "text/html" in content_type:
                    raise RuntimeError("Earthdata returned a login/HTML page instead of NetCDF data.")
                with partial.open("wb") as handle:
                    for chunk in response.iter_content(1024 * 1024):
                        if chunk:
                            handle.write(chunk)
            if not _looks_like_netcdf(partial):
                raise RuntimeError("Downloaded response is not a NetCDF/HDF5 file.")
            partial.replace(destination)
            return destination
        except (requests.RequestException, RuntimeError) as exc:
            last_error = exc
            partial.unlink(missing_ok=True)
            if attempt == attempts or (isinstance(exc, RuntimeError) and "authorization failed" in str(exc)):
                break
            time.sleep(min(2 ** (attempt - 1), 16))
    raise RuntimeError(f"Failed to download {url} after {attempts} attempts: {last_error}") from last_error


def download_nldas_range(start: datetime, end: datetime, out_dir: str | Path,
                         product: NldasProduct = NldasProduct(), session=None,
                         overwrite: bool = False) -> list[Path]:
    session = session or earthdata_session()
    return [download_file(product.url(ts), product.local_path(ts, out_dir), session, overwrite)
            for ts in iter_hours(start, end)]
