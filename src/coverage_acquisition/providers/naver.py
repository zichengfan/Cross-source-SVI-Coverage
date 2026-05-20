"""Naver Maps Street View coverage provider.

robots.txt / ToS caveat from the approved subplan: https://map.naver.com/robots.txt disallows almost everything:
User-agent: * -> Disallow: / with only Allow: /$ and Allow: /p/$. The discovery endpoint
https://map.naver.com/p/api/panorama/nearby/... is under /p/ but is not the literal /p/$ path, so a strict robots
reading does not allow it. ClaudeBot and AI-training agents are explicitly Disallow: /.

This provider uses option (b): minimize map.naver.com calls by using find_panorama only as a low-volume seed probe,
then do bulk discovery through get_neighbors on panorama.map.naver.com, whose robots.txt returned 404 during scouting.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from threading import Lock
from typing import Any

import streetlevel.naver as streetlevel_naver
from streetlevel.naver.panorama import NaverPanorama, PanoramaType
from streetlevel.naver.parse import parse_nearby, parse_neighbors

from coverage_acquisition.models import BoundingBox, ProviderDefinition, SourceDefinition
from coverage_acquisition.providers._registry import register_provider
from coverage_acquisition.source_kinds.streetlevel import ProbeBlockedError, register_streetlevel_probe

USER_AGENT = "global-svi-coverage-observatory/0.3 (+https://github.com/zichengfan/Cross-source-SVI-Coverage)"
STREETLEVEL_PANORAMA_TYPES = {
    int(PanoramaType.CAR),
    int(PanoramaType.BICYCLE),
    int(PanoramaType.TREKKER),
    int(PanoramaType.MESH_EQUIRECT),
}
DEFAULT_FRONTIER_CAP = 256

# The flood-fill can fire up to DEFAULT_FRONTIER_CAP get_neighbors calls per
# probe; throttle every one of them so the burst stays a polite scrape.
GET_NEIGHBORS_MIN_INTERVAL_SECONDS = 1.0


class _NeighborThrottle:
    """Process-wide minimum-interval gate for get_neighbors calls."""

    def __init__(self) -> None:
        self._last_request: float | None = None
        self._lock = Lock()

    def wait(self, min_interval_seconds: float) -> None:
        with self._lock:
            now = time.monotonic()
            if self._last_request is not None:
                elapsed = now - self._last_request
                if elapsed < min_interval_seconds:
                    time.sleep(min_interval_seconds - elapsed)
                    now = time.monotonic()
            self._last_request = now


_NEIGHBOR_THROTTLE = _NeighborThrottle()


@dataclass(frozen=True)
class NaverDecodeResult:
    records: list[dict]
    is_empty: bool = False
    dropped_count: int = 0


PROVIDER = ProviderDefinition(
    key="naver",
    output_namespace="naver_streetview_points",
    run_label_prefix="naver_streetview",
    default_display_zoom=14,
    coordinate_scheme="web_mercator",
    area_presets={
        "seoul_gangnam_pilot_bbox": BoundingBox(
            min_lon=127.020,
            min_lat=37.490,
            max_lon=127.060,
            max_lat=37.520,
        ),
    },
    sources=(
        SourceDefinition(
            id="naver_streetlevel_panos",
            kind="streetlevel",
            template="",
            headers={
                "User-Agent": USER_AGENT,
                "Referer": "https://map.naver.com",
            },
            storage_subdir="streetlevel",
            options={
                "streetlevel_module": "naver",
                "streetlevel_type_allowlist": (3, 4, 13, 15),
                "discovery": {
                    "posture": "option_b_minimize_map_naver_seed_calls",
                    "seed_grid_spacing_m": 300.0,
                    "frontier_cap": DEFAULT_FRONTIER_CAP,
                    "min_interval_seconds": 1.0,
                    "max_retries": 3,
                    "bulk_endpoint_host": "panorama.map.naver.com",
                },
            },
            notes=(
                "Naver streetlevel provider. Seeds with find_panorama on map.naver.com, then flood-fills via "
                "get_neighbors on panorama.map.naver.com with a bounded frontier."
            ),
        ),
    ),
)


def decode_nearby_payload(payload: dict[str, Any]) -> NaverDecodeResult:
    """Decode a Naver nearby FeatureCollection into de-duplicated pano records."""
    features = payload.get("features")
    if features == []:
        return NaverDecodeResult(records=[], is_empty=True)
    if not isinstance(features, list):
        raise ProbeBlockedError("Naver nearby response is missing a features list.")

    records = []
    for feature in features:
        pano = parse_nearby({"type": payload.get("type", "FeatureCollection"), "features": [feature]})
        record = _record_from_pano(pano, raw_extra={"response_kind": "nearby"})
        if record is not None:
            records.append(record)
    return NaverDecodeResult(records=_dedupe_records(records), is_empty=False)


def decode_around_payload(payload: dict[str, Any], parent_id: str) -> NaverDecodeResult:
    """Decode a Naver metadataV3/around payload into street-level pano records."""
    neighbors = parse_neighbors(payload, parent_id)
    records = []
    dropped_count = 0
    for section_name in ("street", "other"):
        panos = getattr(neighbors, section_name) or []
        for pano in panos:
            record = _record_from_pano(pano, raw_extra={"response_kind": "around", "section": section_name})
            if record is None:
                dropped_count += 1
                continue
            records.append(record)
    return NaverDecodeResult(records=_dedupe_records(records), is_empty=False, dropped_count=dropped_count)


def probe_naver(lat: float, lon: float, radius_m: float) -> list[dict]:
    """Probe Naver Street View near a point and flood-fill nearby street-level panoramas."""
    del radius_m
    try:
        seed = streetlevel_naver.find_panorama(lat, lon, neighbors=False, historical=False, depth=False)
    except AssertionError:
        raise
    except Exception as exc:
        raise ProbeBlockedError(f"Naver find_panorama response was blocked or undecodable: {exc}") from exc

    if seed is None:
        return []

    records: dict[str, dict] = {}
    frontier: deque[str] = deque()
    expanded: set[str] = set()
    _add_pano(seed, records, frontier)

    while frontier and len(expanded) < DEFAULT_FRONTIER_CAP:
        panoid = frontier.popleft()
        if panoid in expanded:
            continue
        expanded.add(panoid)
        _NEIGHBOR_THROTTLE.wait(GET_NEIGHBORS_MIN_INTERVAL_SECONDS)
        try:
            neighbors = streetlevel_naver.get_neighbors(panoid)
        except AssertionError:
            raise
        except Exception as exc:
            raise ProbeBlockedError(f"Naver get_neighbors response was blocked or undecodable: {exc}") from exc

        for pano in (getattr(neighbors, "street", None) or []):
            _add_pano(pano, records, frontier)
        for pano in (getattr(neighbors, "other", None) or []):
            _add_pano(pano, records, frontier)

    return list(records.values())


def _add_pano(pano: NaverPanorama, records: dict[str, dict], frontier: deque[str]) -> None:
    record = _record_from_pano(pano, raw_extra={"response_kind": "streetlevel_object"})
    if record is None:
        return
    panoid = str(record["panoid"])
    if panoid in records:
        return
    records[panoid] = record
    frontier.append(panoid)


def _record_from_pano(pano: NaverPanorama, raw_extra: dict[str, Any] | None = None) -> dict | None:
    pano_type = _panorama_type_value(pano.panorama_type)
    if pano_type not in STREETLEVEL_PANORAMA_TYPES:
        return None
    raw = {
        "id": pano.id,
        "panorama_type": pano_type,
        "lat": pano.lat,
        "lon": pano.lon,
    }
    if raw_extra:
        raw.update(raw_extra)
    return {
        "panoid": str(pano.id),
        "lat": float(pano.lat),
        "lon": float(pano.lon),
        "date": _format_date(pano.date),
        "raw": raw,
    }


def _panorama_type_value(value: PanoramaType | int | None) -> int | None:
    if value is None:
        return None
    return int(value)


def _format_date(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _dedupe_records(records: list[dict]) -> list[dict]:
    deduped: dict[str, dict] = {}
    for record in records:
        deduped.setdefault(str(record["panoid"]), record)
    return list(deduped.values())


register_provider(PROVIDER)
register_streetlevel_probe("naver", probe_naver)
