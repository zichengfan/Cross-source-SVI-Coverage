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
import json
import math
import os
import sys
from dataclasses import replace as _dc_replace
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/mpl")
# Make the package importable whether or not it is installed in the environment.
_SRC = Path(__file__).resolve().parents[3] / "src"
if _SRC.is_dir():
    sys.path.insert(0, str(_SRC))

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from coverage_acquisition.discovery_kinds.tencent_city_bl import (  # noqa: E402
    tencent_city_bl_discovery,
)
from coverage_acquisition.geo import (  # noqa: E402
    tencent_gcj02_to_pixel,
    tencent_tile_size,
    tile_range_for_bbox,
    tile_to_lonlat_bounds_for_scheme,
    wgs84_to_gcj02,
)
from coverage_acquisition.models import BoundingBox, FetchAreaRequest  # noqa: E402
from coverage_acquisition.mvt_decoder import decode_tile  # noqa: E402
from coverage_acquisition.polite import PolitePolicy, polite_fetch  # noqa: E402
from coverage_acquisition.providers import get_provider  # noqa: E402
from coverage_acquisition.runtime_config import build_runtime_options  # noqa: E402
from coverage_acquisition.source_kinds.tencent_mobile_street import parse_txvn_tile  # noqa: E402

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


def _draw_geometry(draw: ImageDraw.ImageDraw, geom: dict, scale: float, fill, radius=4, width=4) -> bool:
    """Rasterize one MVT geometry (tile-local coords) onto a 256-px tile. True if drawn."""
    gtype = geom.get("type")
    coords = geom.get("coordinates", [])

    def pt(p):
        return (p[0] * scale, p[1] * scale)

    if gtype in ("Point", "MultiPoint"):
        points = [coords] if gtype == "Point" else coords
        for p in points:
            x, y = pt(p)
            draw.ellipse([x - radius, y - radius, x + radius, y + radius], fill=fill)
        return bool(points)
    if gtype in ("LineString", "MultiLineString"):
        lines = [coords] if gtype == "LineString" else coords
        line_w = max(1, int(round(width)))  # ImageDraw.line requires an int width
        drew = False
        for line in lines:
            if len(line) >= 2:
                draw.line([pt(p) for p in line], fill=fill, width=line_w)
                drew = True
        return drew
    if gtype == "Polygon":
        drew = False
        for ring in coords:
            if len(ring) >= 3:
                draw.polygon([pt(p) for p in ring], fill=fill)
                drew = True
        return drew
    return False


def _fetch_vector_tile(
    url: str, headers: dict[str, str], layer_names: tuple[str, ...], zoom: int
) -> Image.Image | None:
    """Fetch an MVT tile and rasterize its coverage geometry to a 256x256 RGBA mask."""
    try:
        payload, _content_type, _status = polite_fetch(
            url, headers=headers, policy=PolitePolicy(timeout_seconds=30)
        )
    except Exception:
        return None  # 404 / network error — treat as an empty (no-coverage) tile
    if not payload:
        return None  # 204 / zero-byte HTTP 200 — the providers' no-coverage signal
    try:
        decoded = decode_tile(payload)
    except Exception:
        return None
    # A tile pixel covers ~2x more ground per zoom down, so scale the point/line
    # pen with the zoom — a fixed ground footprint stays roughly constant on the
    # final figure instead of blobbing in upscaled low-zoom crops.
    pen = max(1.0, min(8.0, 2.5 * 2.0 ** (zoom - 14)))
    img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    fill = (255, 255, 255, 255)
    wanted = set(layer_names) if layer_names else None
    drew = False
    for name, layer in decoded.items():
        if wanted is not None and name not in wanted:
            continue
        scale = 256.0 / int(layer.get("extent", 4096) or 4096)
        for feature in layer.get("features", []):
            if _draw_geometry(draw, feature.get("geometry", {}), scale, fill, radius=pen, width=pen):
                drew = True
    return img if drew else None


def render_overlay(template, scheme, fmt_values, zoom, bbox, fetch) -> Image.Image:
    """Mosaic the provider's tiles at `zoom` and crop to exactly `bbox` (RGBA).

    `fetch(url)` returns a 256x256 RGBA tile image (or None) — raster providers
    decode a PNG, vector providers rasterize the MVT coverage geometry.
    """
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
            tile = fetch(template.format(z=zoom, x=x, y=y, **fmt_values), zoom)
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


def _bbox_to_px(bbox: BoundingBox, width: int, height: int):
    """Linear WGS84 lon/lat -> pixel projector for one fixed extent (north-up)."""
    dlon = bbox.max_lon - bbox.min_lon or 1e-9
    dlat = bbox.max_lat - bbox.min_lat or 1e-9

    def to_px(lon: float, lat: float) -> tuple[float, float]:
        return (lon - bbox.min_lon) / dlon * width, (bbox.max_lat - lat) / dlat * height

    return to_px


