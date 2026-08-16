"""Fetch or dry-run one provider over a bounding box."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from coverage_acquisition.models import BoundingBox, FetchAreaRequest
from coverage_acquisition.runners import fetch_provider_coverage


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    result.add_argument("--provider", required=True)
    result.add_argument("--bbox", nargs=4, required=True, type=float, metavar=("W", "S", "E", "N"))
    result.add_argument("--zoom", required=True, type=int)
    result.add_argument("--output-root", required=True, type=Path)
    result.add_argument("--dry-run", action="store_true")
    return result


def main() -> None:
    args = parser().parse_args()
    request = FetchAreaRequest(
        provider=args.provider,
        bbox=BoundingBox.from_sequence(args.bbox),
        output_root=args.output_root,
        display_zoom=args.zoom,
        dry_run=args.dry_run,
        access_token=os.environ.get("COVERAGE_ACCESS_TOKEN"),
    )
    result = fetch_provider_coverage(request)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
