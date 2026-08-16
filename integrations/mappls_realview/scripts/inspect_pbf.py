#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mappls_realview.mvt import inspect_pbf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pbf")
    args = ap.parse_args()
    print(json.dumps(inspect_pbf(args.pbf), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
