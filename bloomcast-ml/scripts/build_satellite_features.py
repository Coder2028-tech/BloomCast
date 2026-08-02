"""Build historical Sentinel-2 lake-date features without using future scenes."""
from __future__ import annotations

import argparse
import math
import os
import time
from datetime import timedelta
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd


EVALSCRIPT = """
//VERSION=3
function setup() {
  return {
    input: [{
      bands: ["B03", "B04", "B05", "B08", "SCL", "dataMask"],
      units: ["REFLECTANCE", "REFLECTANCE", "REFLECTANCE", "REFLECTANCE", "DN", "DN"]
    }],
    output: { bands: 6, sampleType: "FLOAT32" }
  };
}
function evaluatePixel(s) {
  return [s.B03, s.B04, s.B05, s.B08, s.SCL, s.dataMask];
}
""".strip()


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


def sentinelhub_config():
    from sentinelhub import SHConfig

    config = SHConfig(use_defaults=True)
    config.sh_client_id = os.getenv("SH_CLIENT_ID", config.sh_client_id)
    config.sh_client_secret = os.getenv("SH_CLIENT_SECRET", config.sh_client_secret)
    config.sh_base_url = os.getenv("SH_BASE_URL", "https://sh.dataspace.copernicus.eu")
    config.sh_token_url = os.getenv(
        "SH_TOKEN_URL",
        "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token",
    )
    if not config.sh_client_id or not config.sh_client_secret:
        raise RuntimeError("Set SH_CLIENT_ID and SH_CLIENT_SECRET in the local .env file.")
    return config


def data_collection(config):
    from sentinelhub import DataCollection

    standard = DataCollection.SENTINEL2_L2A
    if config.sh_base_url.rstrip("/") == standard.service_url.rstrip("/"):
        return standard
    try:
        return DataCollection["SENTINEL2_L2A_CDSE_BLOOMCAST"]
    except KeyError:
        return standard.define_from(
            "SENTINEL2_L2A_CDSE_BLOOMCAST", service_url=config.sh_base_url
        )


def lake_bbox(latitude: float, longitude: float, buffer_km: float) -> tuple[float, float, float, float]:
    lat_delta = buffer_km / 111.32
    lon_delta = buffer_km / (111.32 * max(math.cos(math.radians(latitude)), 0.01))
    return longitude - lon_delta, latitude - lat_delta, longitude + lon_delta, latitude + lat_delta


def find_scene(
    lake: str,
    feature_date: pd.Timestamp,
    latitude: float,
    longitude: float,
    lookback_days: int,
    max_cloud_cover: float,
    config,
) -> dict[str, Any] | None:
    from sentinelhub import BBox, CRS, SentinelHubCatalog

    catalog = SentinelHubCatalog(config=config)
    collection = data_collection(config)
    end = feature_date.normalize() + pd.Timedelta(hours=23, minutes=59, seconds=59)
    start = feature_date.normalize() - pd.Timedelta(days=lookback_days)
    search = catalog.search(
        collection,
        bbox=BBox(lake_bbox(latitude, longitude, 1.5), crs=CRS.WGS84),
        time=(start.to_pydatetime(), end.to_pydatetime()),
        filter=f"eo:cloud_cover <= {float(max_cloud_cover):g}",
        fields={
            "include": ["id", "properties.datetime", "properties.eo:cloud_cover"],
            "exclude": [],
        },
        limit=100,
    )
    candidates = []
    for item in search:
        acquired = pd.to_datetime(item.get("properties", {}).get("datetime"), utc=True).tz_localize(None)
        if acquired <= end:
            candidates.append((acquired, item))
    if not candidates:
        return None
    # Closest earlier acquisition; prefer less cloud if timestamps tie.
    candidates.sort(
        key=lambda pair: (
            pair[0],
            -float(pair[1].get("properties", {}).get("eo:cloud_cover") or 100),
        ),
        reverse=True,
    )
    acquired, item = candidates[0]
    return {
        "scene_id": item.get("id", ""),
        "satellite_date": acquired.normalize(),
        "acquired": acquired,
        "cloud_cover": item.get("properties", {}).get("eo:cloud_cover"),
    }


def fetch_scene_image(
    scene: dict[str, Any], latitude: float, longitude: float, buffer_km: float,
    resolution_m: int, config,
) -> np.ndarray:
    from sentinelhub import BBox, CRS, MimeType, MosaickingOrder, SentinelHubRequest, bbox_to_dimensions

    bbox = BBox(lake_bbox(latitude, longitude, buffer_km), crs=CRS.WGS84)
    size = bbox_to_dimensions(bbox, resolution=resolution_m)
    day = pd.Timestamp(scene["satellite_date"])
    request = SentinelHubRequest(
        evalscript=EVALSCRIPT,
        input_data=[SentinelHubRequest.input_data(
            data_collection=data_collection(config),
            time_interval=(day.date().isoformat(), (day + timedelta(days=1)).date().isoformat()),
            mosaicking_order=MosaickingOrder.LEAST_CC,
        )],
        responses=[SentinelHubRequest.output_response("default", MimeType.TIFF)],
        bbox=bbox,
        size=size,
        config=config,
    )
    images = request.get_data()
    if not images:
        raise RuntimeError("Sentinel Hub returned no image data for the selected scene date.")
    return np.asarray(images[0])


