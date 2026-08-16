from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.request import Request, urlopen

USER_AGENT = "global-svi-coverage-observatory/0.2"
KAKAO_MAP_SDK_LOADER_URL = "https://ssl.daumcdn.net/dmaps/map_js_init/v3.js"


def _fetch_text(url: str, *, user_agent: str = USER_AGENT, timeout_seconds: int = 30) -> str:
    request = Request(url, headers={"User-Agent": user_agent})
    with urlopen(request, timeout=timeout_seconds) as response:
        return response.read().decode("utf-8")


def _normalize_protocol_relative_url(url: str, *, default_scheme: str = "https:") -> str:
    if url.startswith("//"):
        return f"{default_scheme}{url}"
    if "://" not in url:
        return f"{default_scheme}//{url}"
    return url


def _extract_uri_templates(loader_js: str) -> dict[str, str]:
    pattern = re.compile(
        r'([A-Z_]+):function\(\w+,\w+,\w+\)\{\s*return\s*"([^"]+)"'
        r'\+\w+\+"/"\+\w+\+"/"\+\w+\+"\.png"\}',
        re.S,
    )
    templates: dict[str, str] = {}
    for layer_name, prefix in pattern.findall(loader_js):
        normalized_prefix = _normalize_protocol_relative_url(prefix)
        templates[layer_name] = f"{normalized_prefix}" + "{level}/{tile_y}/{tile_x}.png"
    if not templates:
        raise ValueError("Could not parse Kakao tile URI templates from the SDK loader.")
    return templates


def _extract_resource_paths(loader_js: str) -> dict[str, str]:
    pattern = re.compile(r'([A-Z_]+):"([^"]+)"')
    resource_block_match = re.search(r"e\.RESOURCE_PATH=\{(.*?)\};", loader_js, re.S)
    if not resource_block_match:
        return {}

    resource_paths: dict[str, str] = {}
    for key, value in pattern.findall(resource_block_match.group(1)):
        resource_paths[key] = _normalize_protocol_relative_url(value)
    return resource_paths


def _extract_runtime_bundle_versions(loader_js: str) -> dict[str, str]:
    runtime_match = re.search(r'var c=e\.onloadcallbacks,o=\["v3"\],m=\{(.*?)\},l=', loader_js, re.S)
    if not runtime_match:
        return {}

    versions: dict[str, str] = {}
    for key, value in re.findall(r'([a-z0-9_]+):r\+"[^"]+/([^/"]+)/[^/"]+"', runtime_match.group(1), re.I):
        versions[key] = value
    return versions


@dataclass(frozen=True)
class KakaoRoadviewFrontendConfig:
    sdk_loader_url: str
    runtime_bundle_versions: dict[str, str]
    resource_paths: dict[str, str]
    tile_templates: dict[str, str]
    roadview_sd_template: str
    roadview_hd_template: str


def discover_kakao_roadview_frontend_config(
    *,
    user_agent: str = USER_AGENT,
    timeout_seconds: int = 30,
) -> KakaoRoadviewFrontendConfig:
    loader_js = _fetch_text(
        KAKAO_MAP_SDK_LOADER_URL,
        user_agent=user_agent,
        timeout_seconds=timeout_seconds,
    )
    tile_templates = _extract_uri_templates(loader_js)

    roadview_sd_template = tile_templates.get("ROADVIEW")
    roadview_hd_template = tile_templates.get("ROADVIEW_HD")
    if not roadview_sd_template or not roadview_hd_template:
        raise ValueError("Kakao SDK loader did not expose ROADVIEW and ROADVIEW_HD tile templates.")

    return KakaoRoadviewFrontendConfig(
        sdk_loader_url=KAKAO_MAP_SDK_LOADER_URL,
        runtime_bundle_versions=_extract_runtime_bundle_versions(loader_js),
        resource_paths=_extract_resource_paths(loader_js),
        tile_templates=tile_templates,
        roadview_sd_template=roadview_sd_template,
        roadview_hd_template=roadview_hd_template,
    )


def build_kakao_roadview_tile_url(template: str, z: int, x: int, y: int) -> str:
    return template.format(
        level=z,
        tile_x=x,
        tile_y=y,
        z=z,
        x=x,
        y=y,
    )


def build_kakao_roadview_sd_tile_url(versioned_template: str, z: int, x: int, y: int) -> str:
    return build_kakao_roadview_tile_url(versioned_template, z, x, y)


def build_kakao_roadview_hd_tile_url(versioned_template: str, z: int, x: int, y: int) -> str:
    return build_kakao_roadview_tile_url(versioned_template, z, x, y)
