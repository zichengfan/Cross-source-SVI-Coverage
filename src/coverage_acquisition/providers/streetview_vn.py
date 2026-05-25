"""Streetview.vn / NDAVIEW panorama coverage (MVT sequences).

`www.streetview.vn` redirects to the `view.ndamaps.vn` NDAVIEW viewer. The
whole-provider coverage layer is the unauthenticated
`gpx-view.ndamaps.vn/snap/{z}/{x}/{y}.mvt` vector source, using the
`sequences` MultiLineString layer. The per-account
`api-view.ndamaps.vn/v1/map/user/...` variant and the points/search APIs are
filtered or non-coverage endpoints and are intentionally not used.

Empty tiles return HTTP 404. Coverage is Vietnam-only and requires no auth.
The endpoint is undocumented; this project publishes only a derived binary
coverage raster, never NDAVIEW imagery. All tile fetching is on
`gpx-view.ndamaps.vn`; `view.ndamaps.vn` is used only as the Referer.
"""

from __future__ import annotations

from coverage_acquisition.models import BoundingBox, ProviderDefinition, SourceDefinition
from coverage_acquisition.providers._registry import register_provider

PROVIDER = ProviderDefinition(
    key="streetview_vn",
    output_namespace="streetview_vn_mvt_coverage",
    run_label_prefix="streetview_vn_coverage",
    default_display_zoom=13,
    coordinate_scheme="web_mercator",
    area_presets={
        "hanoi_center_bbox": BoundingBox(
            min_lon=105.820,
            min_lat=21.015,
            max_lon=105.860,
            max_lat=21.045,
        ),
    },
    sources=(
        SourceDefinition(
            id="streetview_vn_snap_mvt",
            kind="vector_mvt",
            template="https://gpx-view.ndamaps.vn/snap/{z}/{x}/{y}.mvt",
            headers={
                "User-Agent": "global-svi-coverage-observatory/0.3",
                "Accept": "application/vnd.mapbox-vector-tile, application/octet-stream;q=0.9, */*;q=0.1",
                "Referer": "https://view.ndamaps.vn/",
            },
            layer_names=("sequences",),
            storage_subdir="vector_mvt",
            vector_decoder="custom_mvt",
            display_zoom_min=6,
            display_zoom_max=18,
            notes=(
                "NDAVIEW / Streetview.vn panorama-coverage MVT — `sequences` "
                "MultiLineString capture traces. Empty tiles return HTTP 404. "
                "Vietnam only; carries a per-feature `date`."
            ),
        ),
    ),
)

register_provider(PROVIDER)
