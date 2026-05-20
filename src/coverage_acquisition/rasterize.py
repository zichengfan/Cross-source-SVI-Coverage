"""Rasterize provider coverage onto the shared z14 Web Mercator grid."""

from __future__ import annotations

import math
import tempfile
from pathlib import Path
from typing import Iterable

import numpy as np
import rasterio
from PIL import Image
from pyproj import CRS as PyprojCRS
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.features import rasterize
from rasterio.transform import Affine, array_bounds, from_origin
from rasterio.warp import reproject
from rio_cogeo.cogeo import cog_translate, cog_validate
from rio_cogeo.profiles import cog_profiles
from shapely.geometry import MultiPoint, Point
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform, unary_union

GRID_ZOOM = 14
TILE_SIZE = 256
GRID_SIZE = TILE_SIZE * 2**GRID_ZOOM
WEB_MERCATOR_HALF_WORLD = 20037508.342789244
ORIGIN_X = -WEB_MERCATOR_HALF_WORLD
ORIGIN_Y = WEB_MERCATOR_HALF_WORLD
PIXEL_SIZE = 2 * WEB_MERCATOR_HALF_WORLD / GRID_SIZE
CRS = "EPSG:3857"
RASTERIO_CRS = PyprojCRS.from_epsg(3857).to_wkt()
NODATA = 255

_TO_WEB_MERCATOR = Transformer.from_crs("EPSG:4326", CRS, always_xy=True)
_TO_LONLAT = Transformer.from_crs(CRS, "EPSG:4326", always_xy=True)


def pixel_bounds_for_bbox(bbox: tuple[float, float, float, float]) -> tuple[int, int, int, int]:
    """Return inclusive-exclusive z14 pixel bounds for an EPSG:3857 bbox."""
    minx, miny, maxx, maxy = bbox
    col_min = math.floor((minx - ORIGIN_X) / PIXEL_SIZE)
    col_max = math.ceil((maxx - ORIGIN_X) / PIXEL_SIZE)
    row_min = math.floor((ORIGIN_Y - maxy) / PIXEL_SIZE)
    row_max = math.ceil((ORIGIN_Y - miny) / PIXEL_SIZE)
    return (
        max(0, min(GRID_SIZE, col_min)),
        max(0, min(GRID_SIZE, row_min)),
        max(0, min(GRID_SIZE, col_max)),
        max(0, min(GRID_SIZE, row_max)),
    )


def lonlat_window(bbox: tuple[float, float, float, float]) -> tuple[int, int, int, int]:
    """Return inclusive-exclusive z14 pixel bounds for an EPSG:4326 bbox."""
    minx, miny = _TO_WEB_MERCATOR.transform(bbox[0], bbox[1])
    maxx, maxy = _TO_WEB_MERCATOR.transform(bbox[2], bbox[3])
    return pixel_bounds_for_bbox(
        (min(minx, maxx), min(miny, maxy), max(minx, maxx), max(miny, maxy))
    )


def rasterize_geometries_to_cog(
    geometries: Iterable[BaseGeometry],
    output_path: str | Path,
    *,
    point_buffer_cells: float = 1.0,
) -> dict[str, object]:
    """Burn EPSG:4326 geometries into a single-band uint8 COG on the z14 grid."""
    projected = [
        _project_geometry(geometry, point_buffer_cells)
        for geometry in geometries
        if not geometry.is_empty
    ]
    if not projected:
        raise ValueError("At least one non-empty geometry is required.")

    union = unary_union(projected)
    col_min, row_min, col_max, row_max = pixel_bounds_for_bbox(union.bounds)
    if col_min >= col_max or row_min >= row_max:
        raise ValueError("Geometry extent does not intersect the z14 analysis grid.")

    transform_ = _window_transform(col_min, row_min)
    height = row_max - row_min
    width = col_max - col_min
    data = rasterize(
        [(geometry, 1) for geometry in projected],
        out_shape=(height, width),
        transform=transform_,
        fill=0,
        dtype="uint8",
    )
    return _write_cog(data, output_path, transform_)


