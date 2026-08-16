from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class BBox:
    west: float
    south: float
    east: float
    north: float

    def validate(self) -> "BBox":
        if not (-180 <= self.west <= 180 and -180 <= self.east <= 180):
            raise ValueError("Longitude must be in [-180, 180]")
        if not (-85.05112878 <= self.south <= 85.05112878 and -85.05112878 <= self.north <= 85.05112878):
            raise ValueError("Latitude must be inside Web Mercator limits")
        if self.south >= self.north:
            raise ValueError("south must be < north")
        if self.west >= self.east:
            raise ValueError("This prototype does not support antimeridian-crossing bboxes")
        return self

    def as_list(self) -> list[float]:
        return [self.west, self.south, self.east, self.north]


def lonlat_to_tile(lon: float, lat: float, z: int) -> tuple[int, int]:
    lat = max(min(lat, 85.05112878), -85.05112878)
    n = 2**z
    x = int((lon + 180.0) / 360.0 * n)
    lat_rad = math.radians(lat)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return min(max(x, 0), n - 1), min(max(y, 0), n - 1)


def tile_bounds(z: int, x: int, y: int) -> BBox:
    n = 2**z
    west = x / n * 360.0 - 180.0
    east = (x + 1) / n * 360.0 - 180.0

    def tile_y_to_lat(yy: int) -> float:
        return math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * yy / n))))

    north = tile_y_to_lat(y)
    south = tile_y_to_lat(y + 1)
    return BBox(west, south, east, north)


def tiles_for_bbox(bbox: BBox, z: int) -> list[tuple[int, int, int]]:
    bbox.validate()
    x0, y0 = lonlat_to_tile(bbox.west, bbox.north, z)
    x1, y1 = lonlat_to_tile(bbox.east, bbox.south, z)
    return [(z, x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]


def intersects(a: BBox, b: BBox) -> bool:
    return not (a.east <= b.west or a.west >= b.east or a.north <= b.south or a.south >= b.north)
