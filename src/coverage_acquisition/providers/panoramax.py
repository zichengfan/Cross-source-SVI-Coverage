"""Panoramax federated catalog coverage (MVT sequences)."""

from __future__ import annotations

from coverage_acquisition.models import ProviderDefinition, SourceDefinition
from coverage_acquisition.providers._presets import COMMON_AREA_PRESETS
from coverage_acquisition.providers._registry import register_provider

PROVIDER = ProviderDefinition(
    key="panoramax",
    output_namespace="panoramax_mvt_coverage",
    run_label_prefix="panoramax_coverage",
    default_display_zoom=13,
    area_presets={"amsterdam_city_bbox_approx": COMMON_AREA_PRESETS["amsterdam_city_bbox_approx"]},
    sources=(
        SourceDefinition(
            id="panoramax_xyz_mvt",
            kind="vector_mvt",
            template="https://api.panoramax.xyz/api/map/{z}/{x}/{y}.mvt",
            headers={
                "User-Agent": "global-svi-coverage-observatory/0.2",
                "Accept": "application/vnd.mapbox-vector-tile, application/octet-stream;q=0.9, */*;q=0.1",
                "Referer": "https://api.panoramax.xyz/en/index?focus=map",
            },
            layer_names=("sequences",),
            storage_subdir="vector_mvt",
            vector_decoder="custom_mvt",
        ),
    ),
)

register_provider(PROVIDER)
