#!/usr/bin/env python3
"""Create the P0 schema summary and QGIS-ready GeoJSON for one MVT tile."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mappls_realview.bbox import tile_bounds
from mappls_realview.geo import write_feature_collection
from mappls_realview.mvt import decode_pbf_to_features, inspect_pbf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pbf")
    ap.add_argument("--xyz", nargs=3, type=int, required=True, metavar=("Z", "X", "Y"))
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    z, x, y = args.xyz
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stem = f"{z}_{x}_{y}"
    schema = inspect_pbf(args.pbf)
    features = decode_pbf_to_features(args.pbf, z, x, y)
    geojson = write_feature_collection(features, out / f"realview_{stem}.geojson")
    summary = {
        "pbf": str(args.pbf),
        "canonical_xyz": [z, x, y],
        "tile_bounds_wgs84": tile_bounds(z, x, y).as_list(),
        "crs": "OGC:CRS84 / WGS84 longitude-latitude",
        "decoded_feature_count": len(features),
        "geojson": str(geojson),
        "schema": schema,
    }
    summary_path = out / f"realview_{stem}.summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
