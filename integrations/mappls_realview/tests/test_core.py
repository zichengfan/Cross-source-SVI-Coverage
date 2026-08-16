import asyncio
import gzip
import inspect
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mappls_realview.bbox import BBox, tile_bounds, tiles_for_bbox
from mappls_realview.capture import DIGIT_PROFILES, decode_xyz
from mappls_realview.geo import optimize_tile_features, write_feature_collection
from mappls_realview.mvt import _tile_coord_to_lonlat
from mappls_realview.sdk_capture import (
    KEY_PLACEHOLDER,
    build_output_layout,
    capture_sdk_bbox,
    capture_sdk_bbox_async,
    validate_local_config,
)


def test_observed_payload_xyz():
    payload = "nolrflslnolnolvflrzlvslslvslwtlrzlwtltdlplblflqlvl=lrlelalllvlilelwl&lxl-lslelcl=lwtl"
    assert decode_xyz(payload) == (14, 11507, 7202)


def test_bbox_tiles_nonempty():
    b = BBox(72.80, 21.18, 72.88, 21.24)
    tiles = tiles_for_bbox(b, 14)
    assert tiles
    for z, x, y in tiles:
        tb = tile_bounds(z, x, y)
        assert tb.east > b.west and tb.west < b.east


def test_current_digit_profile_from_fresh_capture():
    payload = "htlslxslslhtltdlplblflqlvl=lrlelalllvlilelwl&lxl-lslelcl=lwtl"
    assert decode_xyz(payload, DIGIT_PROFILES["current_2026_08"]) == (3, 6, 3)
    assert decode_xyz(payload, DIGIT_PROFILES["legacy"]) == (6, 3, 6)


def test_mvt_top_left_corners_convert_to_xyz_bounds():
    bounds = tile_bounds(10, 737, 448)
    assert _tile_coord_to_lonlat(0, 0, 10, 737, 448, 4096) == [bounds.west, bounds.north]
    east, south = _tile_coord_to_lonlat(4096, 4096, 10, 737, 448, 4096)
    assert east == bounds.east
    assert south == bounds.south


def test_sdk_config_rejects_placeholder(tmp_path):
    web_dir = tmp_path / "web"
    web_dir.mkdir()
    (web_dir / "config.local.js").write_text(
        f'window.MAPPLS_CONFIG = {{ accessToken: "{KEY_PLACEHOLDER}" }};',
        encoding="utf-8",
    )
    try:
        validate_local_config(web_dir)
    except ValueError as exc:
        assert "placeholder" in str(exc)
    else:
        raise AssertionError("placeholder key should be rejected")


def test_sdk_config_accepts_manually_populated_key(tmp_path):
    web_dir = tmp_path / "web"
    web_dir.mkdir()
    config = web_dir / "config.local.js"
    config.write_text(
        'window.MAPPLS_CONFIG = { accessToken: "manual-test-key" };',
        encoding="utf-8",
    )
    assert validate_local_config(web_dir) == config


def test_sdk_notebook_entrypoint_is_async():
    assert inspect.iscoroutinefunction(capture_sdk_bbox_async)


def test_sync_sdk_entrypoint_rejects_active_asyncio_loop(tmp_path):
    async def invoke_sync_wrapper():
        try:
            capture_sdk_bbox(
                web_dir=tmp_path,
                bbox=BBox(77.205, 28.625, 77.228, 28.642),
                zoom=14,
                out_dir=tmp_path / "out",
            )
        except RuntimeError as exc:
            assert "await capture_sdk_bbox_async" in str(exc)
        else:
            raise AssertionError("sync wrapper should reject an active asyncio loop")

    asyncio.run(invoke_sync_wrapper())


def test_output_layout_supports_only_production_and_debug(tmp_path):
    production = build_output_layout(tmp_path, "production", "test-run")
    assert production.tile_path(14, 11705, 6830) == (
        tmp_path / "production" / "tiles" / "14" / "11705" / "6830.geojson.gz"
    )
    assert production.debug_run is None

    debug = build_output_layout(tmp_path, "debug", "test-run")
    assert debug.debug_run == tmp_path / "debug" / "runs" / "test-run"

    try:
        build_output_layout(tmp_path, "full", "test-run")
    except ValueError as exc:
        assert "production" in str(exc) and "debug" in str(exc)
    else:
        raise AssertionError("unsupported output mode should be rejected")


def test_production_geojson_is_atomic_gzip_and_lean(tmp_path):
    source = [
        {
            "type": "Feature",
            "properties": {
                "trip_id": "trip-1",
                "_mvt_id": 7,
                "_mvt_layer": "RealViewLayer",
                "_tile_z": 14,
                "_tile_x": 11705,
                "_tile_y": 6830,
            },
            "geometry": {
                "type": "LineString",
                "coordinates": [[77.205123456789, 28.625123456789], [77.206, 28.626]],
            },
        }
    ]
    optimized = optimize_tile_features(source, coordinate_precision=7)
    output = tmp_path / "production" / "tiles" / "14" / "11705" / "6830.geojson.gz"
    write_feature_collection(optimized, output, atomic=True)

    assert output.exists()
    assert not output.with_name(f".{output.name}.tmp").exists()
    with gzip.open(output, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    properties = payload["features"][0]["properties"]
    assert properties == {"trip_id": "trip-1", "_mvt_id": 7}
    assert payload["features"][0]["geometry"]["coordinates"][0] == [77.2051235, 28.6251235]
