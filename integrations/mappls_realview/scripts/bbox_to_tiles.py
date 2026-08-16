#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mappls_realview.bbox import BBox, tile_bounds, tiles_for_bbox


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bbox", nargs=4, type=float, required=True, metavar=("WEST", "SOUTH", "EAST", "NORTH"))
    ap.add_argument("--zoom", type=int, required=True)
    args = ap.parse_args()
    bbox = BBox(*args.bbox).validate()
    rows = tiles_for_bbox(bbox, args.zoom)
    print(f"{len(rows)} XYZ tiles")
    for z, x, y in rows:
        b = tile_bounds(z, x, y)
        print(f"{z}/{x}/{y}  [{b.west:.6f},{b.south:.6f},{b.east:.6f},{b.north:.6f}]")


if __name__ == "__main__":
    main()
