from __future__ import annotations

import csv
import math
import os
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable, Optional

from .lakes import LakeTarget


DEFAULT_EVALSCRIPT = """
//VERSION=3
function setup() {
  return {
    input: [{
      bands: ["B02", "B03", "B04", "B08", "B11", "SCL", "dataMask"],
      units: "DN"
    }],
    output: {
      bands: 7,
      sampleType: "UINT16"
    }
  };
}

function evaluatePixel(sample) {
  return [sample.B02, sample.B03, sample.B04, sample.B08, sample.B11, sample.SCL, sample.dataMask];
}
""".strip()


@dataclass(frozen=True)
class Sentinel2RequestResult:
    lake: str
    slug: str
    start: str
    end: str
    output_dir: Path
    image_count: int
    pass_date: str = ""
    width: int = 0
    height: int = 0
    bands: int = 0
    valid_data_pixels: int = 0
    skipped: bool = False
    message: str = ""


def sentinelhub_config():
    try:
        from sentinelhub import SHConfig
    except ImportError as exc:
        raise RuntimeError("Install sentinelhub-py to download Sentinel-2 imagery: pip install -r requirements.txt") from exc

    config = SHConfig(use_defaults=True)
    client_id = os.getenv("SH_CLIENT_ID")
    client_secret = os.getenv("SH_CLIENT_SECRET")
    base_url = os.getenv("SH_BASE_URL")
    token_url = os.getenv("SH_TOKEN_URL")

    if client_id:
        config.sh_client_id = client_id
    if client_secret:
        config.sh_client_secret = client_secret
    if base_url:
        config.sh_base_url = base_url
    if token_url:
        config.sh_token_url = token_url

    if not config.sh_client_id or not config.sh_client_secret:
        raise RuntimeError("Set SH_CLIENT_ID and SH_CLIENT_SECRET for Sentinel Hub OAuth credentials.")
    return config


def download_sentinel2_batch(
    targets: Iterable[LakeTarget],
    start: str,
    end: str,
    out_dir: Path | str,
    buffer_km: float = 1.5,
    resolution_m: int = 10,
    max_cloud_cover: float = 0.4,
    limit: Optional[int] = None,
    config=None,
    dry_run: bool = False,
) -> list[Sentinel2RequestResult]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if not dry_run:
        config = config or sentinelhub_config()

    results: list[Sentinel2RequestResult] = []
    for index, target in enumerate(targets):
        if limit is not None and index >= limit:
            break
        if not target.has_coordinates:
            results.append(
                Sentinel2RequestResult(
                    lake=target.name,
                    slug=target.slug,
                    start=start,
                    end=end,
                    output_dir=out_dir / target.slug,
                    image_count=0,
                    skipped=True,
                    message="Missing target coordinates.",
                )
            )
            continue

        if dry_run:
            results.append(plan_sentinel2_target(target, start, end, out_dir, buffer_km, resolution_m))
        else:
            results.append(
                download_sentinel2_target(
                    target=target,
                    start=start,
                    end=end,
                    out_dir=out_dir,
                    buffer_km=buffer_km,
                    resolution_m=resolution_m,
                    max_cloud_cover=max_cloud_cover,
                    config=config,
                )
            )

    write_manifest(results, out_dir / "manifest.csv")
    return results


