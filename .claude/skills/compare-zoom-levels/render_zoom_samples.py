#!/usr/bin/env python
"""Render a provider's coverage overlay across source zoom levels, juxtaposed.

Helper for the `compare-zoom-levels` skill. Given one or more registered raster
providers and a single fixed geographic extent, fetch each provider's coverage
overlay at several source zoom levels, mosaic + crop every cell to the *same*
extent, and lay them out as one figure for a human to pick the source zoom.

Run via the project environment, e.g.:
    uv run python .claude/skills/compare-zoom-levels/render_zoom_samples.py \\
        --provider kakao --provider naver \\
        --center 127.0276 37.4979 --extent-km 2 --zooms 13,14,15
"""

from __future__ import annotations

import argparse
import io
import math
import os
import sys
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/mpl")
# Make the package importable whether or not it is installed in the environment.
_SRC = Path(__file__).resolve().parents[3] / "src"
if _SRC.is_dir():
    sys.path.insert(0, str(_SRC))

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from coverage_acquisition.geo import (  # noqa: E402
    tile_range_for_bbox,
    tile_to_lonlat_bounds_for_scheme,
)
from coverage_acquisition.models import BoundingBox, FetchAreaRequest  # noqa: E402
from coverage_acquisition.polite import PolitePolicy, polite_fetch  # noqa: E402
from coverage_acquisition.providers import get_provider  # noqa: E402
from coverage_acquisition.runtime_config import build_runtime_options  # noqa: E402

# One distinct colour per provider row, in order.
PALETTE = [
    (95, 170, 255),   # blue
    (195, 120, 255),  # purple
    (255, 85, 85),    # red
    (110, 210, 130),  # green
    (255, 175, 70),   # orange
    (90, 210, 230),   # cyan
]
EMPTY = (34, 36, 44)
PANEL = (22, 22, 26)
CELL = 300


def bbox_around(lon: float, lat: float, extent_km: float) -> BoundingBox:
    """A square WGS84 bounding box of side `extent_km` centred on (lon, lat)."""
    half_m = extent_km * 500.0
    dlat = half_m / 110_574.0
    dlon = half_m / (111_320.0 * math.cos(math.radians(lat)))
    return BoundingBox(lon - dlon, lat - dlat, lon + dlon, lat + dlat)


def default_zooms(provider, source) -> list[int]:
    """A sensible zoom spread when the caller did not pass `--zooms`."""
    lo, hi = source.display_zoom_min, source.display_zoom_max
    if lo == hi:
        return [lo]
    d = provider.default_display_zoom
    return sorted({max(lo, min(hi, z)) for z in (d - 4, d - 2, d, d + 2)})


def _fetch_tile(url: str, headers: dict[str, str]) -> Image.Image | None:
    try:
        payload, _content_type, _status = polite_fetch(
            url, headers=headers, policy=PolitePolicy(timeout_seconds=30)
        )
        return Image.open(io.BytesIO(payload)).convert("RGBA").resize((256, 256))
    except Exception:
        return None


def render_overlay(template, scheme, headers, fmt_values, zoom, bbox) -> Image.Image:
    """Mosaic the provider's tiles at `zoom` and crop to exactly `bbox` (RGBA)."""
    tr = tile_range_for_bbox(bbox, zoom, scheme)
    xs = list(range(tr.x_min, tr.x_max + 1))
    ys = list(range(tr.y_min, tr.y_max + 1))
    # Tile-y can increase north (e.g. kakao_epsg5181) or south (web mercator).
    lo_b = tile_to_lonlat_bounds_for_scheme(tr.x_min, tr.y_min, zoom, scheme)
    hi_b = tile_to_lonlat_bounds_for_scheme(tr.x_min, tr.y_max, zoom, scheme)
    y_increases_south = lo_b[3] > hi_b[3]

    mosaic = Image.new("RGBA", (len(xs) * 256, len(ys) * 256), (0, 0, 0, 0))
    placed: dict[tuple[int, int], tuple] = {}
    for x in xs:
        for y in ys:
            col = x - tr.x_min
            row = (y - tr.y_min) if y_increases_south else (tr.y_max - y)
            bounds = tile_to_lonlat_bounds_for_scheme(x, y, zoom, scheme)
            placed[(x, y)] = (bounds, col, row)
            tile = _fetch_tile(template.format(z=zoom, x=x, y=y, **fmt_values), headers)
            if tile is not None:
                mosaic.paste(tile, (col * 256, row * 256))

    def to_px(lon: float, lat: float) -> tuple[float, float]:
        for (bounds, col, row) in placed.values():
            mnl, mna, mxl, mxa = bounds
            if mnl - 1e-9 <= lon <= mxl + 1e-9 and mna - 1e-9 <= lat <= mxa + 1e-9:
                fx = (lon - mnl) / (mxl - mnl) if mxl != mnl else 0.0
                fy = (mxa - lat) / (mxa - mna) if mxa != mna else 0.0
                return col * 256 + fx * 256, row * 256 + fy * 256
        return 0.0, 0.0  # corner outside tile union — clamp

    left, top = to_px(bbox.min_lon, bbox.max_lat)
    right, bottom = to_px(bbox.max_lon, bbox.min_lat)
    left, right = sorted((left, right))
    top, bottom = sorted((top, bottom))
    return mosaic.crop((round(left), round(top), round(right), round(bottom)))


