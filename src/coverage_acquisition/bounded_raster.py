from __future__ import annotations

import contextlib
import csv
import hashlib
import io
import json
import os
import statistics
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Iterable

import requests
from PIL import Image
from shapely.geometry import box, shape
from shapely.geometry.base import BaseGeometry

from coverage_acquisition.geo import tile_range_for_bbox, tile_to_lonlat_bounds_for_scheme
from coverage_acquisition.models import BoundingBox
from coverage_acquisition.naver_frontend import (
    NAVER_BASIC_STYLE_JSONP_URL,
    NAVER_STREET_ONLY_OVERLAY_TYPE,
    parse_jsonp_payload,
)
from coverage_acquisition.providers import get_provider

SUPPORTED_RASTER_PROVIDERS = ("naver", "kakao", "mapy")
TERMINAL_STATUSES = frozenset({"present", "decoded_empty"})
RETRYABLE_STATUSES = frozenset({"missing", "error"})


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def manifest_sha256(manifest: dict[str, Any]) -> str:
    comparable = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    return hashlib.sha256(_canonical_json_bytes(comparable)).hexdigest()


def validate_tile_manifest(manifest: dict[str, Any]) -> None:
    provider = str(manifest.get("provider", ""))
    if provider not in SUPPORTED_RASTER_PROVIDERS:
        raise ValueError(f"Unsupported bounded raster provider: {provider!r}")
    tiles = manifest.get("tiles")
    if not isinstance(tiles, list) or not tiles:
        raise ValueError("Tile manifest must contain a non-empty tiles list.")
    keys = [(int(row["level"]), int(row["x"]), int(row["y"])) for row in tiles]
    if len(keys) != len(set(keys)):
        raise ValueError("Tile manifest contains duplicate level/x/y coordinates.")
    expected = manifest_sha256(manifest)
    recorded = manifest.get("manifest_sha256")
    if recorded and recorded != expected:
        raise ValueError("Tile manifest checksum does not match its content.")


def write_immutable_manifest(path: Path, manifest: dict[str, Any]) -> Path:
    manifest = dict(manifest)
    manifest["manifest_sha256"] = manifest_sha256(manifest)
    validate_tile_manifest(manifest)
    if path.exists():
        current = json.loads(path.read_text(encoding="utf-8"))
        if current != manifest:
            raise FileExistsError(f"Refusing to replace a different immutable manifest: {path}")
        return path
    _atomic_write_json(path, manifest)
    return path


def load_tile_manifest(path: Path) -> dict[str, Any]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    validate_tile_manifest(manifest)
    return manifest


def _as_wgs84_geometry(geometry: BaseGeometry | dict[str, Any]) -> BaseGeometry:
    result = shape(geometry) if isinstance(geometry, dict) else geometry
    if result.is_empty:
        raise ValueError("Acquisition polygon is empty.")
    if not result.is_valid:
        result = result.buffer(0)
    if result.is_empty or not result.is_valid:
        raise ValueError("Acquisition polygon could not be repaired.")
    return result


def _tile_polygon(provider: str, level: int, x: int, y: int) -> BaseGeometry:
    coordinate_scheme = get_provider(provider).coordinate_scheme
    west, south, east, north = tile_to_lonlat_bounds_for_scheme(
        x=x,
        y=y,
        zoom=level,
        coordinate_scheme=coordinate_scheme,
    )
    return box(west, south, east, north)


def _clamp_web_mercator_tile(level: int, x: int, y: int) -> tuple[int, int] | None:
    limit = 2**level
    if not (0 <= x < limit and 0 <= y < limit):
        return None
    return x, y


