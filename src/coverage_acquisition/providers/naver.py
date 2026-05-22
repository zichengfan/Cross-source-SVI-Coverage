"""Naver 거리뷰 coverage-overlay raster tiles.

This provider fetches the rendered 거리뷰 overlay raster layer (`mt=ps`), not a
panorama API. Tiles use Web Mercator XYZ on `map.pstatic.net`; the `{version}`
path segment is discovered live from the TileJSON at fetch time, with the value
below only as a fallback. Fetch only from `map.pstatic.net`, whose robots.txt is
unavailable; never crawl `map.naver.com`, which is restrictive and appears here
only as a Referer. Coverage is South Korea only and requires no auth.
"""

from __future__ import annotations

from coverage_acquisition.models import BoundingBox, ProviderDefinition, SourceDefinition
from coverage_acquisition.providers._registry import register_provider

PROVIDER = ProviderDefinition(
    key="naver",
    output_namespace="naver_streetview_raster",
    run_label_prefix="naver_streetview_raster",
    default_display_zoom=13,
    coordinate_scheme="web_mercator",
    area_presets={
        "seoul_gangnam_pilot_bbox": BoundingBox(
            min_lon=127.020,
            min_lat=37.490,
            max_lon=127.060,
            max_lat=37.520,
        ),
    },
    sources=(
        SourceDefinition(
            id="naver_streetview_overlay_png",
            kind="raster",
            template="https://map.pstatic.net/nrb/styles/basic/{version}/{z}/{x}/{y}.png?mt=ps",
            headers={
                "User-Agent": "global-svi-coverage-observatory/0.3",
                "Referer": "https://map.naver.com/",
                "Accept": "image/png,image/*;q=0.9,*/*;q=0.1",
            },
            storage_subdir="tiles",
            expect_content_type_prefix="image/",
            options={
                "config_kind": "naver_pstatic_tiles",
                "tilejson_url": "https://map.pstatic.net/nrb/styles/basic.json?fmt=png&mt=ps",
                "mt": "ps",
                "version_fallback": "1778829614",
                "empty_tile_rule": "transparent_png",
                "coverage_from": "alpha",
            },
            notes=(
                "Naver 거리뷰 coverage-overlay raster tiles (`mt=ps`, transparent "
                "background, Web Mercator XYZ). Presence = alpha>0. Fetch only "
                "from map.pstatic.net; map.naver.com is Referer-only."
            ),
        ),
    ),
)

register_provider(PROVIDER)
