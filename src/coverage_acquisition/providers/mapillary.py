"""Mapillary coverage (mly1_public vector tiles; needs an access token)."""

from __future__ import annotations

from coverage_acquisition.models import ProviderDefinition, SourceDefinition
from coverage_acquisition.providers._presets import COMMON_AREA_PRESETS
from coverage_acquisition.providers._registry import register_provider

PROVIDER = ProviderDefinition(
    key="mapillary",
    output_namespace="mapillary_mvt_coverage",
    run_label_prefix="mapillary_coverage",
    default_display_zoom=13,
    area_presets={"amsterdam_city_bbox_approx": COMMON_AREA_PRESETS["amsterdam_city_bbox_approx"]},
    sources=(
        SourceDefinition(
            id="mapillary_mly1_public_vtp",
            kind="vector_mvt",
            template="https://tiles.mapillary.com/maps/vtp/mly1_public/2/{z}/{x}/{y}",
            headers={
                "User-Agent": "global-svi-coverage-observatory/0.2",
                "Accept": "application/vnd.mapbox-vector-tile, application/octet-stream;q=0.9, */*;q=0.1",
                "Referer": "https://www.mapillary.com/",
            },
            layer_names=("sequence",),
            storage_subdir="vector_mvt",
            token_query_param="access_token",
            vector_decoder="custom_mvt",
        ),
    ),
)

register_provider(PROVIDER)
