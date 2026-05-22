"""Mapy.com Panorama coverage-overlay raster tiles.

Mapy was previously implemented as a `streetlevel` point-probe provider using
the undocumented FRPC `getbest` path. It is now a `raster` provider for the
undocumented `panorama_ln_hybrid-m` line-overlay PNG endpoint used by the public
Mapy.com viewer. The project publishes only a derived binary coverage raster,
never panorama imagery or rendered map tiles.

Coverage is Czech-only in practice. Empty tiles redirect to a transparent
`default` PNG, and `Referer: https://mapy.com/` is required for that empty-tile
path; without it, empty tiles return HTTP 403.
"""

from __future__ import annotations

from coverage_acquisition.models import BoundingBox, ProviderDefinition, SourceDefinition
from coverage_acquisition.providers._registry import register_provider

PROVIDER = ProviderDefinition(
    key="mapy",
    output_namespace="mapy_panorama_raster",
    run_label_prefix="mapy_panorama",
    coordinate_scheme="web_mercator",
    default_display_zoom=14,
    area_presets={
        "prague_centre_pilot_bbox": BoundingBox(
            min_lon=14.40,
            min_lat=50.075,
            max_lon=14.44,
            max_lat=50.095,
        ),
    },
    sources=(
        SourceDefinition(
            id="mapy_panorama_lines",
            kind="raster",
            template="https://mapserver.mapy.cz/panorama_ln_hybrid-m/{z}-{x}-{y}",
            headers={
                "User-Agent": "global-svi-coverage-observatory/0.3",
                "Accept": "image/png, image/*;q=0.9, */*;q=0.1",
                "Referer": "https://mapy.com/",
            },
            storage_subdir="tiles",
            expect_content_type_prefix="image/",
            options={
                "empty_tile_rule": "transparent_png",
                "coverage_from": "alpha",
            },
            notes=(
                "Mapy.com Panorama line coverage overlay (`panorama_ln_hybrid-m`). "
                "Tile paths use one hyphen-joined `{z}-{x}-{y}` token, not a z/x/y "
                "directory tree. Empty tiles resolve via 302 to a transparent "
                "`default` PNG; `Referer: https://mapy.com/` is required for the "
                "empty-tile path."
            ),
        ),
    ),
)

register_provider(PROVIDER)
