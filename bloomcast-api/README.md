# BloomCast NJ Data Pipelines

This workspace now includes Python data-download tooling for the two remote sensing inputs:

- NASA GES DISC NLDAS-2 hourly forcing files, authenticated with NASA Earthdata and opened with xarray.
- Sentinel-2 L2A lake imagery, downloaded through sentinelhub-py for the target lake list.

## Setup

Install the pipeline dependencies:

```bash
python3 -m pip install -r requirements.txt
```

NASA Earthdata can use either environment variables or a `.netrc` entry:

```bash
export EARTHDATA_USERNAME="your-earthdata-user"
export EARTHDATA_PASSWORD="your-earthdata-password"
```

The CLI reads `.env` automatically. You do not need to run `source .env`; shell-loading can shorten passwords that contain characters like `$`.

For NASA GES DISC downloads, also create Earthdata prerequisite files once per computer:

```bash
python3 - <<'PY'
from pathlib import Path

env_values = {}
for raw_line in Path(".env").read_text().splitlines():
    line = raw_line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    if line.startswith("export "):
        line = line[len("export "):].lstrip()
    key, value = line.split("=", 1)
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    env_values[key.strip()] = value

home = Path.home()
username = env_values["EARTHDATA_USERNAME"]
password = env_values["EARTHDATA_PASSWORD"]
netrc_path = home / ".netrc"

netrc_lines = []
if netrc_path.exists():
    netrc_lines = [
        line
        for line in netrc_path.read_text().splitlines()
        if not line.strip().startswith("machine urs.earthdata.nasa.gov ")
    ]
netrc_lines.append(f"machine urs.earthdata.nasa.gov login {username} password {password}")
netrc_path.write_text("\n".join(netrc_lines) + "\n")
(home / ".urs_cookies").touch()
(home / ".dodsrc").write_text(
    f"HTTP.COOKIEJAR={home / '.urs_cookies'}\n"
    f"HTTP.NETRC={home / '.netrc'}\n"
)

for filename in [".netrc", ".urs_cookies", ".dodsrc"]:
    (home / filename).chmod(0o600)

print("Earthdata prerequisite files created.")
PY
```

Then sign in to Earthdata in a browser and authorize GES DISC data access for the same account.

Copernicus Data Space Sentinel Hub services use OAuth client credentials:

```bash
export SH_CLIENT_ID="your-sentinelhub-client-id"
export SH_CLIENT_SECRET="your-sentinelhub-client-secret"
export SH_BASE_URL="https://sh.dataspace.copernicus.eu"
export SH_TOKEN_URL="https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
```

## Lake Targets

`target_lakes.csv` is currently a Markdown-style table. The target builder supports that format and normal CSV files.

Build a reviewed coordinate file from `station.csv`:

```bash
python3 -m bloomcast.data.cli targets --out data/processed/lake_targets.csv
```

The generated file includes match counts and notes. Review any missing or ambiguous coordinates before running a full Sentinel download.

Current station matching finds coordinates for 23 of the 25 target lakes. `Shepherd Lake` and `Culver Lake` need manual latitude/longitude values in `data/processed/lake_targets.csv` before they can be included in Sentinel requests.

## NLDAS-2

Download hourly NLDAS-2 primary forcing netCDF files from NASA GES DISC:

```bash
python3 -m bloomcast.data.cli nldas \
  --start 2024-06-01 \
  --end 2024-06-02 \
  --out-dir data/raw/nldas
```

Date-only `--end` values include the whole day. Use `--print-opendap` to inspect matching OPeNDAP URLs, and `--open` to open downloaded netCDF files with xarray:

```bash
python3 -m bloomcast.data.cli nldas \
  --start 2024-06-01T00 \
  --end 2024-06-01T03 \
  --out-dir data/raw/nldas \
  --open
```

The default xarray engine is `netcdf4`. NASA GES DISC now serves `NLDAS_FORA0125_H.2.0` as hourly netCDF `.020.nc` files rather than the older Version 002 GRIB files.

For the July 11, 2026 sampled-lake handoff, `data/processed/nldas_2026-07-04_2026-07-11_manifest.csv` inventories the 192 downloaded hourly files.

## Sentinel-2

Download Sentinel-2 L2A GeoTIFF responses for the lake targets:

```bash
python3 -m bloomcast.data.cli sentinel2 \
  --targets-csv data/processed/lake_targets.csv \
  --start 2024-06-01 \
  --end 2024-06-15 \
  --out-dir data/raw/sentinel2
```

For a credential smoke test, limit the run:

```bash
python3 -m bloomcast.data.cli sentinel2 \
  --targets-csv data/processed/lake_targets.csv \
  --start 2024-06-01 \
  --end 2024-06-15 \
  --limit 1
```

Verify the three sampled lakes on specific Sentinel-2 pass dates. Repeat `--pass-date` for every acquisition date you want to confirm:

```bash
python3 -m bloomcast.data.cli sentinel2 \
  --targets-csv data/processed/lake_targets.csv \
  --out-dir data/raw/sentinel2_sampled \
  --lake "Lake Hopatcong" \
  --lake "Round Valley Reservoir" \
  --lake "Budd Lake" \
  --pass-date 2026-07-11
```

Pass-date mode uses a one-day UTC acquisition window for each date and writes one manifest row per lake-date pair. Successful downloads are validated before they are written to the manifest: one image must be returned, it must have the expected 7 bands, `dataMask` must contain valid pixels, and the spectral bands must be nonblank over those valid pixels.

For a credential-free planning check, use `--dry-run`. This writes a manifest with each planned lake output directory, bounding box, and estimated raster size:

```bash
python3 -m bloomcast.data.cli sentinel2 \
  --targets-csv data/processed/lake_targets.csv \
  --start 2024-06-01 \
  --end 2024-06-15 \
  --dry-run
```

Each Sentinel request uses a WGS84 bounding box around the lake centroid, a default 1.5 km buffer, 10 m resolution, least-cloud mosaicking, and a 7-band GeoTIFF response: B02, B03, B04, B08, B11, SCL, and dataMask.
