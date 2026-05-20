"""Apple Look Around coverage (via the public lookmap frontend)."""

from __future__ import annotations

from coverage_acquisition.models import ProviderDefinition, SourceDefinition
from coverage_acquisition.providers._presets import COMMON_AREA_PRESETS
from coverage_acquisition.providers._registry import register_provider

PROVIDER = ProviderDefinition(
    key="apple_lookaround",
    output_namespace="apple_lookaround_bluelines_layered",
    run_label_prefix="apple_lookaround_layered",
    default_display_zoom=18,
    supports_auto_zoom=True,
    area_presets={"amsterdam_city_bbox_approx": COMMON_AREA_PRESETS["amsterdam_city_bbox_approx"]},
    sources=(
        SourceDefinition(
            id="apple_lookaround_bluelines_raster_2x",
            kind="raster",
            template="https://lookmap.eu.pythonanywhere.com/bluelines_raster_2x/{z}/{x}/{y}.png",
            headers={
                "Referer": "https://lookmap.eu.pythonanywhere.com/",
                "User-Agent": "global-svi-coverage-observatory/0.2",
            },
            display_zoom_min=3,
            display_zoom_max=7,
            storage_subdir="raster",
            expect_content_type_prefix="image/",
            notes="Low-zoom raster coverage tiles served directly as PNG.",
        ),
        SourceDefinition(
            id="apple_lookaround_cached_bluelines",
            kind="vector_mvt",
            template="https://lookmap.eu.pythonanywhere.com/bluelines2/{z}/{x}/{y}/",
            headers={
                "Referer": "https://lookmap.eu.pythonanywhere.com/",
                "User-Agent": "global-svi-coverage-observatory/0.2",
            },
            display_zoom_min=8,
            display_zoom_max=15,
            layer_names=("panos",),
            storage_subdir="vector_mvt",
            vector_decoder="ogr2ogr",
            notes="Cached vector blue lines. Response body is often gzip-compressed MVT bytes.",
        ),
        SourceDefinition(
            id="apple_lookaround_coverage_tiles",
            kind="coverage_json",
            template="https://lookmap.eu.pythonanywhere.com/tiles/coverage/{x}/{y}/",
            headers={
                "Referer": "https://lookmap.eu.pythonanywhere.com/",
                "User-Agent": "global-svi-coverage-observatory/0.2",
            },
            display_zoom_min=16,
            display_zoom_max=20,
            query_zoom=17,
            storage_subdir="coverage_json",
            expect_content_type_prefix="application/json",
            notes="High-zoom pano coverage tiles returned as JSON on a fixed z17 grid.",
        ),
    ),
)

register_provider(PROVIDER)
