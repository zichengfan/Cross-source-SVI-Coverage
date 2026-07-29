"""MapJack street-view coverage-overlay raster tiles.

MapJack serves unauthenticated `dots_r5` GIF overlay tiles as a standard
web-mercator XYZ pyramid. Presence is derived from non-transparent pixels
(alpha>0) in the public dot-overlay raster; absent tiles are served as HTTP 404
by the origin and are skipped by the fetch runner rather than treated as imagery.

ToS caveat: MapJack Terms forbid bulk downloads of imagery/numerical data; this
provider stores ONLY a derived binary-presence raster (never imagery, never
coordinates); robots.txt is 404; fetches are anonymous over HTTPS.
"""

from __future__ import annotations

from coverage_acquisition.models import BoundingBox, ProviderDefinition, SourceDefinition
from coverage_acquisition.providers._registry import register_provider

PROVIDER = ProviderDefinition(
    key="mapjack",
    output_namespace="mapjack_dots_r5_raster",
    run_label_prefix="mapjack_dots_r5",
    default_display_zoom=14,
    coordinate_scheme="web_mercator",
    area_presets={
        "chiang_mai_bbox": BoundingBox(
            min_lon=98.899549,
            min_lat=18.697236,
            max_lon=99.073957,
            max_lat=18.864633,
        ),
    },
    sources=(
        SourceDefinition(
            id="mapjack_dots_r5",
            kind="raster",
            template="https://www.mapjack.com/dots_r5/{z}/{x}/{z}_{x}_{y}.gif",
            headers={
                "User-Agent": "global-svi-coverage-observatory/0.3 (MapJack coverage alpha raster)",
                "Accept": "image/gif,image/*;q=0.9,*/*;q=0.1",
                "Referer": "https://www.mapjack.com/",
            },
            display_zoom_min=14,
            display_zoom_max=16,
            query_zoom=16,
            expect_content_type_prefix="image/",
            storage_subdir="tiles",
            options={
                "coverage_from": "alpha",
                "absent_tile_status": "404",
                "overlay_folder": "dots_r5",
                "native_source_zoom": "16",
            },
            notes=(
                "MapJack dots_r5 street-view coverage overlay GIF tiles. "
                "Presence = non-transparent pixels (alpha>0); the project stores "
                "only the derived binary-presence raster, not MapJack imagery or "
                "dot coordinates."
            ),
        ),
    ),
)

register_provider(PROVIDER)
