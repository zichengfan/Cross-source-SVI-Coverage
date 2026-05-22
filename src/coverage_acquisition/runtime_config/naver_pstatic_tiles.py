from __future__ import annotations

import json
import re

from coverage_acquisition import polite
from coverage_acquisition.models import FetchAreaRequest, SourceDefinition
from coverage_acquisition.polite import PolitePolicy
from coverage_acquisition.runtime_config._base import register_runtime_config


def build_naver_pstatic_runtime_options(source: SourceDefinition, request: FetchAreaRequest) -> dict:
    fallback_version = source.options.get("version_fallback", "")
    runtime_options = {
        "format_values": {
            "version": fallback_version,
        },
        "frontend_config": {
            "config_source": "fallback",
            "version": fallback_version,
            "tilejson_url": source.options.get(
                "tilejson_url",
                "https://map.pstatic.net/nrb/styles/basic.json?fmt=png&mt=ps",
            ),
        },
    }

    try:
        tilejson_config = _discover_naver_pstatic_tilejson_config(
            tilejson_url=runtime_options["frontend_config"]["tilejson_url"],
            headers={**source.headers, **request.extra_headers},
            timeout_seconds=request.timeout_seconds or 60,
        )
    except Exception as exc:
        runtime_options["frontend_config"]["config_error"] = repr(exc)
        return runtime_options

    runtime_options["frontend_config"].update(tilejson_config)
    runtime_options["frontend_config"]["config_source"] = "live_tilejson"
    runtime_options["format_values"]["version"] = tilejson_config["version"]
    return runtime_options


def _discover_naver_pstatic_tilejson_config(
    tilejson_url: str,
    headers: dict[str, str],
    timeout_seconds: int,
) -> dict[str, str]:
    payload, _, _ = polite.polite_fetch(
        tilejson_url,
        headers=headers,
        policy=PolitePolicy(timeout_seconds=timeout_seconds),
    )
    tilejson = json.loads(payload.decode("utf-8"))
    return {"version": _extract_naver_pstatic_version(tilejson)}


def _extract_naver_pstatic_version(payload: object) -> str:
    if isinstance(payload, dict):
        version = payload.get("version")
        if isinstance(version, str) and version:
            return version
        for value in payload.values():
            try:
                return _extract_naver_pstatic_version(value)
            except ValueError:
                continue
    if isinstance(payload, list):
        for value in payload:
            try:
                return _extract_naver_pstatic_version(value)
            except ValueError:
                continue
    if isinstance(payload, str):
        match = re.search(r"/nrb/styles/basic/([^/]+)/", payload)
        if match:
            return match.group(1)
    raise ValueError("Could not locate Naver pstatic tile version in TileJSON.")


register_runtime_config("naver_pstatic_tiles", build_naver_pstatic_runtime_options)
