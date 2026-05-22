from __future__ import annotations

import json
import re
from urllib.request import Request, urlopen

from coverage_acquisition.models import FetchAreaRequest, SourceDefinition
from coverage_acquisition.runtime_config._base import register_runtime_config


def build_yandex_stv_runtime_options(source: SourceDefinition, request: FetchAreaRequest) -> dict:
    fallback_version = source.options.get("version_fallback", "")
    runtime_options = {
        "format_values": {
            "layer": source.options.get("layer", "stv"),
            "version": fallback_version,
        },
        "frontend_config": {
            "config_source": "fallback",
            "stv_version": fallback_version,
            "query_layers": "",
        },
    }

    try:
        frontend_config = _discover_yandex_frontend_config(
            page_url=source.options["frontend_page_url"],
            headers={**source.headers, **request.extra_headers},
            timeout_seconds=request.timeout_seconds or 60,
        )
    except Exception as exc:
        runtime_options["frontend_config"]["config_error"] = repr(exc)
        return runtime_options

    runtime_options["frontend_config"].update(frontend_config)
    runtime_options["frontend_config"]["config_source"] = "live_page"
    runtime_options["format_values"]["version"] = frontend_config["stv_version"]
    if frontend_config.get("stv_tiles_template"):
        runtime_options["tile_template"] = _normalize_yandex_stv_tile_template(
            frontend_config["stv_tiles_template"],
            request_layer=runtime_options["format_values"]["layer"],
        )
    return runtime_options


def _discover_yandex_frontend_config(page_url: str, headers: dict[str, str], timeout_seconds: int) -> dict[str, str]:
    request = Request(page_url, headers=headers)
    with urlopen(request, timeout=timeout_seconds) as response:
        html = response.read().decode("utf-8")

    match = re.search(r'<script type="application/json" class="state-view">(.*?)</script>', html, re.S)
    if not match:
        raise RuntimeError("Could not locate Yandex state-view JSON in the frontend page.")

    state = json.loads(match.group(1))
    config = state["config"]
    return {
        "stv_tiles_template": config["hosts"]["stvTiles"],
        "stv_version": config["layers"]["stv"]["version"],
        "query_layers": state.get("query", {}).get("l", ""),
    }


def _normalize_yandex_stv_tile_template(template: str, request_layer: str) -> str:
    normalized = template.replace("\\u0026", "&")
    normalized = normalized.replace("l=stv&", f"l={request_layer}&")
    normalized = normalized.replace(
        "https://0%d.core-stv-renderer.maps.yandex.net/",
        "https://core-stv-renderer.maps.yandex.net/",
    )
    normalized = normalized.replace("%c", "x={x}&y={y}&z={z}")
    normalized = normalized.replace("%v", "{version}")
    normalized = normalized.replace("%l", "lang=en_US&scale=1")
    return normalized


register_runtime_config("yandex_stv_renderer", build_yandex_stv_runtime_options)
