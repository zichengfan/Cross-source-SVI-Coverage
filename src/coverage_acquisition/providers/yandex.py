"""Yandex street-view (panorama) coverage raster tiles.

Tile selection and bounds use Yandex's WGS84 elliptic Mercator grid. The
renderer version is discovered live from the Yandex Maps frontend at fetch time
(see runners._build_runtime_options); the value below is only a fallback.
"""

from __future__ import annotations

from coverage_acquisition.models import ProviderDefinition, SourceDefinition
from coverage_acquisition.providers._presets import COMMON_AREA_PRESETS
from coverage_acquisition.providers._registry import register_provider

PROVIDER = ProviderDefinition(
    key="yandex",
    output_namespace="yandex_stv_raster",
    run_label_prefix="yandex_stv_raster",
    default_display_zoom=13,
    coordinate_scheme="yandex_wgs84_mercator",
    area_presets={
        "moscow_center_stv_bbox": COMMON_AREA_PRESETS["moscow_center_stv_bbox"],
        "abakan_bbox": COMMON_AREA_PRESETS["abakan_bbox"],
    },
    sources=(
        SourceDefinition(
            id="yandex_stv_tiles_png",
            kind="raster",
            template=(
                "https://core-stv-renderer.maps.yandex.net/2.x/tiles?"
                "l={layer}&x={x}&y={y}&z={z}&scale=1&v={version}&lang=en_US&format=png"
            ),
            headers={
                "User-Agent": "global-svi-coverage-observatory/0.2",
                "Accept": "image/png, image/*;q=0.9, */*;q=0.1",
                "Referer": "https://yandex.com/maps/",
            },
            storage_subdir="tiles",
            expect_content_type_prefix="image/",
            options={
                "config_kind": "yandex_stv_renderer",
                "frontend_page_url": "https://yandex.com/maps/213/moscow/?l=stv&ll=37.565000%2C55.745000&z=13",
                "layer": "stv",
                "version_fallback": "2026.05.19.17.14-1_26.05.18-0-29389",
            },
            notes=(
                "Yandex street-view coverage raster tiles. Tile selection and bounds use "
                "Yandex's WGS84 elliptic Mercator grid."
            ),
        ),
    ),
)

register_provider(PROVIDER)