def colorize(crop: Image.Image, coverage_from: str, color) -> tuple[Image.Image, float]:
    """Binary coverage mask → a CELL×CELL RGB cell; returns (cell, covered %)."""
    if crop.width < 2 or crop.height < 2:
        return Image.new("RGB", (CELL, CELL), EMPTY), 0.0
    arr = np.array(crop)
    if coverage_from == "non-background":
        mask = np.any(arr[:, :, :3] != arr[0, 0, :3], axis=2)
    else:
        mask = arr[:, :, 3] > 0
    pct = 100.0 * float(mask.sum()) / mask.size
    rgb = np.full((crop.height, crop.width, 3), EMPTY, dtype=np.uint8)
    rgb[mask] = color
    flt = Image.NEAREST if crop.width < CELL else Image.LANCZOS
    return Image.fromarray(rgb).resize((CELL, CELL), flt), pct


def _font(size: int):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def main() -> int:
    ap = argparse.ArgumentParser(description="Juxtapose a provider's coverage overlay across zoom levels.")
    ap.add_argument("--provider", action="append", required=True, help="registered provider key (repeatable)")
    ap.add_argument("--center", nargs=2, type=float, required=True, metavar=("LON", "LAT"))
    ap.add_argument("--extent-km", type=float, required=True, help="square extent side length, km")
    ap.add_argument("--zooms", help="comma-separated source zoom levels (default: per-provider spread)")
    ap.add_argument("--out", default="figures/zoom_samples.png", type=Path)
    args = ap.parse_args()

    bbox = bbox_around(args.center[0], args.center[1], args.extent_km)
    zoom_arg = [int(z) for z in args.zooms.split(",")] if args.zooms else None

    rows = []
    for ci, key in enumerate(args.provider):
        provider = get_provider(key)
        source = provider.sources[0]
        if source.kind != "raster":
            print(f"  skip {key}: source kind is {source.kind!r}; only 'raster' is supported.")
            continue
        runtime = build_runtime_options(
            source, FetchAreaRequest(provider=key, bbox=bbox, output_root=Path("/tmp/zoom_samples"))
        )
        template = runtime.get("tile_template", source.template)
        fmt_values = runtime.get("format_values", {})
        coverage_from = source.options.get("coverage_from", "alpha")
        zooms = zoom_arg or default_zooms(provider, source)
        cells = []
        for z in zooms:
            try:
                crop = render_overlay(template, provider.coordinate_scheme, source.headers, fmt_values, z, bbox)
                cell, pct = colorize(crop, coverage_from, PALETTE[ci % len(PALETTE)])
            except Exception as exc:  # zoom unsupported by this provider's grid, etc.
                cell, pct = Image.new("RGB", (CELL, CELL), EMPTY), None
                print(f"  {key} z{z}: unavailable for {provider.coordinate_scheme} ({exc})")
            else:
                print(f"  {key} z{z}: covered {pct:.0f}%")
            cells.append((z, cell, pct))
        rows.append((key, PALETTE[ci % len(PALETTE)], cells))

    if not rows:
        print("No raster providers to render.")
        return 1

    lbl, gap, provw, pad, title_h = 28, 12, 188, 20, 64
    maxcols = max(len(c) for _, _, c in rows)
    width = pad + provw + maxcols * (CELL + gap) + pad
    height = title_h + pad + len(rows) * (lbl + CELL + gap) + pad
    canvas = Image.new("RGB", (width, height), PANEL)
    draw = ImageDraw.Draw(canvas)
    f_title, f_prov, f_lbl, f_small = _font(23), _font(19), _font(15), _font(13)

    draw.text((pad, 14), "Coverage overlay vs. source zoom  -  fixed "
              f"{args.extent_km:g} km extent, centre {args.center[0]:.4f},{args.center[1]:.4f}",
              fill=(240, 240, 245), font=f_title)
    draw.text((pad, 42), "Every cell is the identical geographic box. Covered = "
              "any non-transparent overlay pixel.", fill=(150, 150, 160), font=f_small)

    for ri, (key, color, cells) in enumerate(rows):
        ry = title_h + pad + ri * (lbl + CELL + gap)
        draw.text((pad, ry + lbl + CELL // 2 - 14), key, fill=(235, 235, 238), font=f_prov)
        draw.rectangle([pad, ry + lbl + CELL // 2 + 12, pad + 14, ry + lbl + CELL // 2 + 26], fill=color)
        for ci, (z, cell, pct) in enumerate(cells):
            cx = pad + provw + ci * (CELL + gap)
            cy = ry + lbl
            canvas.paste(cell, (cx, cy))
            draw.rectangle([cx, cy, cx + CELL - 1, cy + CELL - 1], outline=(95, 95, 105))
            draw.text((cx + 6, ry + 5), f"z{z}", fill=(225, 225, 230), font=f_lbl)
            badge = f"covered {pct:.0f}%" if pct is not None else "zoom n/a"
            draw.rectangle([cx + 4, cy + CELL - 21, cx + 104, cy + CELL - 4], fill=(0, 0, 0))
            draw.text((cx + 8, cy + CELL - 19), badge,
                      fill=(150, 225, 150) if pct is not None else (210, 150, 150), font=f_lbl)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(args.out)
    print(f"saved {args.out}  ({canvas.size[0]}x{canvas.size[1]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
