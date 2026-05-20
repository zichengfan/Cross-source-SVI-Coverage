"""Google Street View coverage (via the sv-map mts raster endpoint)."""

from __future__ import annotations

from coverage_acquisition.models import ProviderDefinition, SourceDefinition
from coverage_acquisition.providers._presets import COMMON_AREA_PRESETS
from coverage_acquisition.providers._registry import register_provider

PROVIDER = ProviderDefinition(
    key="svmap_google",
    output_namespace="svmap_google_mts_raster",
    run_label_prefix="svmap_google_mts",
    default_display_zoom=13,
    area_presets={"amsterdam_city_bbox_approx": COMMON_AREA_PRESETS["amsterdam_city_bbox_approx"]},
    sources=(
        SourceDefinition(
            id="svmap_google_mts",
            kind="raster",
            template=(
                "https://mts.googleapis.com/vt?pb="
                "!1m4!1m3!1i{z}!2i{x}!3i{y}"
                "!2m8!1e2!2ssvv"
                "!4m2!1scc!2s*211m3*211e2*212b1*213e2*212b1*214b1"
                "!4m2!1ssvl!2s*212b1"
                "!3m11!2sen!3sUS"
                "!12m4!1e68!2m2!1sset!2sRoadmap"
                "!12m3!1e37!2m1!1ssmartmaps"
                "!5m1!5f1.5"
            ),
            headers={
                "User-Agent": "global-svi-coverage-observatory/0.2",
                "Referer": "https://sv-map.netlify.app/",
            },
            storage_subdir="tiles",
            expect_content_type_prefix="image/",
        ),
    ),
)

register_provider(PROVIDER)