def build_polygon_tile_manifest(
    *,
    provider: str,
    region_id: str,
    geometry_wgs84: BaseGeometry | dict[str, Any],
    level: int,
    halo_tiles: int = 1,
) -> dict[str, Any]:
    """Build a deterministic WGS84 polygon-masked tile manifest.

    The polygon itself is never stored in the manifest; only its SHA256 and bounds
    are retained. Tiles intersecting the polygon are selected first, then a native
    one-tile (or configured) halo is added.
    """

    if provider not in SUPPORTED_RASTER_PROVIDERS:
        raise ValueError(f"provider must be one of {SUPPORTED_RASTER_PROVIDERS}")
    if halo_tiles < 0:
        raise ValueError("halo_tiles must be non-negative")
    geometry = _as_wgs84_geometry(geometry_wgs84)
    provider_definition = get_provider(provider)
    source = provider_definition.sources[0]
    min_lon, min_lat, max_lon, max_lat = geometry.bounds
    tile_range = tile_range_for_bbox(
        BoundingBox(min_lon=min_lon, min_lat=min_lat, max_lon=max_lon, max_lat=max_lat),
        level,
        provider_definition.coordinate_scheme,
    )

    intersecting: set[tuple[int, int]] = set()
    for x in range(tile_range.x_min, tile_range.x_max + 1):
        for y in range(tile_range.y_min, tile_range.y_max + 1):
            if _tile_polygon(provider, level, x, y).intersects(geometry):
                intersecting.add((x, y))
    if not intersecting:
        raise ValueError("No source tiles intersect the acquisition polygon.")

    selected: set[tuple[int, int]] = set()
    for x, y in intersecting:
        for dx in range(-halo_tiles, halo_tiles + 1):
            for dy in range(-halo_tiles, halo_tiles + 1):
                candidate = (x + dx, y + dy)
                if provider_definition.coordinate_scheme == "web_mercator":
                    candidate = _clamp_web_mercator_tile(level, *candidate)
                    if candidate is None:
                        continue
                selected.add(candidate)

    geometry_fingerprint = hashlib.sha256(geometry.wkb).hexdigest()
    tiles = [
        {
            "provider": provider,
            "source_id": source.id,
            "coordinate_scheme": provider_definition.coordinate_scheme,
            "level": int(level),
            "x": int(x),
            "y": int(y),
        }
        for x, y in sorted(selected)
    ]
    manifest: dict[str, Any] = {
        "schema_version": 1,
        "provider": provider,
        "source_id": source.id,
        "region_id": region_id,
        "coordinate_scheme": provider_definition.coordinate_scheme,
        "level": int(level),
        "halo_tiles": int(halo_tiles),
        "geometry_wgs84_bounds": [float(value) for value in geometry.bounds],
        "geometry_wkb_sha256": geometry_fingerprint,
        "intersecting_tile_count": len(intersecting),
        "tile_count": len(tiles),
        "tiles": tiles,
    }
    manifest["manifest_sha256"] = manifest_sha256(manifest)
    validate_tile_manifest(manifest)
    return manifest


def deterministic_roi_sample_manifest(
    full_manifest: dict[str, Any],
    *,
    rois: Iterable[tuple[str, BaseGeometry | dict[str, Any]]],
    per_roi: int = 100,
) -> dict[str, Any]:
    """Select exactly ``per_roi`` unique manifest tiles for every named ROI."""

    validate_tile_manifest(full_manifest)
    if per_roi < 1:
        raise ValueError("per_roi must be positive")
    provider = str(full_manifest["provider"])
    level = int(full_manifest["level"])
    chosen: list[dict[str, Any]] = []
    chosen_keys: set[tuple[int, int, int]] = set()
    strata: list[dict[str, Any]] = []

    for roi_name, roi_geometry in rois:
        geometry = _as_wgs84_geometry(roi_geometry)
        candidates = []
        for row in full_manifest["tiles"]:
            key = (int(row["level"]), int(row["x"]), int(row["y"]))
            if key in chosen_keys:
                continue
            if not _tile_polygon(provider, level, key[1], key[2]).intersects(geometry):
                continue
            rank = hashlib.sha256(f"{provider}:{level}:{key[1]}:{key[2]}:{roi_name}".encode("utf-8")).hexdigest()
            candidates.append((rank, row))
        candidates.sort(key=lambda item: item[0])
        if len(candidates) < per_roi:
            raise ValueError(f"ROI {roi_name!r} contains only {len(candidates)} unused tiles; {per_roi} are required.")
        selected_rows = []
        for _, row in candidates[:per_roi]:
            copied = dict(row)
            copied["sample_stratum"] = roi_name
            selected_rows.append(copied)
            chosen_keys.add((int(row["level"]), int(row["x"]), int(row["y"])))
        chosen.extend(selected_rows)
        strata.append({"name": roi_name, "tile_count": len(selected_rows)})

    sample = {
        "schema_version": 1,
        "provider": provider,
        "source_id": full_manifest["source_id"],
        "region_id": f"{full_manifest['region_id']}_stability_sample",
        "coordinate_scheme": full_manifest["coordinate_scheme"],
        "level": level,
        "halo_tiles": 0,
        "parent_manifest_sha256": full_manifest["manifest_sha256"],
        "sample_method": "sha256_rank_without_replacement",
        "sample_strata": strata,
        "tile_count": len(chosen),
        "tiles": sorted(chosen, key=lambda row: (row["sample_stratum"], row["x"], row["y"])),
    }
    sample["manifest_sha256"] = manifest_sha256(sample)
    validate_tile_manifest(sample)
    return sample


