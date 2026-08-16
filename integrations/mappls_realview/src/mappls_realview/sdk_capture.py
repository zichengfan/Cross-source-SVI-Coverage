from __future__ import annotations

import asyncio
import hashlib
import json
import re
import threading
import urllib.parse
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterator

from .bbox import BBox, tile_bounds, tiles_for_bbox
from .capture import decode_request_url
from .geo import optimize_tile_features, write_feature_collection
from .mvt import decode_pbf_to_features, inspect_pbf

KEY_PLACEHOLDER = "PASTE_YOUR_MAPPLS_STATIC_KEY_HERE"
OUTPUT_MODES = frozenset({"production", "debug"})


@dataclass(frozen=True)
class OutputLayout:
    root: Path
    output_mode: str
    run_id: str
    production_tiles: Path
    production_runs: Path
    debug_run: Path | None

    def tile_path(self, z: int, x: int, y: int) -> Path:
        return self.production_tiles / str(z) / str(x) / f"{y}.geojson.gz"

    @property
    def run_summary_path(self) -> Path:
        return self.production_runs / f"{self.run_id}.json"


def build_output_layout(
    out_dir: str | Path,
    output_mode: str,
    run_id: str | None = None,
) -> OutputLayout:
    """Resolve the only two supported output profiles: production and debug."""
    if output_mode not in OUTPUT_MODES:
        choices = ", ".join(sorted(OUTPUT_MODES))
        raise ValueError(f"output_mode must be one of: {choices}")
    resolved_run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", resolved_run_id):
        raise ValueError("run_id must use only letters, digits, '.', '_' or '-' (max 128 chars)")
    root = Path(out_dir).resolve()
    return OutputLayout(
        root=root,
        output_mode=output_mode,
        run_id=resolved_run_id,
        production_tiles=root / "production" / "tiles",
        production_runs=root / "production" / "runs",
        debug_run=(root / "debug" / "runs" / resolved_run_id if output_mode == "debug" else None),
    )


def _write_json_atomic(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)
    return path


@dataclass(frozen=True)
class LocalWebServer:
    host: str
    port: int

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"


class _QuietStaticHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return


def validate_local_config(web_dir: str | Path) -> Path:
    """Validate that the user populated the ignored Web SDK key file.

    The key is deliberately not returned, logged or copied into Python output.
    It is read only by the local browser page.
    """
    config_path = Path(web_dir) / "config.local.js"
    if not config_path.exists():
        raise FileNotFoundError(
            f"Missing {config_path}. Copy config.example.js to config.local.js and add your Mappls static key."
        )
    text = config_path.read_text(encoding="utf-8")
    key_assignment = re.search(r"accessToken\s*:\s*['\"]([^'\"]+)['\"]", text)
    if KEY_PLACEHOLDER in text or key_assignment is None or not key_assignment.group(1).strip():
        raise ValueError(f"Add your Mappls Web Maps JS static key to {config_path}; the placeholder is still present.")
    return config_path


