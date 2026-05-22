"""Offline tests for Tencent mobile street-view foundation helpers."""

from __future__ import annotations

import zlib
from pathlib import Path

import pytest

from coverage_acquisition.geo import (
    BoundingBox,
    gcj02_to_wgs84,
    tencent_bl_tiles_for_gcj02_bbox,
    tencent_gcj02_to_pixel,
    tencent_pixel_to_gcj02,
    tencent_tile_size,
    wgs84_to_gcj02,
)
from coverage_acquisition.source_kinds import SOURCE_KIND_HANDLERS, get_source_kind_handler
from coverage_acquisition.source_kinds.tencent_mobile_street import (
    TXVN_HEADER_SIZE,
    parse_txvn_header,
    parse_txvn_tile,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "tencent"


@pytest.mark.parametrize(
    ("filename", "tile_index", "body_size"),
    [
        ("mobile_street_beijing_lv13_bl10_empty.bin", 10, 7),
        ("mobile_street_beijing_lv13_bl100.bin", 100, 98),
        ("mobile_street_beijing_lv13_bl200.bin", 200, 822),
    ],
)
def test_txvn_header_parse_for_recorded_fixtures(filename: str, tile_index: int, body_size: int):
    payload = (FIXTURE_DIR / filename).read_bytes()

    header = parse_txvn_header(payload)

    assert header.idx == 1001
    assert header.level == 13
    assert header.tile_index == tile_index
    assert header.signature == b"TXVN"
    assert header.date == 20150227
    assert header.body_size == body_size
    assert header.body_offset == TXVN_HEADER_SIZE
    assert header.body_offset == len(payload) - body_size


def test_txvn_covered_tiles_use_standard_zlib_and_empty_tile_is_literal():
    covered = (FIXTURE_DIR / "mobile_street_beijing_lv13_bl100.bin").read_bytes()
    empty = (FIXTURE_DIR / "mobile_street_beijing_lv13_bl10_empty.bin").read_bytes()

    covered_body = covered[TXVN_HEADER_SIZE:]
    empty_body = empty[TXVN_HEADER_SIZE:]

    assert covered_body.startswith(b"\x78\x9c")
    assert len(zlib.decompress(covered_body)) == 101
    with pytest.raises(zlib.error):
        zlib.decompress(covered_body, -15)

    assert empty_body == b"\x0a\x00\x00\x00\x0d\x00\x00"
    with pytest.raises(zlib.error):
        zlib.decompress(empty_body)


def test_tencent_geo_pixel_gcj02_round_trip_within_one_pixel():
    pixel = (86811234.25, 101234567.75)

    lon, lat = tencent_pixel_to_gcj02(*pixel)
    recovered = tencent_gcj02_to_pixel(lon, lat)

    assert abs(recovered[0] - pixel[0]) <= 1.0
    assert abs(recovered[1] - pixel[1]) <= 1.0


def test_gcj02_wgs84_inverse_round_trip():
    gcj_lon, gcj_lat = 116.410244, 39.916404

    wgs_lon, wgs_lat = gcj02_to_wgs84(gcj_lon, gcj_lat)
    recovered_gcj_lon, recovered_gcj_lat = wgs84_to_gcj02(wgs_lon, wgs_lat)

    assert abs(recovered_gcj_lon - gcj_lon) < 1e-6
    assert abs(recovered_gcj_lat - gcj_lat) < 1e-6


def test_tencent_bl_tile_enumeration_is_column_major_north_to_south():
    tile_size = tencent_tile_size(13)
    min_px_x = 1000 * tile_size + 1
    max_px_x = 1002 * tile_size - 1
    north_px_y = 2000 * tile_size + 1
    south_px_y = 2003 * tile_size - 1

    min_lon, max_lat = tencent_pixel_to_gcj02(min_px_x, north_px_y)
    max_lon, min_lat = tencent_pixel_to_gcj02(max_px_x, south_px_y)

    tiles = tencent_bl_tiles_for_gcj02_bbox(
        BoundingBox(min_lon=min_lon, min_lat=min_lat, max_lon=max_lon, max_lat=max_lat),
        13,
    )

    assert [(tile.bl, tile.tile_x, tile.tile_y) for tile in tiles] == [
        (0, 1000, 2000),
        (1, 1000, 2001),
        (2, 1000, 2002),
        (3, 1001, 2000),
        (4, 1001, 2001),
        (5, 1001, 2002),
    ]


@pytest.mark.parametrize(
    ("filename", "expected_min_lines"),
    [
        ("mobile_street_beijing_lv13_bl200.bin", 1),
        ("mobile_street_beijing_lv13_bl100.bin", 1),
        ("mobile_street_beijing_lv13_bl10_empty.bin", 0),
    ],
)
def test_txvn_linestring_decode_from_fixtures(filename: str, expected_min_lines: int):
    payload = (FIXTURE_DIR / filename).read_bytes()

    tile = parse_txvn_tile(payload, tile_origin_px=(0, 0))

    assert len(tile.linestrings) >= expected_min_lines
    if expected_min_lines == 0:
        assert tile.is_empty is True
    else:
        assert tile.is_empty is False
        assert all(len(line) >= 2 for line in tile.linestrings)


def test_tencent_mobile_street_source_kind_registered_and_counts_fixture(make_source, make_decode_context):
    assert "tencent_mobile_street" in SOURCE_KIND_HANDLERS

    source = make_source("tencent_mobile_street")
    payload = (FIXTURE_DIR / "mobile_street_beijing_lv13_bl100.bin").read_bytes()
    ctx = make_decode_context(source, payload=payload, content_type="text/plain")

    result = get_source_kind_handler("tencent_mobile_street")(ctx)

    assert result.feature_count >= 1
    assert result.record_count == result.feature_count
    assert result.is_empty is False
    assert result.tile_path is not None and result.tile_path.exists()