class GlobalStartLimiter:
    """Serialize request starts across workers for one provider."""

    def __init__(
        self,
        interval_seconds: float,
        *,
        monotonic: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if interval_seconds < 0:
            raise ValueError("interval_seconds must be non-negative")
        self.interval_seconds = float(interval_seconds)
        self._monotonic = monotonic
        self._sleep = sleep
        self._lock = threading.Lock()
        self._next_start = 0.0

    def wait(self) -> float:
        with self._lock:
            now = self._monotonic()
            scheduled = max(now, self._next_start)
            delay = scheduled - now
            if delay > 0:
                self._sleep(delay)
            actual = self._monotonic()
            self._next_start = max(scheduled, actual) + self.interval_seconds
            return actual


@contextlib.contextmanager
def exclusive_file_lock(path: Path, owner_label: str):
    """Acquire a non-blocking POSIX file lock and record its owner."""

    import fcntl

    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+", encoding="utf-8")
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            handle.seek(0)
            owner = handle.read().strip()
            raise RuntimeError(f"Acquisition lock is already held: {path}. {owner}") from exc
        handle.seek(0)
        handle.truncate()
        handle.write(json.dumps({"owner": owner_label, "pid": os.getpid(), "acquired_at": utc_now_iso()}))
        handle.flush()
        yield
    finally:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def _new_direct_session(session_factory: Callable[[], requests.Session]) -> requests.Session:
    session = session_factory()
    session.trust_env = False
    return session


def resolve_raster_runtime_config(
    provider: str,
    *,
    session_factory: Callable[[], requests.Session] = requests.Session,
    timeout: tuple[float, float] = (10.0, 60.0),
) -> dict[str, Any]:
    """Resolve a provider template once with a direct, explicitly closed Session."""

    definition = get_provider(provider)
    source = definition.sources[0]
    session = _new_direct_session(session_factory)
    try:
        if provider == "naver":
            response = session.get(NAVER_BASIC_STYLE_JSONP_URL, headers=source.headers, timeout=timeout)
            response.raise_for_status()
            metadata = parse_jsonp_payload(response.text)
            version = str(metadata["version"])
            template = str(metadata["tiles"][0]) + f"?mt={NAVER_STREET_ONLY_OVERLAY_TYPE}"
            frontend = {
                "config_source": "live_style_metadata",
                "version": version,
                "street_layer_air_water_control": "StreetLayer.setAirWaterView(false)",
                "street_layer_air_water_control_scope": "GL frontend maps pr to ps",
                "consumer_toggle_class": "btn_panorama_toggle",
                "overlay_type_when_enabled": "pr",
                "overlay_type_when_disabled": NAVER_STREET_ONLY_OVERLAY_TYPE,
                "overlay_type": NAVER_STREET_ONLY_OVERLAY_TYPE,
                "air_water_icons_visible": False,
            }
            evidence_scope = "street_panorama_lines_only"
        elif provider == "kakao":
            from coverage_acquisition.kakao_frontend import (
                KAKAO_MAP_SDK_LOADER_URL,
                _extract_resource_paths,
                _extract_runtime_bundle_versions,
                _extract_uri_templates,
            )

            response = session.get(KAKAO_MAP_SDK_LOADER_URL, headers=source.headers, timeout=timeout)
            response.raise_for_status()
            templates = _extract_uri_templates(response.text)
            template = templates["ROADVIEW_HD"]
            frontend = {
                "config_source": "live_sdk_loader",
                "sdk_loader_url": KAKAO_MAP_SDK_LOADER_URL,
                "runtime_bundle_versions": _extract_runtime_bundle_versions(response.text),
                "resource_paths": _extract_resource_paths(response.text),
            }
            evidence_scope = "roadview_coverage_overlay"
        elif provider == "mapy":
            template = source.template
            frontend = {"config_source": "fixed_provider_definition"}
            evidence_scope = "panorama_coverage_overlay"
        else:
            raise ValueError(f"Unsupported raster provider: {provider}")
    finally:
        session.close()
    return {
        "provider": provider,
        "source_id": source.id,
        "template": template,
        "headers": dict(source.headers),
        "frontend": frontend,
        "evidence_scope": evidence_scope,
        "resolved_at": utc_now_iso(),
    }


def download_file_with_manifest(
    *,
    url: str,
    output_path: Path,
    source_page: str,
    license_name: str,
    session_factory: Callable[[], requests.Session] = requests.Session,
    timeout: tuple[float, float] = (10.0, 120.0),
    expected_kind: str | None = None,
) -> dict[str, Any]:
    """Stream one context file, validate its payload, and retain provenance."""

    session = _new_direct_session(session_factory)
    try:
        with session.get(url, timeout=timeout, stream=True, allow_redirects=True) as response:
            response.raise_for_status()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = output_path.with_name(f".{output_path.name}.{os.getpid()}.tmp")
            digest = hashlib.sha256()
            byte_count = 0
            try:
                with temporary.open("wb") as handle:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if not chunk:
                            continue
                        handle.write(chunk)
                        digest.update(chunk)
                        byte_count += len(chunk)
                validate_downloaded_file(temporary, expected_kind=expected_kind)
                os.replace(temporary, output_path)
            finally:
                temporary.unlink(missing_ok=True)
            record = {
                "url": url,
                "final_url": response.url,
                "source_page": source_page,
                "license": license_name,
                "output_path": str(output_path),
                "bytes": byte_count,
                "sha256": digest.hexdigest(),
                "etag": response.headers.get("ETag", ""),
                "last_modified": response.headers.get("Last-Modified", ""),
                "content_type": response.headers.get("Content-Type", ""),
                "expected_kind": expected_kind or "unspecified",
                "downloaded_at": utc_now_iso(),
                "session_trust_env": False,
            }
    finally:
        session.close()
    _atomic_write_json(Path(str(output_path) + ".download.json"), record)
    return record


def _payload_description(path: Path) -> str:
    with path.open("rb") as handle:
        prefix = handle.read(512).lstrip().lower()
    if prefix.startswith((b"<!doctype html", b"<html")) or b"<html" in prefix:
        return "HTML (probably a product or error page)"
    return f"an unrecognized payload beginning with {prefix[:24]!r}"


def validate_downloaded_file(path: Path, *, expected_kind: str | None) -> None:
    """Reject mislabeled HTML and verify signatures used by notebook 0008."""

    if expected_kind is None:
        return
    if expected_kind == "zip":
        valid = zipfile.is_zipfile(path)
    elif expected_kind == "gpkg":
        with path.open("rb") as handle:
            valid = handle.read(16) == b"SQLite format 3\x00"
    elif expected_kind == "csv":
        with path.open("rb") as handle:
            prefix = handle.read(4096).lstrip().lower()
        valid = bool(prefix) and not prefix.startswith((b"<!doctype html", b"<html"))
    else:
        raise ValueError(f"Unsupported expected download kind: {expected_kind!r}")
    if not valid:
        raise ValueError(
            f"Downloaded payload is not a valid {expected_kind.upper()}: {path}. "
            f"The server returned {_payload_description(path)}. Use a direct distribution URL."
        )


def safe_extract_zip(archive: Path, destination: Path) -> None:
    """Extract a verified ZIP while rejecting path-traversal members."""

    validate_downloaded_file(archive, expected_kind="zip")
    destination.mkdir(parents=True, exist_ok=True)
    resolved_destination = destination.resolve()
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            target = (destination / member.filename).resolve()
            if resolved_destination not in target.parents and target != resolved_destination:
                raise ValueError(f"Unsafe ZIP member: {member.filename}")
        bundle.extractall(destination)


class _HTMLTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._table_depth = 0
        self._table: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell_parts: list[str] | None = None

    def handle_starttag(self, tag: str, _attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "table":
            if self._table_depth == 0:
                self._table = []
            self._table_depth += 1
        elif self._table_depth == 1 and tag == "tr":
            self._row = []
        elif self._table_depth == 1 and tag in {"th", "td"} and self._row is not None:
            self._cell_parts = []

    def handle_data(self, data: str) -> None:
        if self._cell_parts is not None:
            self._cell_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self._table_depth == 1 and tag in {"th", "td"} and self._cell_parts is not None:
            assert self._row is not None
            self._row.append(" ".join("".join(self._cell_parts).split()))
            self._cell_parts = None
        elif self._table_depth == 1 and tag == "tr" and self._row is not None:
            if self._row and self._table is not None:
                self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._table_depth:
            self._table_depth -= 1
            if self._table_depth == 0 and self._table:
                self.tables.append(self._table)
                self._table = None


def _m49_tables(html: str) -> list[Any]:
    import pandas as pd

    required = {"ISO-alpha3 Code", "Region Name", "Sub-region Name"}
    parser = _HTMLTableParser()
    parser.feed(html)
    candidates = []
    for rows in parser.tables:
        header_index = next(
            (index for index, row in enumerate(rows) if required.issubset(row)),
            None,
        )
        if header_index is None:
            continue
        header = rows[header_index]
        records = [(row + [""] * len(header))[: len(header)] for row in rows[header_index + 1 :] if any(row)]
        candidates.append(pd.DataFrame(records, columns=header))
    return candidates


def _select_english_m49_table(candidates: list[Any]) -> Any:
    english = [
        table
        for table in candidates
        if "Global Name" in table.columns
        and table["Global Name"].astype(str).eq("World").any()
        and table["Region Name"].astype(str).eq("Africa").any()
    ]
    if len(english) != 1:
        raise ValueError(
            "Expected exactly one English UN M49 table identified by Global Name='World' "
            f"and Region Name='Africa'; found {len(english)} among {len(candidates)} tables."
        )
    return english[0]


def _cache_un_m49_table(table: Any, output_path: Path) -> tuple[str, int]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(f".{output_path.name}.{os.getpid()}.tmp")
    try:
        table.to_csv(temporary, index=False)
        validate_downloaded_file(temporary, expected_kind="csv")
        digest = hashlib.sha256(temporary.read_bytes()).hexdigest()
        byte_count = temporary.stat().st_size
        os.replace(temporary, output_path)
    finally:
        temporary.unlink(missing_ok=True)
    return digest, byte_count


def recover_un_m49_csv_from_cached_html(
    *,
    cached_html_path: Path,
    source_page: str,
    license_name: str,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Recover the official UN M49 CSV from a previously cached HTML page."""

    raw_html = cached_html_path.read_text(encoding="utf-8", errors="replace")
    source_response_bytes = len(raw_html.encode("utf-8"))
    candidates = _m49_tables(raw_html)
    table = _select_english_m49_table(candidates)
    destination = cached_html_path if output_path is None else output_path
    digest, byte_count = _cache_un_m49_table(table, destination)
    record = {
        "url": source_page,
        "final_url": source_page,
        "source_page": source_page,
        "license": license_name,
        "output_path": str(destination),
        "bytes": byte_count,
        "sha256": digest,
        "source_response_bytes": source_response_bytes,
        "etag": "",
        "last_modified": "",
        "content_type": "text/html",
        "transformation": "recovered CSV from previously cached official M49 HTML page",
        "downloaded_at": utc_now_iso(),
        "session_trust_env": False,
    }
    _atomic_write_json(Path(str(destination) + ".download.json"), record)
    return record


def download_un_m49_csv(
    *,
    url: str,
    output_path: Path,
    source_page: str,
    license_name: str,
    session_factory: Callable[[], requests.Session] = requests.Session,
    timeout: tuple[float, float] = (10.0, 120.0),
) -> dict[str, Any]:
    """Parse the official UN M49 HTML table and cache a validated CSV."""

    session = _new_direct_session(session_factory)
    try:
        response = session.get(url, timeout=timeout, allow_redirects=True)
        response.raise_for_status()
        candidates = _m49_tables(response.text)
        table = _select_english_m49_table(candidates)
        digest, byte_count = _cache_un_m49_table(table, output_path)
        record = {
            "url": url,
            "final_url": response.url,
            "source_page": source_page,
            "license": license_name,
            "output_path": str(output_path),
            "bytes": byte_count,
            "sha256": digest,
            "source_response_bytes": len(response.content),
            "etag": response.headers.get("ETag", ""),
            "last_modified": response.headers.get("Last-Modified", ""),
            "content_type": response.headers.get("Content-Type", ""),
            "transformation": "standard-library HTML table parse of official M49 page to CSV",
            "downloaded_at": utc_now_iso(),
            "session_trust_env": False,
        }
    finally:
        session.close()
    _atomic_write_json(Path(str(output_path) + ".download.json"), record)
    return record


def download_geoboundary_adm0(
    *,
    iso3: str,
    output_path: Path,
    session_factory: Callable[[], requests.Session] = requests.Session,
    timeout: tuple[float, float] = (10.0, 120.0),
) -> dict[str, Any]:
    """Resolve and download one current geoBoundaries open ADM0 GeoJSON."""

    iso3 = iso3.upper()
    api_url = f"https://www.geoboundaries.org/api/current/gbOpen/{iso3}/ADM0/"
    session = _new_direct_session(session_factory)
    try:
        metadata_response = session.get(api_url, timeout=timeout)
        metadata_response.raise_for_status()
        metadata = metadata_response.json()
        download_url = metadata["gjDownloadURL"]
    finally:
        session.close()
    record = download_file_with_manifest(
        url=download_url,
        output_path=output_path,
        source_page="https://www.geoboundaries.org/globalDownloads.html",
        license_name="CC BY 4.0",
        session_factory=session_factory,
        timeout=timeout,
    )
    record["geoboundaries_api_url"] = api_url
    record["iso3"] = iso3
    _atomic_write_json(Path(str(output_path) + ".download.json"), record)
    return record


def _tile_url(template: str, row: dict[str, Any]) -> str:
    level = int(row["level"])
    x = int(row["x"])
    y = int(row["y"])
    return template.format(level=level, tile_x=x, tile_y=y, z=level, x=x, y=y)


def _tile_paths(output_root: Path, manifest: dict[str, Any], row: dict[str, Any]) -> tuple[Path, Path]:
    base = output_root / str(manifest["provider"]) / str(manifest["region_id"]) / str(row["level"]) / str(row["x"])
    tile_path = base / f"{row['y']}.png"
    metadata_path = base / f"{row['y']}.png.metadata.json"
    return tile_path, metadata_path


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        temporary.write_bytes(payload)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_write_json(path: Path, payload: Any) -> None:
    content = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8")
    _atomic_write_bytes(path, content)


def _png_alpha_summary(payload: bytes) -> dict[str, int | float]:
    with Image.open(io.BytesIO(payload)) as image:
        rgba = image.convert("RGBA")
        alpha = rgba.getchannel("A")
        histogram = alpha.histogram()
        empty_pixels = int(histogram[0])
        total_pixels = int(rgba.width * rgba.height)
        coverage_pixels = total_pixels - empty_pixels
        return {
            "width": int(rgba.width),
            "height": int(rgba.height),
            "coverage_pixel_count": coverage_pixels,
            "total_pixel_count": total_pixels,
            "coverage_ratio": coverage_pixels / total_pixels if total_pixels else 0.0,
        }


def _existing_status(metadata_path: Path) -> str:
    if not metadata_path.exists():
        return "missing"
    try:
        return str(json.loads(metadata_path.read_text(encoding="utf-8")).get("status", "error"))
    except (OSError, json.JSONDecodeError):
        return "error"


@dataclass(frozen=True)
class RasterPassConfig:
    max_workers: int = 2
    start_interval_seconds: float = 1.0
    connect_timeout_seconds: float = 10.0
    read_timeout_seconds: float = 60.0

    def validate(self) -> None:
        if self.max_workers != 2:
            raise ValueError("The approved bounded-raster configuration requires exactly 2 workers per provider.")
        if self.start_interval_seconds != 1.0:
            raise ValueError("The approved bounded-raster configuration requires a 1.0 second provider interval.")


def _fetch_one_tile(
    *,
    session: requests.Session,
    limiter: GlobalStartLimiter,
    runtime_config: dict[str, Any],
    manifest: dict[str, Any],
    row: dict[str, Any],
    output_root: Path,
    timeout: tuple[float, float],
) -> dict[str, Any]:
    provider = str(manifest["provider"])
    tile_path, metadata_path = _tile_paths(output_root, manifest, row)
    url = _tile_url(str(runtime_config["template"]), row)
    started_monotonic = limiter.wait()
    started_at = utc_now_iso()
    timer = time.perf_counter()
    record: dict[str, Any] = {
        **row,
        "provider": provider,
        "url": url,
        "request_started_at": started_at,
        "request_started_monotonic": started_monotonic,
        "manifest_sha256": manifest["manifest_sha256"],
        "runtime_config_sha256": hashlib.sha256(_canonical_json_bytes(runtime_config)).hexdigest(),
        "status": "error",
        "output_path": str(tile_path),
        "metadata_path": str(metadata_path),
    }
    try:
        response = session.get(
            url,
            headers=runtime_config["headers"],
            timeout=timeout,
            allow_redirects=True,
        )
        record["elapsed_seconds"] = time.perf_counter() - timer
        record["http_status"] = int(response.status_code)
        record["content_type"] = response.headers.get("Content-Type", "")
        record["etag"] = response.headers.get("ETag", "")
        record["last_modified"] = response.headers.get("Last-Modified", "")
        response.raise_for_status()
        if not record["content_type"].lower().startswith("image/"):
            raise ValueError(f"Unexpected content type: {record['content_type']!r}")
        payload = response.content
        alpha = _png_alpha_summary(payload)
        record.update(alpha)
        record["payload_bytes"] = len(payload)
        record["payload_sha256"] = hashlib.sha256(payload).hexdigest()
        record["status"] = "present" if alpha["coverage_pixel_count"] else "decoded_empty"
        _atomic_write_bytes(tile_path, payload)
    except Exception as exc:  # retained as an auditable retryable record
        record.setdefault("elapsed_seconds", time.perf_counter() - timer)
        record["error_type"] = type(exc).__name__
        record["error"] = str(exc)[:1000]
    record["completed_at"] = utc_now_iso()
    _atomic_write_json(metadata_path, record)
    return record


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return float(values[0])
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return float(ordered[lower] * (1 - fraction) + ordered[upper] * fraction)


def summarize_stability_pass(
    records: list[dict[str, Any]],
    *,
    expected_interval_seconds: float = 1.0,
) -> dict[str, Any]:
    attempted = len(records)
    durations = [float(row["elapsed_seconds"]) for row in records if "elapsed_seconds" in row]
    halfway = max(1, attempted // 2)
    first = [float(row["elapsed_seconds"]) for row in records[:halfway] if "elapsed_seconds" in row]
    second = [float(row["elapsed_seconds"]) for row in records[halfway:] if "elapsed_seconds" in row]
    starts = sorted(float(row["request_started_monotonic"]) for row in records)
    intervals = [later - earlier for earlier, later in zip(starts, starts[1:])]
    error_count = sum(row.get("status") == "error" for row in records)
    throttled_count = sum(int(row.get("http_status", 0) or 0) in {403, 429} for row in records)
    first_p95 = _percentile(first, 0.95)
    second_p95 = _percentile(second, 0.95)
    latency_ratio = None
    if first_p95 is not None and second_p95 is not None:
        latency_ratio = second_p95 / max(first_p95, 1e-9)
    min_interval = min(intervals) if intervals else None
    error_rate = error_count / attempted if attempted else 1.0
    accepted = bool(
        attempted
        and error_rate < 0.01
        and throttled_count == 0
        and (latency_ratio is None or latency_ratio <= 2.0)
        and (min_interval is None or min_interval >= expected_interval_seconds - 0.01)
    )
    return {
        "attempted_tile_count": attempted,
        "present_tile_count": sum(row.get("status") == "present" for row in records),
        "decoded_empty_tile_count": sum(row.get("status") == "decoded_empty" for row in records),
        "error_tile_count": error_count,
        "error_rate": error_rate,
        "http_403_or_429_count": throttled_count,
        "latency_p50_seconds": _percentile(durations, 0.50),
        "latency_p95_seconds": _percentile(durations, 0.95),
        "first_half_p95_seconds": first_p95,
        "second_half_p95_seconds": second_p95,
        "second_to_first_p95_ratio": latency_ratio,
        "minimum_request_start_interval_seconds": min_interval,
        "mean_payload_bytes": statistics.fmean([float(row.get("payload_bytes", 0)) for row in records])
        if records
        else None,
        "accepted_for_full_acquisition": accepted,
    }


def fetch_raster_manifest_pass(
    manifest_or_path: dict[str, Any] | Path,
    *,
    output_root: Path,
    runtime_config: dict[str, Any] | None = None,
    pass_config: RasterPassConfig = RasterPassConfig(),
    session_factory: Callable[[], requests.Session] = requests.Session,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Run one manual, resumable pass for a single provider manifest."""

    pass_config.validate()
    manifest = load_tile_manifest(manifest_or_path) if isinstance(manifest_or_path, Path) else dict(manifest_or_path)
    validate_tile_manifest(manifest)
    provider = str(manifest["provider"])
    runtime_config = runtime_config or resolve_raster_runtime_config(
        provider,
        session_factory=session_factory,
        timeout=(pass_config.connect_timeout_seconds, pass_config.read_timeout_seconds),
    )
    if runtime_config.get("provider") != provider:
        raise ValueError("Runtime config provider does not match the tile manifest.")

    pending = []
    for row in manifest["tiles"]:
        _, metadata_path = _tile_paths(output_root, manifest, row)
        if _existing_status(metadata_path) in RETRYABLE_STATUSES:
            pending.append(row)

    def notify_progress(event: str, completed: int, status_counts: dict[str, int]) -> None:
        if progress_callback is not None:
            try:
                progress_callback(
                    {
                        "event": event,
                        "provider": provider,
                        "region_id": manifest["region_id"],
                        "completed": completed,
                        "total": len(pending),
                        "skipped_terminal": int(manifest["tile_count"]) - len(pending),
                        "status_counts": dict(status_counts),
                    }
                )
            except Exception:
                # A frontend/widget failure must never terminate an acquisition pass.
                pass

    progress_lock = threading.Lock()
    progress_completed = 0
    progress_status_counts = {"present": 0, "decoded_empty": 0, "error": 0}
    notify_progress("start", progress_completed, progress_status_counts)

    lock_path = output_root / provider / f".{manifest['region_id']}.lock"
    with exclusive_file_lock(lock_path, f"{provider}:{manifest['region_id']}"):
        limiter = GlobalStartLimiter(pass_config.start_interval_seconds)
        shards = [pending[index :: pass_config.max_workers] for index in range(pass_config.max_workers)]

        def run_shard(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
            nonlocal progress_completed
            session = _new_direct_session(session_factory)
            records: list[dict[str, Any]] = []
            try:
                for row in rows:
                    record = _fetch_one_tile(
                        session=session,
                        limiter=limiter,
                        runtime_config=runtime_config,
                        manifest=manifest,
                        row=row,
                        output_root=output_root,
                        timeout=(
                            pass_config.connect_timeout_seconds,
                            pass_config.read_timeout_seconds,
                        ),
                    )
                    records.append(record)
                    with progress_lock:
                        progress_completed += 1
                        status = str(record.get("status", "error"))
                        progress_status_counts[status if status in progress_status_counts else "error"] += 1
                        notify_progress("update", progress_completed, progress_status_counts)
            finally:
                session.close()
            return records

        records: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=pass_config.max_workers) as executor:
            futures = [executor.submit(run_shard, shard) for shard in shards]
            for future in as_completed(futures):
                records.extend(future.result())

    notify_progress("finish", progress_completed, progress_status_counts)

    records.sort(key=lambda row: float(row["request_started_monotonic"]))
    summary = summarize_stability_pass(
        records,
        expected_interval_seconds=pass_config.start_interval_seconds,
    )
    summary.update(
        {
            "provider": provider,
            "region_id": manifest["region_id"],
            "manifest_sha256": manifest["manifest_sha256"],
            "manifest_tile_count": manifest["tile_count"],
            "skipped_terminal_tile_count": int(manifest["tile_count"]) - len(pending),
            "worker_count": pass_config.max_workers,
            "provider_start_interval_seconds": pass_config.start_interval_seconds,
            "evidence_scope": runtime_config.get("evidence_scope", "unspecified"),
            "session_trust_env": False,
            "completed_at": utc_now_iso(),
        }
    )
    pass_dir = output_root / provider / str(manifest["region_id"]) / "passes"
    pass_name = datetime.now(timezone.utc).strftime("pass_%Y%m%dT%H%M%S%fZ")
    _atomic_write_json(pass_dir / f"{pass_name}.json", {"summary": summary, "records": records})
    return {"summary": summary, "records": records}


def summarize_manifest_completion(
    manifest_or_path: dict[str, Any] | Path,
    *,
    output_root: Path,
) -> dict[str, Any]:
    manifest = load_tile_manifest(manifest_or_path) if isinstance(manifest_or_path, Path) else dict(manifest_or_path)
    validate_tile_manifest(manifest)
    counts = {"missing": 0, "present": 0, "decoded_empty": 0, "error": 0}
    for row in manifest["tiles"]:
        _, metadata_path = _tile_paths(output_root, manifest, row)
        status = _existing_status(metadata_path)
        counts[status if status in counts else "error"] += 1
    return {
        "provider": manifest["provider"],
        "region_id": manifest["region_id"],
        "manifest_sha256": manifest["manifest_sha256"],
        "tile_count": manifest["tile_count"],
        **{f"{status}_tile_count": count for status, count in counts.items()},
        "terminal_tile_count": counts["present"] + counts["decoded_empty"],
        "complete": counts["missing"] == 0 and counts["error"] == 0,
    }


def run_provider_passes_concurrently(
    jobs: dict[str, dict[str, Any]],
    *,
    notebook_lock_path: Path,
) -> dict[str, Any]:
    """Run up to three provider supervisors concurrently (two workers each)."""

    unknown = set(jobs) - set(SUPPORTED_RASTER_PROVIDERS)
    if unknown:
        raise ValueError(f"Unsupported provider jobs: {sorted(unknown)}")
    results: dict[str, Any] = {}
    with exclusive_file_lock(notebook_lock_path, "0007 bounded raster acquisition"):
        with ThreadPoolExecutor(max_workers=len(jobs) or 1) as executor:
            future_map = {
                executor.submit(fetch_raster_manifest_pass, **arguments): provider
                for provider, arguments in jobs.items()
            }
            for future in as_completed(future_map):
                provider = future_map[future]
                try:
                    results[provider] = future.result()
                except Exception as exc:
                    results[provider] = {
                        "summary": {
                            "provider": provider,
                            "accepted_for_full_acquisition": False,
                            "supervisor_error_type": type(exc).__name__,
                            "supervisor_error": str(exc),
                        },
                        "records": [],
                    }
    return results


def write_pass_summary_csv(results: dict[str, Any], path: Path) -> None:
    """Optional cache helper used by the acquisition notebook, not a report export."""

    rows = [dict(value["summary"]) for _, value in sorted(results.items())]
    fieldnames = sorted({key for row in rows for key in row})
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
