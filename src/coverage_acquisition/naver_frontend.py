from __future__ import annotations

import json
import re
from dataclasses import dataclass
from urllib.request import Request, urlopen


USER_AGENT = "global-svi-coverage-observatory/0.2"
NAVER_BASIC_STYLE_JSONP_URL = "https://map.pstatic.net/nrb/styles/basic.json?fmt=png&callback=__naver_maps_callback__0"


def _fetch_text(url: str, *, user_agent: str = USER_AGENT, timeout_seconds: int = 30) -> str:
    request = Request(url, headers={"User-Agent": user_agent})
    with urlopen(request, timeout=timeout_seconds) as response:
        return response.read().decode("utf-8")


def parse_jsonp_payload(payload: str) -> dict:
    match = re.search(r"\(\s*(\{.*\})\s*\)\s*;?\s*$", payload, re.S)
    if not match:
        raise ValueError("Could not extract JSON object from JSONP payload.")
    return json.loads(match.group(1))


def discover_basic_style_metadata(
    *,
    user_agent: str = USER_AGENT,
    timeout_seconds: int = 30,
) -> dict:
    payload = _fetch_text(
        NAVER_BASIC_STYLE_JSONP_URL,
        user_agent=user_agent,
        timeout_seconds=timeout_seconds,
    )
    return parse_jsonp_payload(payload)


@dataclass(frozen=True)
class NaverPanoramaFrontendConfig:
    version: str
    base_style_template: str
    panorama_overlay_template: str
    panorama_picker_template: str


def discover_naver_panorama_frontend_config(
    *,
    user_agent: str = USER_AGENT,
    timeout_seconds: int = 30,
) -> NaverPanoramaFrontendConfig:
    metadata = discover_basic_style_metadata(
        user_agent=user_agent,
        timeout_seconds=timeout_seconds,
    )

    version = str(metadata["version"])
    base_style_template = metadata["tiles"][0]

    panorama_overlay_template = (
        f"https://map.pstatic.net/nrb/styles/basic/{version}" "/{z}/{x}/{y}.png?mt=bg.ol.ts.pr.lko"
    )
    panorama_picker_template = (
        f"https://map.pstatic.net/nrb/picker/basic/{version}" "/{z}/{x}/{y}.json?mt=ts.pr.lko&crs=EPSG:4326"
    )

    return NaverPanoramaFrontendConfig(
        version=version,
        base_style_template=base_style_template,
        panorama_overlay_template=panorama_overlay_template,
        panorama_picker_template=panorama_picker_template,
    )


def build_naver_panorama_overlay_url(version: str, z: int, x: int, y: int) -> str:
    return f"https://map.pstatic.net/nrb/styles/basic/{version}/{z}/{x}/{y}.png?mt=bg.ol.ts.pr.lko"


def build_naver_panorama_picker_url(version: str, z: int, x: int, y: int) -> str:
    return f"https://map.pstatic.net/nrb/picker/basic/{version}/{z}/{x}/{y}.json?mt=ts.pr.lko&crs=EPSG:4326"
