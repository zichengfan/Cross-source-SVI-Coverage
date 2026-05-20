"""KartaView (OpenStreetCam) sequence coverage raster tiles."""

from __future__ import annotations

from coverage_acquisition.models import ProviderDefinition, SourceDefinition
from coverage_acquisition.providers._presets import COMMON_AREA_PRESETS
from coverage_acquisition.providers._registry import register_provider

PROVIDER = ProviderDefinition(
    key="kartaview",
    output_namespace="kartaview_coverage_raster",
    run_label_prefix="kartaview_coverage",
    default_display_zoom=13,
    area_presets={"amsterdam_city_bbox_approx": COMMON_AREA_PRESETS["amsterdam_city_bbox_approx"]},
    sources=(
        SourceDefinition(
            id="kartaview_sequence_tiles",
            kind="raster",
            template="https://api.openstreetcam.org/2.0/sequence/tiles/{x}/{y}/{z}.png",
            headers={
                "User-Agent": "global-svi-coverage-observatory/0.2",
                "Referer": "https://kartaview.org/",
            },
            storage_subdir="tiles",
            expect_content_type_prefix="image/",
        ),
    ),
)

register_provider(PROVIDER)