def rasterize_raster_tiles_to_cog(
    tile_paths: Iterable[tuple[int, int, int, str | Path]],
    output_path: str | Path,
    *,
    coverage_from: str = "alpha",
) -> dict[str, object]:
    """Merge stored PNG coverage tiles into a single-band uint8 COG on the z14 grid."""
    tiles = list(tile_paths)
    if not tiles:
        raise ValueError("At least one raster tile is required.")

    bounds = [_tile_bounds_3857(z, x, y) for z, x, y, _path in tiles]
    union_bounds = (
        min(bound[0] for bound in bounds),
        min(bound[1] for bound in bounds),
        max(bound[2] for bound in bounds),
        max(bound[3] for bound in bounds),
    )
    col_min, row_min, col_max, row_max = pixel_bounds_for_bbox(union_bounds)
    if col_min >= col_max or row_min >= row_max:
        raise ValueError("Tile extent does not intersect the z14 analysis grid.")

    transform_ = _window_transform(col_min, row_min)
    data = np.zeros((row_max - row_min, col_max - col_min), dtype=np.uint8)

    for (z, x, y, path), bounds_ in zip(tiles, bounds, strict=True):
        mask = _coverage_mask_from_png(path, coverage_from)
        source_transform = from_origin(
            bounds_[0],
            bounds_[3],
            (bounds_[2] - bounds_[0]) / mask.shape[1],
            (bounds_[3] - bounds_[1]) / mask.shape[0],
        )
        reprojected = np.zeros_like(data)
        reproject(
            mask,
            reprojected,
            src_transform=source_transform,
            src_crs=RASTERIO_CRS,
            dst_transform=transform_,
            dst_crs=RASTERIO_CRS,
            resampling=Resampling.nearest,
        )
        data = np.maximum(data, reprojected)

    return _write_cog(data, output_path, transform_)


def _project_geometry(geometry: BaseGeometry, point_buffer_cells: float) -> BaseGeometry:
    projected = transform(_TO_WEB_MERCATOR.transform, geometry)
    if isinstance(projected, Point | MultiPoint):
        return projected.buffer(point_buffer_cells * PIXEL_SIZE)
    return projected


def _window_transform(col_min: int, row_min: int) -> Affine:
    return from_origin(
        ORIGIN_X + col_min * PIXEL_SIZE,
        ORIGIN_Y - row_min * PIXEL_SIZE,
        PIXEL_SIZE,
        PIXEL_SIZE,
    )


def _write_cog(data: np.ndarray, output_path: str | Path, transform_: Affine) -> dict[str, object]:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    profile = {
        "driver": "GTiff",
        "height": data.shape[0],
        "width": data.shape[1],
        "count": 1,
        "dtype": "uint8",
        "crs": RASTERIO_CRS,
        "transform": transform_,
        "nodata": NODATA,
    }
    with tempfile.NamedTemporaryFile(suffix=".tif") as temp:
        with rasterio.open(temp.name, "w", **profile) as dataset:
            dataset.write(data, 1)
        cog_translate(temp.name, output, cog_profiles.get("deflate"), in_memory=False, quiet=True)

    valid, errors, warnings = cog_validate(output)
    if not valid:
        raise RuntimeError(f"Generated GeoTIFF is not a valid COG: errors={errors}, warnings={warnings}")

    west, south, east, north = _lonlat_bounds(data.shape, transform_)
    covered = int(np.count_nonzero(data == 1))
    total = int(data.size)
    return {
        "output_path": str(output),
        "bbox": [west, south, east, north],
        "pixel_count": total,
        "checked_empty_pixel_count": total - covered,
        "covered_pixel_count": covered,
        "nodata_pixel_count": 0,
        "crs": CRS,
    }


def _lonlat_bounds(shape: tuple[int, int], transform_: Affine) -> tuple[float, float, float, float]:
    west, south, east, north = array_bounds(shape[0], shape[1], transform_)
    min_lon, min_lat = _TO_LONLAT.transform(west, south)
    max_lon, max_lat = _TO_LONLAT.transform(east, north)
    return min_lon, min_lat, max_lon, max_lat


def _tile_bounds_3857(z: int, x: int, y: int) -> tuple[float, float, float, float]:
    span = 2 * WEB_MERCATOR_HALF_WORLD / 2**z
    minx = ORIGIN_X + x * span
    maxx = minx + span
    maxy = ORIGIN_Y - y * span
    miny = maxy - span
    return minx, miny, maxx, maxy


def _coverage_mask_from_png(path: str | Path, coverage_from: str) -> np.ndarray:
    with Image.open(path) as image:
        rgba = np.asarray(image.convert("RGBA"))

    if coverage_from == "alpha":
        return (rgba[:, :, 3] != 0).astype(np.uint8)
    if coverage_from == "non-background":
        background = rgba[0, 0, :]
        return np.any(rgba != background, axis=2).astype(np.uint8)
    raise ValueError("coverage_from must be 'alpha' or 'non-background'.")