@contextmanager
def serve_web_directory(
    web_dir: str | Path,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> Iterator[LocalWebServer]:
    """Serve the SDK page over HTTP so Mappls domain/IP restrictions work."""
    directory = Path(web_dir).resolve()
    if not (directory / "index.html").exists():
        raise FileNotFoundError(f"No index.html found in {directory}")
    handler = partial(_QuietStaticHandler, directory=str(directory))
    httpd = ThreadingHTTPServer((host, port), handler)
    server = LocalWebServer(host=host, port=int(httpd.server_address[1]))
    thread = threading.Thread(target=httpd.serve_forever, name="mappls-local-web", daemon=True)
    thread.start()
    try:
        yield server
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def _page_url(base_url: str, bbox: BBox, zoom: int) -> str:
    query = urllib.parse.urlencode(
        {
            "west": bbox.west,
            "south": bbox.south,
            "east": bbox.east,
            "north": bbox.north,
            "zoom": zoom,
        }
    )
    return f"{base_url}/index.html?{query}"


async def capture_sdk_bbox_async(
    *,
    web_dir: str | Path,
    bbox: BBox,
    zoom: int,
    out_dir: str | Path,
    output_mode: str = "production",
    run_id: str | None = None,
    host: str = "127.0.0.1",
    port: int = 8765,
    headless: bool = True,
    tile_wait_seconds: float = 1.5,
    ready_timeout_seconds: float = 60.0,
    chrome_executable: str | None = None,
    screenshot_name: str = "map_realview.png",
) -> dict:
    """Capture authorized RealView coverage into production or debug output.

    The browser page owns the Mappls key and SDK session. Python's preflight
    only verifies that the ignored config no longer contains a placeholder; it
    does not return or log the key. Only responses whose signed URL decodes to
    a canonical XYZ in the requested bbox are retained. Production keeps only
    compressed per-tile GeoJSON and a lean run summary. Debug adds raw PBFs, a
    screenshot, schemas and response diagnostics. This coroutine is safe to
    call with ``await`` from a Jupyter/IPython asyncio event loop.
    """
    bbox.validate()
    if zoom < 0 or zoom > 24:
        raise ValueError("zoom must be in [0, 24]")
    if tile_wait_seconds <= 0:
        raise ValueError("tile_wait_seconds must be positive")

    web_dir = Path(web_dir).resolve()
    validate_local_config(web_dir)
    layout = build_output_layout(out_dir, output_mode, run_id)
    layout.production_tiles.mkdir(parents=True, exist_ok=True)
    layout.production_runs.mkdir(parents=True, exist_ok=True)

    expected = tiles_for_bbox(bbox, zoom)
    expected_set = set(expected)
    successful: dict[tuple[int, int, int], dict] = {}
    attempts: list[dict] = []
    page_errors: list[str] = []
    map_state: dict = {}
    screenshot_path: Path | None = None

    from playwright.async_api import async_playwright

    with TemporaryDirectory(prefix="mappls-realview-pbf-") as temporary_pbf_root:
        if layout.debug_run is not None:
            pbf_dir = layout.debug_run / "pbf"
        else:
            pbf_dir = Path(temporary_pbf_root) / "pbf"
        pbf_dir.mkdir(parents=True, exist_ok=True)

        with serve_web_directory(web_dir, host=host, port=port) as server:
            async with async_playwright() as playwright:
                launch_options: dict = {"headless": headless}
                if chrome_executable:
                    launch_options["executable_path"] = chrome_executable
                browser = await playwright.chromium.launch(**launch_options)
                context = await browser.new_context(viewport={"width": 1600, "height": 1000})
                page = await context.new_page()
                page.on("pageerror", lambda error: page_errors.append(str(error)))
                response_tasks: set[asyncio.Task] = set()

                async def handle_response(response) -> None:
                    request = decode_request_url(
                        response.url,
                        source="sdk-response",
                        digit_profile="auto",
                    )
                    if request is None:
                        return
                    xyz = (request.z, request.x, request.y)
                    if xyz not in expected_set:
                        return

                    row = {
                        "z": request.z,
                        "x": request.x,
                        "y": request.y,
                        "status": response.status,
                        "content_type": response.headers.get("content-type"),
                        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
                        "digit_profile": request.digit_profile,
                    }
                    attempts.append(row)
                    if response.status != 200:
                        return
                    try:
                        body = await response.body()
                        pbf_path = pbf_dir / str(request.z) / str(request.x) / f"{request.y}.pbf"
                        pbf_path.parent.mkdir(parents=True, exist_ok=True)
                        pbf_path.write_bytes(body)
                        schema = inspect_pbf(pbf_path)
                    except Exception as exc:
                        row["error"] = f"{type(exc).__name__}: {exc}"
                        return

                    row.update(
                        {
                            "bytes": len(body),
                            "sha256": hashlib.sha256(body).hexdigest(),
                            "path": str(pbf_path),
                            "schema": schema,
                        }
                    )
                    successful[xyz] = row

                def schedule_response(response) -> None:
                    task = asyncio.create_task(handle_response(response))
                    response_tasks.add(task)
                    task.add_done_callback(response_tasks.discard)

                async def drain_response_tasks() -> None:
                    while response_tasks:
                        await asyncio.gather(*tuple(response_tasks), return_exceptions=True)

                page.on("response", schedule_response)
                try:
                    await page.goto(
                        _page_url(server.base_url, bbox, zoom),
                        wait_until="domcontentloaded",
                    )
                    await page.wait_for_function(
                        "window.captureReady === true || Boolean(window.captureError)",
                        timeout=round(ready_timeout_seconds * 1000),
                    )
                    error = await page.evaluate("window.captureError")
                    if error:
                        raise RuntimeError(str(error))
                    map_state = await page.evaluate("window.realviewCapture.state()")

                    for z, x, y in expected:
                        bounds = tile_bounds(z, x, y)
                        lon = (bounds.west + bounds.east) / 2
                        lat = (bounds.south + bounds.north) / 2
                        await page.evaluate(
                            "([lon, lat, zoom]) => window.realviewCapture.goTo(lon, lat, zoom)",
                            [lon, lat, z],
                        )
                        await page.wait_for_timeout(round(tile_wait_seconds * 1000))

                    await page.wait_for_timeout(round(tile_wait_seconds * 1000))
                    await drain_response_tasks()
                    if layout.debug_run is not None:
                        screenshot_path = layout.debug_run / screenshot_name
                        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                        await page.screenshot(path=str(screenshot_path), full_page=True)
                finally:
                    await drain_response_tasks()
                    await context.close()
                    await browser.close()

        captured = sorted(successful)
        missing = sorted(expected_set - set(captured))
        schemas: dict[str, dict] = {}
        decoded_feature_count = 0
        for z, x, y in captured:
            pbf_path = pbf_dir / str(z) / str(x) / f"{y}.pbf"
            features = decode_pbf_to_features(
                pbf_path,
                z,
                x,
                y,
                geometry_types={"LineString", "MultiLineString"},
            )
            production_features = optimize_tile_features(features, coordinate_precision=7)
            write_feature_collection(
                production_features,
                layout.tile_path(z, x, y),
                atomic=True,
            )
            decoded_feature_count += len(production_features)
            schemas[f"{z}/{x}/{y}.pbf"] = successful[(z, x, y)]["schema"]

    failed_tiles: list[dict] = []
    for z, x, y in missing:
        matching = [row for row in attempts if (row["z"], row["x"], row["y"]) == (z, x, y)]
        last = matching[-1] if matching else {}
        failed = {"z": z, "x": x, "y": y, "http_status": last.get("status")}
        if last.get("error"):
            failed["error"] = last["error"]
        failed_tiles.append(failed)

    warning = (
        "A failed tile means missing from this SDK capture, not necessarily no RealView coverage." if missing else None
    )
    summary = {
        "schema_version": 1,
        "run_id": layout.run_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "capture_source": "authorized local Mappls Web Maps JS v3.0 page",
        "output_mode": layout.output_mode,
        "bbox": bbox.as_list(),
        "zoom": zoom,
        "expected_tile_count": len(expected),
        "captured_tile_count": len(captured),
        "failed_tile_count": len(missing),
        "decoded_feature_count": decoded_feature_count,
        "tile_format": "GeoJSON FeatureCollection, EPSG:4326, gzip",
        "tile_path_template": "production/tiles/{z}/{x}/{y}.geojson.gz",
        "coordinate_precision": 7,
        "removed_redundant_properties": ["_tile_z", "_tile_x", "_tile_y", "_mvt_layer"],
        "failed_tiles": failed_tiles,
        "page_error_count": len(page_errors),
        "warning": warning,
    }
    _write_json_atomic(layout.run_summary_path, summary)

    result = dict(summary)
    result["run_summary"] = str(layout.run_summary_path)
    if layout.debug_run is not None:
        debug_manifest = {
            **summary,
            "map_state": map_state,
            "screenshot": str(screenshot_path) if screenshot_path else None,
            "response_attempts": attempts,
            "page_errors": page_errors,
            "schema": schemas,
        }
        debug_manifest_path = _write_json_atomic(layout.debug_run / "manifest.json", debug_manifest)
        result["debug_manifest"] = str(debug_manifest_path)
        result["screenshot"] = str(screenshot_path) if screenshot_path else None
    return result


def capture_sdk_bbox(
    *,
    web_dir: str | Path,
    bbox: BBox,
    zoom: int,
    out_dir: str | Path,
    output_mode: str = "production",
    run_id: str | None = None,
    host: str = "127.0.0.1",
    port: int = 8765,
    headless: bool = True,
    tile_wait_seconds: float = 1.5,
    ready_timeout_seconds: float = 60.0,
    chrome_executable: str | None = None,
    screenshot_name: str = "map_realview.png",
) -> dict:
    """Synchronous wrapper for CLI/non-async callers.

    Jupyter already runs an asyncio loop, so notebooks must instead call
    ``await capture_sdk_bbox_async(...)``.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(
            capture_sdk_bbox_async(
                web_dir=web_dir,
                bbox=bbox,
                zoom=zoom,
                out_dir=out_dir,
                output_mode=output_mode,
                run_id=run_id,
                host=host,
                port=port,
                headless=headless,
                tile_wait_seconds=tile_wait_seconds,
                ready_timeout_seconds=ready_timeout_seconds,
                chrome_executable=chrome_executable,
                screenshot_name=screenshot_name,
            )
        )
    raise RuntimeError(
        "capture_sdk_bbox() cannot run inside an active asyncio loop; use: await capture_sdk_bbox_async(...)"
    )
