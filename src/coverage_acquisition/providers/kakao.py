"""Kakao Maps Road View coverage provider.

This provider probes the public Kakao Road View radius-search JSON API on
`rv.map.kakao.com` only. The Kakao viewer host `map.kakao.com` has a restrictive
robots.txt, so this module must never crawl viewer pages there; the viewer URL
appears only as a referer. Coverage is South Korea only and requires no auth.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from streetlevel.kakao.api import build_find_panoramas_request_url
from streetlevel.kakao.parse import parse_panoramas

from coverage_acquisition.models import BoundingBox, ProviderDefinition, SourceDefinition
from coverage_acquisition.polite import polite_fetch
from coverage_acquisition.providers._registry import register_provider
from coverage_acquisition.source_kinds.streetlevel import ProbeBlockedError, register_streetlevel_probe


@dataclass(frozen=True)
class KakaoProbeConfig:
    limit: int = 100
    user_agent: str = "global-svi-coverage-observatory/0.3"


KAKAO_PROBE_CONFIG = KakaoProbeConfig()

KAKAO_HEADERS = {
    "User-Agent": KAKAO_PROBE_CONFIG.user_agent,
    "Accept": "application/json",
    "Referer": "https://map.kakao.com/",
}


def build_kakao_query_url(lat: float, lon: float, radius_m: float, limit: int = 100) -> str:
    """Build a Kakao Road View radius-search URL using streetlevel's API helper."""
    return build_find_panoramas_request_url(
        lat=lat,
        lon=lon,
        radius=int(round(radius_m)),
        limit=int(limit),
    )


def probe_kakao_coverage(lat: float, lon: float, radius_m: float) -> list[dict]:
    """Probe Kakao Road View coverage near one WGS84 point."""
    url = build_kakao_query_url(lat=lat, lon=lon, radius_m=radius_m, limit=KAKAO_PROBE_CONFIG.limit)
    payload, content_type, _status = polite_fetch(url, headers=KAKAO_HEADERS)
    if not content_type.startswith("application/json"):
        raise ProbeBlockedError(f"Kakao probe returned unexpected content type: {content_type!r}")
    return decode_kakao_panoramas(payload)


def decode_kakao_panoramas(payload: bytes | str) -> list[dict]:
    """Decode Kakao Road View JSON into normalized pano dictionaries."""
    try:
        response = json.loads(payload.decode("utf-8") if isinstance(payload, bytes) else payload)
        street_view = response["street_view"]
        count = int(street_view["cnt"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ProbeBlockedError("Kakao probe returned undecodable JSON.") from exc

    street_list = street_view.get("streetList")
    if count == 0:
        return []
    if not isinstance(street_list, list):
        raise ProbeBlockedError("Kakao probe returned a non-empty response without streetList.")

    try:
        panoramas = parse_panoramas(response)
    except Exception as exc:
        raise ProbeBlockedError("Kakao probe returned an unparseable panorama list.") from exc

    return [_to_pano_record(panorama, raw) for panorama, raw in zip(panoramas, street_list, strict=True)]


def _to_pano_record(panorama: Any, raw: dict) -> dict:
    date = panorama.date.date().isoformat() if panorama.date is not None else None
    return {
        "panoid": panorama.id,
        "lat": panorama.lat,
        "lon": panorama.lon,
        "date": date,
        "raw": raw,
    }


PROVIDER = ProviderDefinition(
    key="kakao",
    output_namespace="kakao_roadview_coverage",
    run_label_prefix="kakao_roadview_coverage",
    default_display_zoom=14,
    coordinate_scheme="web_mercator",
    area_presets={
        "seoul_city_hall_bbox": BoundingBox(
            min_lon=126.960,
            min_lat=37.560,
            max_lon=126.990,
            max_lat=37.580,
        ),
    },
    sources=(
        SourceDefinition(
            id="kakao_roadview_nodes",
            kind="streetlevel",
            template=(
                "https://rv.map.kakao.com/roadview-search/v2/nodes?"
                "PX={lon}&PY={lat}&RAD={radius}&PAGE_SIZE={limit}&INPUT=wgs&TYPE=w&SERVICE=glpano"
            ),
            headers=KAKAO_HEADERS,
            expect_content_type_prefix="application/json",
            storage_subdir="nodes",
            options={
                "streetlevel_module": "kakao",
                "search_radius_m": "100",
                "page_size": "100",
                "grid_spacing_m": "140",
            },
            notes=(
                "Kakao Road View coverage via the rv.map.kakao.com radius-search JSON API. "
                "Point-query, not tiles; presence = street_view.cnt > 0."
            ),
        ),
    ),
)

register_provider(PROVIDER)
register_streetlevel_probe("kakao", probe_kakao_coverage)
