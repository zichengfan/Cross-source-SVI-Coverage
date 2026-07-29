"""ASIG Albania StreetView 360 coverage provider.

ASIG serves Albania StreetView 360 coverage as http-only static GeoJSON tiles
under a fixed build-stamp path segment, `tiles-1674737600`. Each tile mixes
photo-center `Point` features with decorative `LineString`/`MultiLineString`
features. The geometry coordinates are tile-local pixel space, so the provider
configures `vector_geojson` to emit only `Point` records using true WGS84
coordinates from the `lon` and `lat` properties.

ASIG is Albania's public spatial-data infrastructure authority. Coverage access
is based on the Law 72/2012 public-SDI mandate; this project stores derived
coverage records only, not panorama imagery.
"""

from __future__ import annotations

from coverage_acquisition.models import BoundingBox, ProviderDefinition, SourceDefinition
from coverage_acquisition.providers._registry import register_provider

PROVIDER = ProviderDefinition(
    key="asig",
    output_namespace="asig_coverage",
    run_label_prefix="asig_coverage",
    default_display_zoom=14,
    coordinate_scheme="web_mercator",
    area_presets={
        "tirana_center_bbox": BoundingBox(min_lon=19.79, min_lat=41.30, max_lon=19.86, max_lat=41.35),
    },
    sources=(
        SourceDefinition(
            id="asig_streetview_360_geojson",
            kind="vector_geojson",
            template="http://360.asig.gov.al/AlbaniaStreetView/player2/tiles-1674737600/{z}/{x}/{y}.geojson",
            headers={
                "User-Agent": "cross-source-svi-coverage/0.1 ASIG-Albania-StreetView360 coverage research",
                "Accept": "application/geo+json, application/json;q=0.9, */*;q=0.1",
            },
            display_zoom_min=6,
            display_zoom_max=15,
            options={
                "geojson_lon_property": "lon",
                "geojson_lat_property": "lat",
                "geojson_geometry_types": "Point",
            },
        ),
    ),
)

register_provider(PROVIDER)
