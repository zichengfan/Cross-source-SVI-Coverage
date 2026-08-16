#!/usr/bin/env python3
"""Capture Mappls RealView coverage through the authorized local Web SDK."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from mappls_realview.bbox import BBox
from mappls_realview.sdk_capture import capture_sdk_bbox


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture and decode RealView PBF responses for one bbox/zoom.")
    parser.add_argument(
        "--bbox",
        nargs=4,
        type=float,
        required=True,
        metavar=("WEST", "SOUTH", "EAST", "NORTH"),
    )
    parser.add_argument("--zoom", type=int, required=True)
    parser.add_argument(
        "--out",
        default=str(ROOT.parent / "data" / "raw" / "mappls_realview_mvt_coverage"),
        help="Output root containing production/ and, in debug mode, debug/.",
    )
    parser.add_argument(
        "--mode",
        choices=("production", "debug"),
        default="production",
        help="production keeps GeoJSON tiles + run summary; debug also keeps PBF/schema/screenshot.",
    )
    parser.add_argument("--run-id", help="Optional stable run label; defaults to a UTC timestamp.")
    parser.add_argument("--web-dir", default=str(ROOT / "web"))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--tile-wait", type=float, default=1.5)
    parser.add_argument("--ready-timeout", type=float, default=60.0)
    parser.add_argument("--headful", action="store_true")
    parser.add_argument(
        "--chrome-executable",
        default=("/usr/bin/google-chrome-stable" if Path("/usr/bin/google-chrome-stable").exists() else None),
    )
    args = parser.parse_args()

    manifest = capture_sdk_bbox(
        web_dir=args.web_dir,
        bbox=BBox(*args.bbox),
        zoom=args.zoom,
        out_dir=args.out,
        output_mode=args.mode,
        run_id=args.run_id,
        host=args.host,
        port=args.port,
        headless=not args.headful,
        tile_wait_seconds=args.tile_wait,
        ready_timeout_seconds=args.ready_timeout,
        chrome_executable=args.chrome_executable,
    )
    summary_keys = (
        "bbox",
        "zoom",
        "map_state",
        "expected_tile_count",
        "captured_tile_count",
        "failed_tile_count",
        "decoded_feature_count",
        "run_summary",
        "debug_manifest",
        "screenshot",
        "warning",
    )
    print(json.dumps({key: manifest.get(key) for key in summary_keys}, indent=2))


if __name__ == "__main__":
    main()