def render_tencent_overlay(
    provider, source, bbox: BoundingBox, level: int | None = None, render_px: int = 768
) -> Image.Image:
    """Rasterize Tencent TXVN street-view coverage lines over a fixed WGS84 extent.

    Tencent is not a {z}/{x}/{y} layer — it is the per-city `bl` index over the
    `streetcfg` regions. This reuses the `tencent_city_bl` discovery to find the
    region(s) + `bl` tiles for the extent, fetches the TXVN tiles overlapping it,
    decodes them to WGS84 lines, and burns the lines onto the extent.
    """
    configured_level = int(source.options.get("data_level", "14"))
    level = configured_level if level is None else level
    if level != configured_level:
        # Override data_level so the discovery enumerates at the requested level
        # (its `valid_levels` check still applies).
        source = _dc_replace(source, options={**source.options, "data_level": str(level)})
    tile_size = tencent_tile_size(level)
    request = FetchAreaRequest(provider=provider.key, bbox=bbox, output_root=Path("/tmp/zoom_samples"))
    jobs = tencent_city_bl_discovery(provider, request)

    # The extent in Tencent's GCJ-02 pixel grid, for filtering bl tiles to it.
    px_corners = [
        tencent_gcj02_to_pixel(*wgs84_to_gcj02(bbox.min_lon, bbox.min_lat)),
        tencent_gcj02_to_pixel(*wgs84_to_gcj02(bbox.max_lon, bbox.max_lat)),
    ]
    ex0, ex1 = sorted(p[0] for p in px_corners)
    ey0, ey1 = sorted(p[1] for p in px_corners)

    img = Image.new("RGBA", (render_px, render_px), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    to_px = _bbox_to_px(bbox, render_px, render_px)
    fetched = 0
    for job in jobs:
        idx = int(job["tencent_region"]["idx"])
        for tile in job["tencent_bl_tiles"]:
            ox, oy = tile["origin_px_x"], tile["origin_px_y"]
            if ox + tile_size < ex0 or ox > ex1 or oy + tile_size < ey0 or oy > ey1:
                continue  # bl tile does not overlap the extent
            url = source.template.format(z=level, x=idx, y=tile["bl"])
            try:
                payload, _ct, _st = polite_fetch(
                    url, headers=source.headers, policy=PolitePolicy(timeout_seconds=30)
                )
            except Exception:
                continue
            if not payload:
                continue
            fetched += 1
            try:
                txvn = parse_txvn_tile(payload, tile_origin_px=(ox, oy))
            except Exception:
                continue
            for line in txvn.linestrings:
                pts = [to_px(lon, lat) for lon, lat in line]
                if len(pts) >= 2:
                    draw.line(pts, fill=(255, 255, 255, 255), width=2)
    print(f"    tencent: {fetched} bl tiles fetched over the extent")
    return img


def render_points_overlay(provider, source, bbox: BoundingBox, render_px: int = 768) -> Image.Image:
    """Rasterize a fixed point-list provider (dprk360) — one dot per site in the extent."""
    from urllib.request import urlopen

    with urlopen(source.template) as response:  # file:// URL to the committed points.json
        data = json.loads(response.read().decode("utf-8"))
    img = Image.new("RGBA", (render_px, render_px), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    to_px = _bbox_to_px(bbox, render_px, render_px)
    radius = max(3, render_px // 110)
    drawn = 0
    for pano in data.get("panos", []):
        lon, lat = float(pano["lon"]), float(pano["lat"])
        if not (bbox.min_lon <= lon <= bbox.max_lon and bbox.min_lat <= lat <= bbox.max_lat):
            continue
        x, y = to_px(lon, lat)
        draw.ellipse([x - radius, y - radius, x + radius, y + radius], fill=(255, 255, 255, 255))
        drawn += 1
    print(f"    dprk360: {drawn} sites inside the extent")
    return img, drawn


def _render_tile_row(provider, source, key, bbox, zoom_arg, color):
    """Cells for a raster / vector_mvt provider — one per source zoom level."""
    if source.kind == "raster":
        def fetch(url, zoom, _h=source.headers):
            return _fetch_tile(url, _h)
    else:
        def fetch(url, zoom, _h=source.headers, _ln=source.layer_names):
            return _fetch_vector_tile(url, _h, _ln, zoom)
    runtime = build_runtime_options(
        source, FetchAreaRequest(provider=key, bbox=bbox, output_root=Path("/tmp/zoom_samples"))
    )
    template = runtime.get("tile_template", source.template)
    fmt_values = runtime.get("format_values", {})
    coverage_from = source.options.get("coverage_from", "alpha")
    cells = []
    for z in zoom_arg or default_zooms(provider, source):
        try:
            crop = render_overlay(template, provider.coordinate_scheme, fmt_values, z, bbox, fetch)
            cell, pct = colorize(crop, coverage_from, color)
        except Exception as exc:  # zoom unsupported by this provider's grid, etc.
            cell, pct = Image.new("RGB", (CELL, CELL), EMPTY), None
            print(f"  {key} z{z}: unavailable ({exc})")
        else:
            print(f"  {key} z{z}: covered {pct:.0f}%")
        badge = f"covered {pct:.0f}%" if pct is not None else "n/a"
        cells.append((f"z{z}", cell, badge, pct is not None))
    return cells


def main() -> int:
    ap = argparse.ArgumentParser(description="Juxtapose provider coverage overlays for review.")
    ap.add_argument("--provider", action="append", required=True, help="registered provider key (repeatable)")
    ap.add_argument("--center", action="append", nargs=2, type=float, required=True, metavar=("LON", "LAT"),
                    help="extent centre; repeat to give each provider its own (else shared)")
    ap.add_argument("--extent-km", action="append", type=float, required=True,
                    help="square extent side, km; repeat per provider or give one for all")
    ap.add_argument("--zooms", help="comma-separated source zoom levels (tile providers only)")
    ap.add_argument("--out", default="figures/zoom_samples.png", type=Path)
    ap.add_argument("--title", default="Coverage overlay - binary presence mask")
    args = ap.parse_args()

    zoom_arg = [int(z) for z in args.zooms.split(",")] if args.zooms else None

    def pick(seq, i):
        return seq[i] if i < len(seq) else seq[-1]

    rows = []
    for ci, key in enumerate(args.provider):
        provider = get_provider(key)
        source = provider.sources[0]
        color = PALETTE[ci % len(PALETTE)]
        center = pick(args.center, ci)
        extent_km = pick(args.extent_km, ci)
        bbox = bbox_around(center[0], center[1], extent_km)
        sub = f"{center[0]:.3f},{center[1]:.3f} - {extent_km:g} km"

        if source.kind in ("raster", "vector_mvt"):
            cells = _render_tile_row(provider, source, key, bbox, zoom_arg, color)
        elif source.kind == "tencent_mobile_street":
            # Tencent stores each region's TXVN at one specific data level (the SDK
            # picks per display zoom). In practice the server 404s other levels for
            # a given region, so multi-zoom is not "available" for tencent — render
            # one cell at the configured data_level.
            level = int(source.options.get("data_level", "14"))
            try:
                cell, pct = colorize(
                    render_tencent_overlay(provider, source, bbox, level), "alpha", color
                )
                badge, good = f"covered {pct:.0f}%", True
            except Exception as exc:
                cell, badge, good = Image.new("RGB", (CELL, CELL), EMPTY), "n/a", False
                print(f"  {key} lv{level}: unavailable ({exc})")
            else:
                print(f"  {key} lv{level}: covered {pct:.0f}%")
            cells = [(f"lv{level}", cell, badge, good)]
        elif source.kind == "coverage_json":
            try:
                points_img, site_count = render_points_overlay(provider, source, bbox)
                cell, _pct = colorize(points_img, "alpha", color)
                badge, good = f"{site_count} sites", True
            except Exception as exc:
                cell, badge, good = Image.new("RGB", (CELL, CELL), EMPTY), "n/a", False
                print(f"  {key}: unavailable ({exc})")
            cells = [("sites", cell, badge, good)]
        else:
            print(f"  skip {key}: source kind {source.kind!r} not supported.")
            continue

        rows.append((key, color, sub, cells))

    if not rows:
        print("No supported providers to render.")
        return 1

    lbl, gap, provw, pad, title_h = 28, 12, 212, 20, 64
    maxcols = max(len(c) for _, _, _, c in rows)
    width = pad + provw + maxcols * (CELL + gap) + pad
    height = title_h + pad + len(rows) * (lbl + CELL + gap) + pad
    canvas = Image.new("RGB", (width, height), PANEL)
    draw = ImageDraw.Draw(canvas)
    f_title, f_prov, f_lbl, f_small = _font(23), _font(19), _font(15), _font(13)

    draw.text((pad, 14), args.title, fill=(240, 240, 245), font=f_title)
    draw.text((pad, 42), "Each row is one provider over its own fixed extent; covered = "
              "any non-transparent overlay pixel.", fill=(150, 150, 160), font=f_small)

    for ri, (key, color, sub, cells) in enumerate(rows):
        ry = title_h + pad + ri * (lbl + CELL + gap)
        mid = ry + lbl + CELL // 2
        draw.text((pad, mid - 24), key, fill=(235, 235, 238), font=f_prov)
        draw.rectangle([pad, mid + 2, pad + 14, mid + 16], fill=color)
        draw.text((pad, mid + 24), sub, fill=(140, 140, 150), font=f_small)
        for ci, (clabel, cell, badge, good) in enumerate(cells):
            cx = pad + provw + ci * (CELL + gap)
            cy = ry + lbl
            canvas.paste(cell, (cx, cy))
            draw.rectangle([cx, cy, cx + CELL - 1, cy + CELL - 1], outline=(95, 95, 105))
            draw.text((cx + 6, ry + 5), clabel, fill=(225, 225, 230), font=f_lbl)
            draw.rectangle([cx + 4, cy + CELL - 21, cx + 110, cy + CELL - 4], fill=(0, 0, 0))
            draw.text((cx + 8, cy + CELL - 19), badge,
                      fill=(150, 225, 150) if good else (210, 150, 150), font=f_lbl)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(args.out)
    print(f"saved {args.out}  ({canvas.size[0]}x{canvas.size[1]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