def download_sentinel2_pass_dates(
    targets: Iterable[LakeTarget],
    pass_dates: Iterable[str],
    out_dir: Path | str,
    buffer_km: float = 1.5,
    resolution_m: int = 10,
    max_cloud_cover: float = 0.4,
    config=None,
    dry_run: bool = False,
) -> list[Sentinel2RequestResult]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    targets = list(targets)
    dates = [normalize_pass_date(pass_date) for pass_date in pass_dates]
    if not dates:
        raise ValueError("At least one Sentinel-2 pass date is required.")

    if not dry_run:
        config = config or sentinelhub_config()

    results: list[Sentinel2RequestResult] = []
    for target in targets:
        for pass_date in dates:
            start, end = pass_date_interval(pass_date)
            if not target.has_coordinates:
                results.append(
                    Sentinel2RequestResult(
                        lake=target.name,
                        slug=target.slug,
                        start=start,
                        end=end,
                        output_dir=out_dir / target.slug / pass_date,
                        image_count=0,
                        pass_date=pass_date,
                        skipped=True,
                        message="Missing target coordinates.",
                    )
                )
                continue

            if dry_run:
                results.append(
                    plan_sentinel2_target(
                        target=target,
                        start=start,
                        end=end,
                        out_dir=out_dir,
                        buffer_km=buffer_km,
                        resolution_m=resolution_m,
                        pass_date=pass_date,
                    )
                )
            else:
                results.append(
                    download_sentinel2_target(
                        target=target,
                        start=start,
                        end=end,
                        out_dir=out_dir,
                        buffer_km=buffer_km,
                        resolution_m=resolution_m,
                        max_cloud_cover=max_cloud_cover,
                        config=config,
                        pass_date=pass_date,
                    )
                )

    write_manifest(results, out_dir / "manifest.csv")
    return results


def plan_sentinel2_target(
    target: LakeTarget,
    start: str,
    end: str,
    out_dir: Path | str,
    buffer_km: float = 1.5,
    resolution_m: int = 10,
    pass_date: str = "",
) -> Sentinel2RequestResult:
    bbox = target.bbox(buffer_km)
    width, height = estimate_bbox_dimensions(target.latitude, bbox, resolution_m)
    output_label = pass_date or f"{start}_{end}"
    message = (
        "Dry run only; "
        f"bbox={_format_bbox(bbox)}, estimated_size={width}x{height}px, resolution={resolution_m}m."
    )
    return Sentinel2RequestResult(
        lake=target.name,
        slug=target.slug,
        start=start,
        end=end,
        output_dir=Path(out_dir) / target.slug / output_label,
        image_count=0,
        pass_date=pass_date,
        width=width,
        height=height,
        bands=7,
        skipped=False,
        message=message,
    )


def estimate_bbox_dimensions(
    latitude: Optional[float],
    bbox: tuple[float, float, float, float],
    resolution_m: int,
) -> tuple[int, int]:
    west, south, east, north = bbox
    center_latitude = float(latitude if latitude is not None else (south + north) / 2)
    width_m = abs(east - west) * 111_320 * max(math.cos(math.radians(center_latitude)), 0.01)
    height_m = abs(north - south) * 111_320
    return max(1, math.ceil(width_m / resolution_m)), max(1, math.ceil(height_m / resolution_m))


def download_sentinel2_target(
    target: LakeTarget,
    start: str,
    end: str,
    out_dir: Path | str,
    buffer_km: float = 1.5,
    resolution_m: int = 10,
    max_cloud_cover: float = 0.4,
    config=None,
    pass_date: str = "",
) -> Sentinel2RequestResult:
    config = config or sentinelhub_config()
    output_label = pass_date or f"{start}_{end}"
    target_dir = Path(out_dir) / target.slug / output_label
    target_dir.mkdir(parents=True, exist_ok=True)

    request = build_sentinel2_request(
        target=target,
        start=start,
        end=end,
        target_dir=target_dir,
        buffer_km=buffer_km,
        resolution_m=resolution_m,
        max_cloud_cover=max_cloud_cover,
        config=config,
    )
    images = request.get_data(save_data=True)
    summary = validate_sentinel2_images(images)
    return Sentinel2RequestResult(
        lake=target.name,
        slug=target.slug,
        start=start,
        end=end,
        output_dir=target_dir,
        image_count=len(images),
        pass_date=pass_date,
        width=summary["width"],
        height=summary["height"],
        bands=summary["bands"],
        valid_data_pixels=summary["valid_data_pixels"],
        message=(
            f"Saved Sentinel Hub response under {target_dir}; "
            f"{summary['width']}x{summary['height']}px, {summary['bands']} bands, "
            f"{summary['valid_data_pixels']} valid data pixels."
        ),
    )