def summarize_image(image: np.ndarray) -> dict[str, float | int]:
    if image.ndim != 3 or image.shape[-1] != 6:
        raise ValueError(f"Expected HxWx6 Sentinel image, received shape {image.shape}")
    green, red, red_edge, nir, scl, data_mask = np.moveaxis(image.astype(float), -1, 0)
    water = (np.rint(scl) == 6) & (data_mask > 0)
    ndci_denominator = red_edge + red
    ndwi_denominator = green + nir
    valid = water & (np.abs(ndci_denominator) > 1e-12) & (np.abs(ndwi_denominator) > 1e-12)
    total = int(water.size)
    valid_pixels = int(valid.sum())
    if valid_pixels == 0:
        return {
            "ndci": np.nan, "ndwi": np.nan, "valid_pixels": 0,
            "total_pixels": total, "water_pixel_fraction": float(water.mean()),
        }
    ndci = (red_edge[valid] - red[valid]) / ndci_denominator[valid]
    ndwi = (green[valid] - nir[valid]) / ndwi_denominator[valid]
    return {
        "ndci": float(np.nanmean(ndci)), "ndwi": float(np.nanmean(ndwi)),
        "valid_pixels": valid_pixels, "total_pixels": total,
        "water_pixel_fraction": float(water.mean()),
    }


def build_features(
    required: pd.DataFrame,
    targets: pd.DataFrame,
    *,
    lookback_days: int = 14,
    max_cloud_cover: float = 40,
    buffer_km: float = 1.5,
    resolution_m: int = 10,
    config=None,
    scene_finder: Callable[..., dict[str, Any] | None] = find_scene,
    image_fetcher: Callable[..., np.ndarray] = fetch_scene_image,
    fail_fast: bool = False,
    request_delay: float = 0,
) -> pd.DataFrame:
    required = required.copy()
    required["date"] = pd.to_datetime(required["date"]).dt.normalize()
    coordinates = targets.set_index("name")[["latitude", "longitude"]].to_dict("index")
    rows = []
    for item in required[["lake", "date"]].drop_duplicates().itertuples(index=False):
        base = {"lake": item.lake, "date": item.date.date().isoformat()}
        coordinate = coordinates.get(item.lake)
        if not coordinate or pd.isna(coordinate["latitude"]) or pd.isna(coordinate["longitude"]):
            rows.append({**base, "status": "missing_coordinates", "message": "No lake coordinates."})
            continue
        latitude, longitude = float(coordinate["latitude"]), float(coordinate["longitude"])
        try:
            scene = scene_finder(
                item.lake, item.date, latitude, longitude, lookback_days,
                max_cloud_cover, config,
            )
            if scene is None:
                rows.append({**base, "status": "no_scene", "message": "No earlier scene in lookback window."})
                continue
            image = image_fetcher(scene, latitude, longitude, buffer_km, resolution_m, config)
            summary = summarize_image(image)
            status = "ok" if summary["valid_pixels"] else "no_valid_water_pixels"
            rows.append({
                **base,
                "satellite_date": pd.Timestamp(scene["satellite_date"]).date().isoformat(),
                "scene_id": scene.get("scene_id", ""),
                "cloud_cover": scene.get("cloud_cover"),
                **summary,
                "status": status,
                "message": "" if status == "ok" else "Scene contained no valid water pixels.",
            })
            if request_delay:
                time.sleep(request_delay)
        except Exception as exc:
            if fail_fast:
                raise
            rows.append({**base, "status": "error", "message": str(exc)})
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--required-dates", default="data/satellite_required_dates.csv")
    parser.add_argument("--targets", default="data/lake_targets.csv")
    parser.add_argument("--out", default="data/satellite_features.csv")
    parser.add_argument("--env", default="../.env")
    parser.add_argument("--lookback-days", type=int, default=14)
    parser.add_argument("--max-cloud-cover", type=float, default=40)
    parser.add_argument("--buffer-km", type=float, default=1.5)
    parser.add_argument("--resolution-m", type=int, default=10)
    parser.add_argument("--request-delay", type=float, default=0.2)
    parser.add_argument("--fail-fast", action="store_true")
    args = parser.parse_args()
    load_env(args.env)
    config = sentinelhub_config()
    result = build_features(
        pd.read_csv(args.required_dates), pd.read_csv(args.targets),
        lookback_days=args.lookback_days, max_cloud_cover=args.max_cloud_cover,
        buffer_km=args.buffer_km, resolution_m=args.resolution_m,
        config=config, fail_fast=args.fail_fast, request_delay=args.request_delay,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(out, index=False)
    print(f"Wrote {len(result)} lake-date satellite rows to {out}")
    print(result["status"].value_counts(dropna=False).to_string())


if __name__ == "__main__":
    main()
