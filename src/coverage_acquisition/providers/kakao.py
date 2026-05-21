"""Kakao Road View coverage-overlay raster tiles.

This provider fetches the rendered `map_roadviewline` overlay raster layer, not
a panorama API. Tiles use Kakao's EPSG:5181 custom grid and are served at L7
only, with a native resolution of 16 m/px. Fetch only from `*.daumcdn.net`,
whose robots.txt has an empty `Disallow:` rule; never crawl `map.kakao.com`,
which disallows crawling and appears here only as a Referer. Coverage is South
Korea only and requires no auth.
"""

from __future__ import annotations

from coverage_acquisition.models import BoundingBox, ProviderDefinition, SourceDefinition
from coverage_acquisition.providers._registry import register_provider

PROVIDER = ProviderDefinition(
    key="kakao",
    output_namespace="kakao_roadview_overlay_raster",
    run_label_prefix="kakao_roadview_overlay",
    default_display_zoom=7,
    coordinate_scheme="kakao_epsg5181",
    area_presets={
        "seoul_city_hall_bbox": BoundingBox(
            min_lon=126.960,
            min_lat=37.560,
            max_lon=126.990,
            max_lat=37.580,
        ),
    },
    sources=(
        SourceDefinition(
            id="kakao_roadviewline",
            kind="raster",
            template="https://map0.daumcdn.net/map_roadviewline/3.00/L{z}/{y}/{x}.png",
            headers={
                "User-Agent": "global-svi-coverage-observatory/0.3",
                "Accept": "image/png,image/*;q=0.9,*/*;q=0.1",
                "Referer": "https://map.kakao.com/",
            },
            display_zoom_min=7,
            display_zoom_max=7,
            expect_content_type_prefix="image/",
            storage_subdir="tiles",
            options={
                "coverage_from": "alpha",
                "empty_tile_rule": "transparent_png",
                "layer": "map_roadviewline",
                "version": "3.00",
                "native_resolution_m_per_px": "16",
            },
            notes=(
                "Kakao Road View coverage-overlay raster tiles (`map_roadviewline`, "
                "EPSG:5181 grid, served at L7 only). Presence = alpha>0 "
                "(transparent bg, semi-transparent blue strokes)."
            ),
        ),
    ),
)

register_provider(PROVIDER)
