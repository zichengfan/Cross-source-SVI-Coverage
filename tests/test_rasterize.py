"""Tests for z14 coverage rasterization."""

from __future__ import annotations

import numpy as np
import rasterio
from PIL import Image
from pyproj import Transformer
from rio_cogeo.cogeo import cog_validate
from shapely.geometry import LineString, Point

from coverage_acquisition.rasterize import (
    GRID_SIZE,
    ORIGIN_X,
    ORIGIN_Y,
    PIXEL_SIZE,
    WEB_MERCATOR_HALF_WORLD,
    _tile_bounds_3857,
    lonlat_window,
    rasterize_geometries_to_cog,
    rasterize_raster_tiles_to_cog,
)


def test_z14_grid_constants() -> None:
    assert GRID_SIZE == 4_194_304
    assert PIXEL_SIZE == 9.554628535647032


def test_rasterize_linestring_to_valid_cog(tmp_path) -> None:
    output_path = tmp_path / "line.tif"
    manifest = rasterize_geometries_to_cog(
        [LineString([(-73.98570, 40.74835), (-73.98520, 40.74875)])],
        output_path,
    )

    assert output_path.exists()
    assert cog_validate(output_path)[0] is True
    assert manifest["covered_pixel_count"] > 0
    assert manifest["crs"] == "EPSG:3857"


def test_rasterize_point_buffers_to_at_least_one_pixel(tmp_path) -> None:
    output_path = tmp_path / "point.tif"
    manifest = rasterize_geometries_to_cog([Point(-73.98570, 40.74835)], output_path, point_buffer_cells=1.0)

    assert manifest["covered_pixel_count"] >= 1


def test_rasterize_output_dtype_and_nodata(tmp_path) -> None:
    output_path = tmp_path / "dtype.tif"
    rasterize_geometries_to_cog([Point(-73.98570, 40.74835)], output_path)

    with rasterio.open(output_path) as dataset:
        assert dataset.dtypes == ("uint8",)
        assert dataset.nodata == 255


def test_rasterize_disjoint_geometries_produce_separated_regions(tmp_path) -> None:
    output_path = tmp_path / "disjoint.tif"
    rasterize_geometries_to_cog(
        [
            LineString([(-73.9900, 40.7480), (-73.9898, 40.7482)]),
            LineString([(-73.9840, 40.7480), (-73.9838, 40.7482)]),
        ],
        output_path,
    )

    with rasterio.open(output_path) as dataset:
        covered = np.argwhere(dataset.read(1) == 1)

    assert covered.size > 0
    assert covered[:, 1].max() - covered[:, 1].min() > 20


def test_tile_bounds_3857_web_mercator_matches_existing_xyz_math() -> None:
    assert _tile_bounds_3857(0, 0, 0) == (
        -WEB_MERCATOR_HALF_WORLD,
        -WEB_MERCATOR_HALF_WORLD,
        WEB_MERCATOR_HALF_WORLD,
        WEB_MERCATOR_HALF_WORLD,
    )

    z, x, y = 14, 12_054, 6_162
    span = 2 * WEB_MERCATOR_HALF_WORLD / 2**z
    assert _tile_bounds_3857(z, x, y) == (
        ORIGIN_X + x * span,
        ORIGIN_Y - y * span - span,
        ORIGIN_X + x * span + span,
        ORIGIN_Y - y * span,
    )


def test_tile_bounds_3857_kakao_epsg5181_contains_projected_seoul_city_hall() -> None:
    minx, miny, maxx, maxy = _tile_bounds_3857(7, 55, 124, coordinate_scheme="kakao_epsg5181")
    seoul_x, seoul_y = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True).transform(126.9779, 37.5663)

    assert minx <= seoul_x <= maxx
    assert miny <= seoul_y <= maxy


def test_rasterize_raster_tiles_to_cog_places_kakao_epsg5181_tile_coverage_near_seoul(tmp_path) -> None:
    png_path = tmp_path / "kakao.png"
    output_path = tmp_path / "kakao.tif"

    tile_size = 256
    tile_span = tile_size * 16.0
    x_min_m = -30000.0 + 55 * tile_span
    y_max_m = -60000.0 + (124 + 1) * tile_span
    seoul_x_m, seoul_y_m = Transformer.from_crs("EPSG:4326", "EPSG:5181", always_xy=True).transform(126.9779, 37.5663)
    seoul_col = round((seoul_x_m - x_min_m) / tile_span * tile_size)
    seoul_row = round((y_max_m - seoul_y_m) / tile_span * tile_size)

    rgba = np.zeros((tile_size, tile_size, 4), dtype=np.uint8)
    rgba[seoul_row - 3 : seoul_row + 4, seoul_col - 3 : seoul_col + 4] = (12, 34, 56, 255)
    Image.fromarray(rgba, mode="RGBA").save(png_path)

    manifest = rasterize_raster_tiles_to_cog(
        [(7, 55, 124, png_path)],
        output_path,
        coordinate_scheme="kakao_epsg5181",
    )

    assert output_path.exists()
    assert cog_validate(output_path)[0] is True
    assert manifest["crs"] == "EPSG:3857"
    assert manifest["covered_pixel_count"] > 0
    with rasterio.open(output_path) as dataset:
        assert dataset.dtypes == ("uint8",)
        transform = dataset.transform
        covered_rows_cols = np.argwhere(dataset.read(1) == 1)

    seoul_col_min, seoul_row_min, seoul_col_max, seoul_row_max = lonlat_window((126.96, 37.55, 126.99, 37.58))
    covered_cols = covered_rows_cols[:, 1] + round((transform.c - ORIGIN_X) / PIXEL_SIZE)
    covered_rows = covered_rows_cols[:, 0] + round((ORIGIN_Y - transform.f) / PIXEL_SIZE)
    assert covered_cols.min() >= seoul_col_min
    assert covered_cols.max() < seoul_col_max
    assert covered_rows.min() >= seoul_row_min
    assert covered_rows.max() < seoul_row_max
