"""Tests for z14 coverage rasterization."""

from __future__ import annotations

import numpy as np
import rasterio
from rio_cogeo.cogeo import cog_validate
from shapely.geometry import LineString, Point

from coverage_acquisition.rasterize import GRID_SIZE, PIXEL_SIZE, rasterize_geometries_to_cog


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
