"""Baidu Maps street-view coverage raster tiles (Baidu bd09mc tile grid)."""

from __future__ import annotations

from coverage_acquisition.models import ProviderDefinition, SourceDefinition
from coverage_acquisition.providers._presets import COMMON_AREA_PRESETS
from coverage_acquisition.providers._registry import register_provider

PROVIDER = ProviderDefinition(
    key="baidu",
    output_namespace="baidu_mapsv_raster",
    run_label_prefix="baidu_mapsv",
    default_display_zoom=13,
    coordinate_scheme="baidu",
    area_presets={"hong_kong_urban_bbox_approx": COMMON_AREA_PRESETS["hong_kong_urban_bbox_approx"]},
    sources=(
        SourceDefinition(
            id="baidu_mapsv_tile",
            kind="raster",
            template="https://mapsv0.bdimg.com/tile/?udt=20200825&qt=tile&styles=pl&x={x}&y={y}&z={z}",
            headers={
                "User-Agent": "global-svi-coverage-observatory/0.2",
                "Referer": "https://map.baidu.com/",
            },
            storage_subdir="tiles",
            expect_content_type_prefix="image/",
        ),
    ),
)

register_provider(PROVIDER)
