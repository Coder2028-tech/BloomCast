from __future__ import annotations

import csv
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TARGET_LAKES = PROJECT_ROOT / "target_lakes.csv"
DEFAULT_STATIONS = PROJECT_ROOT / "station.csv"


@dataclass(frozen=True)
class LakeTarget:
    name: str
    slug: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    match_count: int = 0
    match_score: int = 0
    source: str = ""
    notes: str = ""

    @property
    def has_coordinates(self) -> bool:
        return self.latitude is not None and self.longitude is not None

    def bbox(self, buffer_km: float) -> tuple[float, float, float, float]:
        if not self.has_coordinates:
            raise ValueError(f"{self.name} does not have coordinates")

        latitude = float(self.latitude)
        longitude = float(self.longitude)
        lat_delta = buffer_km / 111.32
        lon_delta = buffer_km / (111.32 * max(math.cos(math.radians(latitude)), 0.01))
        return (
            longitude - lon_delta,
            latitude - lat_delta,
            longitude + lon_delta,
            latitude + lat_delta,
        )


@dataclass(frozen=True)
class StationPoint:
    name: str
    latitude: float
    longitude: float
    identifier: str


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "lake"


def normalize_name(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", value.lower())).strip()


def load_lake_names(path: Path | str = DEFAULT_TARGET_LAKES) -> List[str]:
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines:
        return []
    if "|" in lines[0]:
        return _load_markdown_table_names(text)

    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        rows = list(reader)

    if not rows:
        return []

    first_row = [cell.strip() for cell in rows[0]]
    start_index = 1 if first_row and "lake" in first_row[0].lower() else 0
    return [row[0].strip() for row in rows[start_index:] if row and row[0].strip()]


def _load_markdown_table_names(text: str) -> List[str]:
    names: List[str] = []
    for line in text.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not cells or not cells[0] or set(cells[0]) <= {"-"}:
            continue
        if cells[0].lower() in {"candidate lake", "lake", "name"}:
            continue
        names.append(cells[0])
    return names


def load_station_points(path: Path | str = DEFAULT_STATIONS) -> List[StationPoint]:
    path = Path(path)
    points: List[StationPoint] = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            latitude = _parse_float(row.get("LatitudeMeasure"))
            longitude = _parse_float(row.get("LongitudeMeasure"))
            name = (row.get("MonitoringLocationName") or "").strip()
            if latitude is None or longitude is None or not name:
                continue
            points.append(
                StationPoint(
                    name=name,
                    latitude=latitude,
                    longitude=longitude,
                    identifier=(row.get("MonitoringLocationIdentifier") or "").strip(),
                )
            )
    return points


def build_lake_targets(
    lake_names: Sequence[str],
    station_points: Sequence[StationPoint],
) -> List[LakeTarget]:
    targets: List[LakeTarget] = []
    for lake_name in lake_names:
        matches, best_score, notes = _select_station_matches(lake_name, station_points)
        if not matches:
            targets.append(
                LakeTarget(
                    name=lake_name,
                    slug=slugify(lake_name),
                    notes=notes,
                )
            )
            continue

        latitude = sum(point.latitude for point in matches) / len(matches)
        longitude = sum(point.longitude for point in matches) / len(matches)
        targets.append(
            LakeTarget(
                name=lake_name,
                slug=slugify(lake_name),
                latitude=latitude,
                longitude=longitude,
                match_count=len(matches),
                match_score=best_score,
                source="station.csv",
                notes=notes,
            )
        )
    return targets


def load_or_build_targets(
    target_lakes_path: Path | str = DEFAULT_TARGET_LAKES,
    stations_path: Path | str = DEFAULT_STATIONS,
    target_csv_path: Optional[Path | str] = None,
) -> List[LakeTarget]:
    if target_csv_path:
        csv_path = Path(target_csv_path)
        if csv_path.exists():
            return load_targets_csv(csv_path)

    lake_names = load_lake_names(target_lakes_path)
    station_points = load_station_points(stations_path)
    return build_lake_targets(lake_names, station_points)


def load_targets_csv(path: Path | str) -> List[LakeTarget]:
    targets: List[LakeTarget] = []
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            name = (row.get("name") or row.get("lake") or "").strip()
            if not name:
                continue
            targets.append(
                LakeTarget(
                    name=name,
                    slug=(row.get("slug") or slugify(name)).strip(),
                    latitude=_parse_float(row.get("latitude")),
                    longitude=_parse_float(row.get("longitude")),
                    match_count=int(row.get("match_count") or 0),
                    match_score=int(row.get("match_score") or 0),
                    source=(row.get("source") or "").strip(),
                    notes=(row.get("notes") or "").strip(),
                )
            )
    return targets


def write_targets_csv(targets: Iterable[LakeTarget], path: Path | str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "name",
                "slug",
                "latitude",
                "longitude",
                "match_count",
                "match_score",
                "source",
                "notes",
            ],
        )
        writer.writeheader()
        for target in targets:
            writer.writerow(
                {
                    "name": target.name,
                    "slug": target.slug,
                    "latitude": "" if target.latitude is None else f"{target.latitude:.8f}",
                    "longitude": "" if target.longitude is None else f"{target.longitude:.8f}",
                    "match_count": target.match_count,
                    "match_score": target.match_score,
                    "source": target.source,
                    "notes": target.notes,
                }
            )


