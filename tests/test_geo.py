"""Tests for coordinate / tile math."""

from __future__ import annotations

from coverage_acquisition.geo import (
    baidu_out_of_china,
    bbox_to_tile_range,
    lonlat_to_tile,
    tile_range_for_bbox,
    tile_to_lonlat_bounds,
    tile_to_lonlat_bounds_for_scheme,
    yandex_elliptic_mercator_lat_to_y_fraction,
    yandex_elliptic_mercator_y_fraction_to_lat,
)
from coverage_acquisition.models import BoundingBox


def test_lonlat_to_tile_origin():
    # (0, 0) at zoom 1 sits at the centre of the 2x2 grid -> tile (1, 1).
    assert lonlat_to_tile(0.0, 0.0, 1) == (1, 1)


def test_tile_to_lonlat_bounds_round_trip():
    lon, lat = 4.9, 52.37
    zoom = 14
    x, y = lonlat_to_tile(lon, lat, zoom)
    lon_min, lat_min, lon_max, lat_max = tile_to_lonlat_bounds(x, y, zoom)
    assert lon_min <= lon <= lon_max
    assert lat_min <= lat <= lat_max


def test_bbox_to_tile_range_is_ordered():
    bbox = BoundingBox(min_lon=4.8, min_lat=52.3, max_lon=5.0, max_lat=52.4)
    tile_range = bbox_to_tile_range(bbox, 14)
    assert tile_range.x_min <= tile_range.x_max
    assert tile_range.y_min <= tile_range.y_max
    assert tile_range.count >= 1


def test_yandex_elliptic_mercator_round_trip():
    for lat in (-60.0, -10.0, 0.0, 35.5, 55.75, 70.0):
        fraction = yandex_elliptic_mercator_lat_to_y_fraction(lat)
        recovered = yandex_elliptic_mercator_y_fraction_to_lat(fraction)
        assert abs(recovered - lat) < 1e-6


def test_baidu_out_of_china():
    assert baidu_out_of_china(-100.0, 40.0) is True   # USA
    assert baidu_out_of_china(116.4, 39.9) is False   # Beijing


def test_tile_range_for_bbox_dispatches_by_scheme():
    bbox = BoundingBox(min_lon=37.5, min_lat=55.7, max_lon=37.6, max_lat=55.8)
    web = tile_range_for_bbox(bbox, 12, "web_mercator")
    yandex = tile_range_for_bbox(bbox, 12, "yandex_wgs84_mercator")
    # Both schemes return a usable range; Yandex's elliptic grid shifts y.
    assert web.count >= 1 and yandex.count >= 1


def test_kakao_epsg5181_known_seoul_city_hall_tile():
    bbox = BoundingBox(min_lon=126.9779, min_lat=37.5663, max_lon=126.9779, max_lat=37.5663)

    tile_range = tile_range_for_bbox(bbox, 7, "kakao_epsg5181")

    assert (tile_range.x_min, tile_range.y_min) == (55, 124)
    assert (tile_range.x_max, tile_range.y_max) == (55, 124)


def test_kakao_epsg5181_tile_bounds_contain_round_trip_point():
    lon, lat = 126.9779, 37.5663
    bbox = BoundingBox(min_lon=lon, min_lat=lat, max_lon=lon, max_lat=lat)
    tile_range = tile_range_for_bbox(bbox, 7, "kakao_epsg5181")

    lon_min, lat_min, lon_max, lat_max = tile_to_lonlat_bounds_for_scheme(
        tile_range.x_min,
        tile_range.y_min,
        7,
        "kakao_epsg5181",
    )

    assert lon_min <= lon <= lon_max
    assert lat_min <= lat <= lat_max
