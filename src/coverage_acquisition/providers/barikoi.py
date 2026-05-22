"""Barikoi ThirdEye360 street-view coverage (MVT panorama points).

This provider reads the vector MVT coverage layer `ThirdEye360` used by the
ThirdEye360 viewer, not a raster overlay or per-point JSON API. The endpoint is
an undocumented © Barikoi tile source; this project publishes only a derived
binary presence raster and never downloads imagery.

The tile source requires no auth and no `.env` key. Coverage is Bangladesh
only, concentrated around the Dhaka region. Low-zoom tiles are large because
the tileset was generated without feature or tile-size limits, so discovery
should run at z11-z12 and final fetching at z14. A date layer from
`capture_date_raw` is deferred to a follow-up.
"""

from __future__ import annotations

from coverage_acquisition.models import BoundingBox, ProviderDefinition, SourceDefinition
from coverage_acquisition.providers._registry import register_provider

PROVIDER = ProviderDefinition(
    key="barikoi",
    output_namespace="barikoi_mvt_coverage",
    run_label_prefix="barikoi_coverage",
    default_display_zoom=14,
    coordinate_scheme="web_mercator",
    area_presets={
        "dhaka_pilot_bbox": BoundingBox(
            min_lon=90.395,
            min_lat=23.790,
            max_lon=90.430,
            max_lat=23.815,
        ),
    },
    sources=(
        SourceDefinition(
            id="barikoi_thirdeye360_mvt",
            kind="vector_mvt",
            template="https://tiles.bmapsbd.com/ThirdEye360/{z}/{x}/{y}",
            headers={
                "User-Agent": "global-svi-coverage-observatory/0.3",
                "Referer": "https://streetview.bmapsbd.com/",
                "Accept": "application/vnd.mapbox-vector-tile, application/octet-stream;q=0.9, */*;q=0.1",
            },
            layer_names=("ThirdEye360",),
            storage_subdir="vector_mvt",
            vector_decoder="custom_mvt",
            notes=(
                "Barikoi ThirdEye360 street-view coverage — the `ThirdEye360` source-layer of the "
                "public `tiles.bmapsbd.com/ThirdEye360` MVT tileset (the vector source the "
                "streetview.bmapsbd.com viewer adds). Web Mercator XYZ; one `Point` feature per "
                "captured 360° panorama; presence = >=1 feature. Empty tiles return HTTP 204."
            ),
        ),
    ),
)

register_provider(PROVIDER)
