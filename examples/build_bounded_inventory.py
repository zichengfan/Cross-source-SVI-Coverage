"""Build a deterministic bounded raster inventory without network requests."""

from __future__ import annotations

import argparse
import json

from shapely.geometry import box

from coverage_acquisition.bounded_raster import build_polygon_tile_manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", required=True)
    parser.add_argument("--region-id", required=True)
    parser.add_argument("--bbox", nargs=4, required=True, type=float, metavar=("W", "S", "E", "N"))
    parser.add_argument("--level", required=True, type=int)
    parser.add_argument("--halo-tiles", type=int, default=1)
    args = parser.parse_args()

    manifest = build_polygon_tile_manifest(
        provider=args.provider,
        region_id=args.region_id,
        geometry_wgs84=box(*args.bbox),
        level=args.level,
        halo_tiles=args.halo_tiles,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