def build_sentinel2_request(
    target: LakeTarget,
    start: str,
    end: str,
    target_dir: Path | str,
    buffer_km: float = 1.5,
    resolution_m: int = 10,
    max_cloud_cover: float = 0.4,
    config=None,
):
    try:
        from sentinelhub import (
            BBox,
            CRS,
            DataCollection,
            MimeType,
            MosaickingOrder,
            SentinelHubRequest,
            bbox_to_dimensions,
        )
    except ImportError as exc:
        raise RuntimeError("Install sentinelhub-py to download Sentinel-2 imagery: pip install -r requirements.txt") from exc

    bbox = BBox(bbox=target.bbox(buffer_km), crs=CRS.WGS84)
    size = bbox_to_dimensions(bbox, resolution=resolution_m)
    return SentinelHubRequest(
        evalscript=DEFAULT_EVALSCRIPT,
        input_data=[
            SentinelHubRequest.input_data(
                data_collection=DataCollection.SENTINEL2_L2A,
                time_interval=(start, end),
                maxcc=max_cloud_cover,
                mosaicking_order=MosaickingOrder.LEAST_CC,
            )
        ],
        responses=[SentinelHubRequest.output_response("default", MimeType.TIFF)],
        bbox=bbox,
        size=size,
        data_folder=str(target_dir),
        config=config,
    )


def write_manifest(results: Iterable[Sentinel2RequestResult], path: Path | str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "lake",
                "slug",
                "pass_date",
                "start",
                "end",
                "output_dir",
                "image_count",
                "width",
                "height",
                "bands",
                "valid_data_pixels",
                "skipped",
                "message",
            ],
        )
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "lake": result.lake,
                    "slug": result.slug,
                    "pass_date": result.pass_date,
                    "start": result.start,
                    "end": result.end,
                    "output_dir": result.output_dir,
                    "image_count": result.image_count,
                    "width": result.width,
                    "height": result.height,
                    "bands": result.bands,
                    "valid_data_pixels": result.valid_data_pixels,
                    "skipped": result.skipped,
                    "message": result.message,
                }
            )


def normalize_pass_date(value: str) -> str:
    return date.fromisoformat(value).isoformat()


def pass_date_interval(pass_date: str) -> tuple[str, str]:
    start_date = date.fromisoformat(pass_date)
    end_date = start_date + timedelta(days=1)
    return f"{start_date.isoformat()}T00:00:00Z", f"{end_date.isoformat()}T00:00:00Z"


def validate_sentinel2_images(images, expected_bands: int = 7) -> dict[str, int]:
    if not images:
        raise RuntimeError("Sentinel Hub returned no images.")

    try:
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("Install numpy to validate Sentinel-2 imagery: pip install -r requirements.txt") from exc

    image = np.asarray(images[0])
    if image.ndim != 3:
        raise RuntimeError(f"Expected Sentinel-2 image shape (height, width, bands), got {image.shape}.")

    height, width, bands = image.shape
    if bands != expected_bands:
        raise RuntimeError(f"Expected {expected_bands} Sentinel-2 bands, got {bands}.")

    if not np.isfinite(image).all():
        raise RuntimeError("Sentinel-2 image contains non-finite values.")

    data_mask = image[:, :, expected_bands - 1] > 0
    valid_data_pixels = int(np.count_nonzero(data_mask))
    if valid_data_pixels == 0:
        raise RuntimeError("Sentinel-2 image has no valid pixels according to dataMask.")

    spectral_bands = image[:, :, :5]
    if int(np.count_nonzero(spectral_bands[data_mask])) == 0:
        raise RuntimeError("Sentinel-2 image spectral bands are blank over valid pixels.")

    return {
        "width": int(width),
        "height": int(height),
        "bands": int(bands),
        "valid_data_pixels": valid_data_pixels,
    }


def _format_bbox(bbox: tuple[float, float, float, float]) -> str:
    return ",".join(f"{value:.6f}" for value in bbox)
