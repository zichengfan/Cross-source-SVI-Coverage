from __future__ import annotations

from pathlib import Path
from urllib.request import Request, urlopen

from coverage_acquisition.io_utils import (
    ensure_directory,
    sha256_bytes,
    suffix_for_content_type,
    utc_now_iso,
    write_json,
)
from coverage_acquisition.models import DownloadSource, TileCoordinate, TileFetchRequest

USER_AGENT = "global-svi-coverage-observatory/0.2"


def download_file(source: DownloadSource, output_root: Path) -> dict:
    provider_dir = output_root / source.provider
    ensure_directory(provider_dir)

    destination = provider_dir / source.filename
    request = Request(source.url, headers={"User-Agent": USER_AGENT})

    with urlopen(request) as response:
        payload = response.read()
        content_type = response.headers.get("Content-Type", "")

    destination.write_bytes(payload)

    manifest = {
        "provider": source.provider,
        "source_url": source.url,
        "fetched_at": utc_now_iso(),
        "output_path": str(destination),
        "content_type": content_type,
        "sha256": sha256_bytes(payload),
        "byte_length": len(payload),
        "notes": source.notes,
    }
    write_json(provider_dir / "manifest.json", manifest)
    return manifest


def fetch_raster_tiles(request: TileFetchRequest) -> dict:
    ensure_directory(request.output_dir)

    tile_count = 0
    stored_files: list[str] = []

    for x in range(request.x_min, request.x_max + 1):
        for y in range(request.y_min, request.y_max + 1):
            tile = TileCoordinate(z=request.zoom, x=x, y=y)
            url = request.template.format(z=tile.z, x=tile.x, y=tile.y)
            relative_path = tile.relative_path
            destination = request.output_dir / relative_path
            ensure_directory(destination.parent)

            headers = {"User-Agent": USER_AGENT}
            headers.update(request.headers)
            response = Request(url, headers=headers)

            with urlopen(response, timeout=request.timeout_seconds) as opened:
                payload = opened.read()
                content_type = opened.headers.get("Content-Type", "")

            suffix = suffix_for_content_type(content_type, url)
            destination = destination.with_suffix(suffix)
            destination.write_bytes(payload)

            tile_count += 1
            stored_files.append(str(destination))

            write_json(
                destination.with_suffix(".json"),
                {
                    "provider": request.provider,
                    "tile_url": url,
                    "z": tile.z,
                    "x": tile.x,
                    "y": tile.y,
                    "fetched_at": utc_now_iso(),
                    "content_type": content_type,
                    "sha256": sha256_bytes(payload),
                    "byte_length": len(payload),
                },
            )

    manifest = {
        "provider": request.provider,
        "template": request.template,
        "zoom": request.zoom,
        "x_range": [request.x_min, request.x_max],
        "y_range": [request.y_min, request.y_max],
        "tile_count": tile_count,
        "stored_files": stored_files,
        "headers": request.headers,
        "fetched_at": utc_now_iso(),
    }
    write_json(request.output_dir / "manifest.json", manifest)
    return manifest
