from __future__ import annotations

import csv
import math
import os
from dataclasses import dataclass
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
    skipped: bool = False
    message: str = ""


def sentinelhub_config():
    try:
        from sentinelhub import SHConfig
    except ImportError as exc:
        raise RuntimeError("Install sentinelhub-py to download Sentinel-2 imagery: pip install -r requirements.txt") from exc

    config = SHConfig()
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


def plan_sentinel2_target(
    target: LakeTarget,
    start: str,
    end: str,
    out_dir: Path | str,
    buffer_km: float = 1.5,
    resolution_m: int = 10,
) -> Sentinel2RequestResult:
    bbox = target.bbox(buffer_km)
    width, height = estimate_bbox_dimensions(target.latitude, bbox, resolution_m)
    message = (
        "Dry run only; "
        f"bbox={_format_bbox(bbox)}, estimated_size={width}x{height}px, resolution={resolution_m}m."
    )
    return Sentinel2RequestResult(
        lake=target.name,
        slug=target.slug,
        start=start,
        end=end,
        output_dir=Path(out_dir) / target.slug / f"{start}_{end}",
        image_count=0,
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
) -> Sentinel2RequestResult:
    config = config or sentinelhub_config()
    target_dir = Path(out_dir) / target.slug / f"{start}_{end}"
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
    return Sentinel2RequestResult(
        lake=target.name,
        slug=target.slug,
        start=start,
        end=end,
        output_dir=target_dir,
        image_count=len(images),
        message=f"Saved Sentinel Hub response under {target_dir}.",
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
            fieldnames=["lake", "slug", "start", "end", "output_dir", "image_count", "skipped", "message"],
        )
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "lake": result.lake,
                    "slug": result.slug,
                    "start": result.start,
                    "end": result.end,
                    "output_dir": result.output_dir,
                    "image_count": result.image_count,
                    "skipped": result.skipped,
                    "message": result.message,
                }
            )


def _format_bbox(bbox: tuple[float, float, float, float]) -> str:
    return ",".join(f"{value:.6f}" for value in bbox)