def _select_station_matches(
    lake_name: str,
    station_points: Sequence[StationPoint],
    max_cluster_span_km: float = 8.0,
) -> tuple[List[StationPoint], int, str]:
    groups: dict[int, List[StationPoint]] = {}
    for point in station_points:
        score = _station_match_score(lake_name, point)
        if score > 0:
            groups.setdefault(score, []).append(point)

    if not groups:
        return [], 0, "No matching station coordinate found."

    ambiguity_note = ""
    for score in sorted(groups, reverse=True):
        points = groups[score]
        clusters = _station_clusters(points, max_cluster_span_km)
        ranked = sorted(clusters, key=lambda cluster: (-len(cluster), _cluster_span_km(cluster)))
        best_cluster = ranked[0]
        same_size_clusters = [cluster for cluster in ranked if len(cluster) == len(best_cluster)]

        if len(points) == len(best_cluster):
            return best_cluster, score, f"Centroid from {len(best_cluster)} station match(es)."

        if len(best_cluster) > 1 and len(same_size_clusters) == 1:
            return (
                best_cluster,
                score,
                f"Centroid from {len(best_cluster)} station match(es); excluded distant same-name station(s).",
            )

        ambiguity_note = (
            f"Ambiguous station matches at score {score}; "
            f"{len(points)} match(es) split into {len(clusters)} distant cluster(s)."
        )

    return [], 0, ambiguity_note or "Ambiguous station coordinate matches; review manually."


def _station_clusters(points: Sequence[StationPoint], max_distance_km: float) -> List[List[StationPoint]]:
    remaining = set(range(len(points)))
    clusters: List[List[StationPoint]] = []

    while remaining:
        seed = remaining.pop()
        component = {seed}
        frontier = [seed]
        while frontier:
            current = frontier.pop()
            neighbors = [
                candidate
                for candidate in list(remaining)
                if _haversine_km(points[current], points[candidate]) <= max_distance_km
            ]
            for neighbor in neighbors:
                remaining.remove(neighbor)
                component.add(neighbor)
                frontier.append(neighbor)
        clusters.append([points[index] for index in sorted(component)])

    return clusters


def _cluster_span_km(points: Sequence[StationPoint]) -> float:
    return max((_haversine_km(first, second) for first in points for second in points), default=0.0)


def _haversine_km(first: StationPoint, second: StationPoint) -> float:
    radius_km = 6371.0
    first_lat = math.radians(first.latitude)
    second_lat = math.radians(second.latitude)
    delta_lat = math.radians(second.latitude - first.latitude)
    delta_lon = math.radians(second.longitude - first.longitude)
    value = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(first_lat) * math.cos(second_lat) * math.sin(delta_lon / 2) ** 2
    )
    return 2 * radius_km * math.asin(math.sqrt(value))


def _station_match_score(lake_name: str, station_point: StationPoint) -> int:
    lake = normalize_name(lake_name)
    station = normalize_name(station_point.name)
    if station == lake:
        return 100
    if station.startswith(f"{lake} "):
        return 90
    if station.startswith(lake):
        return 85
    if f" {lake} " in f" {station} ":
        return 50
    return 0


def _parse_float(value: object) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None
