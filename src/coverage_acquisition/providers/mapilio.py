"""Mapilio MVT coverage layer.

This provider fetches the `map_roads_line` layer from the Mapbox/MapLibre
`mapilio-tiles` vector source. The tile URL uses Mapilio's non-standard
`{x}/{y}/{z}` path order, and zero-byte HTTP 200 tile bodies mean no coverage.

The `geo.mapilio.com/map` endpoint is undocumented; this project publishes only
a derived binary coverage raster and never downloads imagery. Coverage requires
no auth and is global but sparse and contributor-driven.
"""

from __future__ import annotations

from coverage_acquisition.models import BoundingBox, ProviderDefinition, SourceDefinition
from coverage_acquisition.providers._registry import register_provider

PROVIDER = ProviderDefinition(
    key="mapilio",
    output_namespace="mapilio_mvt_coverage",
    run_label_prefix="mapilio_coverage",
    coordinate_scheme="web_mercator",
    default_display_zoom=14,
    area_presets={
        "istanbul_beyoglu_pilot_bbox": BoundingBox(
            min_lon=28.96,
            min_lat=41.00,
            max_lon=29.00,
            max_lat=41.03,
        ),
    },
    sources=(
        SourceDefinition(
            id="mapilio_map_roads_line_vtp",
            kind="vector_mvt",
            template="https://geo.mapilio.com/map/{x}/{y}/{z}",
            headers={
                "User-Agent": "global-svi-coverage-observatory/0.3",
                "Accept": "application/vnd.mapbox-vector-tile, application/octet-stream;q=0.9, */*;q=0.1",
                "Referer": "https://mapilio.com/",
            },
            layer_names=("map_roads_line",),
            storage_subdir="vector_mvt",
            vector_decoder="custom_mvt",
            notes=(
                "Mapilio coverage MVT layer `map_roads_line` from the "
                "`mapilio-tiles` source. Tile path order is `{x}/{y}/{z}` "
                "(x first, z last). Zero-byte HTTP 200 tile bodies indicate "
                "no coverage."
            ),
        ),
    ),
)

register_provider(PROVIDER)
