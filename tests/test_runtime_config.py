"""Tests for provider runtime-config discovery."""

from __future__ import annotations

from pathlib import Path

from coverage_acquisition.models import BoundingBox, FetchAreaRequest, SourceDefinition
from coverage_acquisition.runtime_config import build_runtime_options
from coverage_acquisition.runtime_config._base import RUNTIME_CONFIG_HANDLERS, register_runtime_config


def _request(tmp_path: Path) -> FetchAreaRequest:
    return FetchAreaRequest(
        provider="test",
        bbox=BoundingBox(min_lon=0.0, min_lat=0.0, max_lon=1.0, max_lat=1.0),
        output_root=tmp_path,
    )


def test_build_runtime_options_returns_empty_without_registered_config_kind(tmp_path):
    source = SourceDefinition(id="plain", kind="raster", template="https://example.test/{z}/{x}/{y}.png")
    unknown_source = SourceDefinition(
        id="unknown",
        kind="raster",
        template="https://example.test/{z}/{x}/{y}.png",
        options={"config_kind": "not_registered"},
    )

    assert build_runtime_options(source, _request(tmp_path)) == {}
    assert build_runtime_options(unknown_source, _request(tmp_path)) == {}


def test_build_runtime_options_dispatches_to_registered_handler(tmp_path):
    def fake_handler(source: SourceDefinition, request: FetchAreaRequest) -> dict:
        assert source.id == "registered"
        assert request.provider == "test"
        return {"format_values": {"version": "from-handler"}}

    config_kind = "test_runtime_config_dispatch"
    register_runtime_config(config_kind, fake_handler)
    source = SourceDefinition(
        id="registered",
        kind="raster",
        template="https://example.test/{version}/{z}/{x}/{y}.png",
        options={"config_kind": config_kind},
    )

    try:
        assert build_runtime_options(source, _request(tmp_path)) == {"format_values": {"version": "from-handler"}}
    finally:
        RUNTIME_CONFIG_HANDLERS.pop(config_kind, None)


def test_build_runtime_options_discovers_naver_pstatic_version(monkeypatch, tmp_path):
    source = SourceDefinition(
        id="naver_tiles",
        kind="raster",
        template="https://map.pstatic.net/nrb/styles/basic/{version}/{z}/{x}/{y}.png?mt=ps",
        headers={"Referer": "https://map.naver.com/"},
        options={
            "config_kind": "naver_pstatic_tiles",
            "tilejson_url": "https://map.pstatic.net/nrb/styles/basic.json?fmt=png&mt=ps",
            "version_fallback": "fallback-version",
        },
    )

    def fake_polite_fetch(url, headers=None, policy=None):
        assert url == "https://map.pstatic.net/nrb/styles/basic.json?fmt=png&mt=ps"
        assert headers["Referer"] == "https://map.naver.com/"
        assert headers["X-Test"] == "1"
        return (
            b'{"version":"1732841753","tiles":["https://map.pstatic.net/nrb/styles/basic/1732841753/{z}/{x}/{y}.png"]}',
            "application/json",
            200,
        )

    monkeypatch.setattr("coverage_acquisition.polite.polite_fetch", fake_polite_fetch)
    request = FetchAreaRequest(
        provider="test",
        bbox=BoundingBox(min_lon=0.0, min_lat=0.0, max_lon=1.0, max_lat=1.0),
        output_root=tmp_path,
        extra_headers={"X-Test": "1"},
    )

    runtime_options = build_runtime_options(source, request)

    assert runtime_options["format_values"]["version"] == "1732841753"
    assert runtime_options["frontend_config"]["config_source"] == "live_tilejson"


def test_build_runtime_options_falls_back_for_naver_pstatic_version(monkeypatch, tmp_path):
    source = SourceDefinition(
        id="naver_tiles",
        kind="raster",
        template="https://map.pstatic.net/nrb/styles/basic/{version}/{z}/{x}/{y}.png?mt=ps",
        options={
            "config_kind": "naver_pstatic_tiles",
            "tilejson_url": "https://map.pstatic.net/nrb/styles/basic.json?fmt=png&mt=ps",
            "version_fallback": "fallback-version",
        },
    )

    def fake_polite_fetch(url, headers=None, policy=None):
        raise RuntimeError("offline")

    monkeypatch.setattr("coverage_acquisition.polite.polite_fetch", fake_polite_fetch)

    runtime_options = build_runtime_options(source, _request(tmp_path))

    assert runtime_options["format_values"]["version"] == "fallback-version"
    assert runtime_options["frontend_config"]["config_source"] == "fallback"
    assert "config_error" in runtime_options["frontend_config"]


def test_build_runtime_options_falls_back_for_yandex_stv_renderer(tmp_path):
    source = SourceDefinition(
        id="yandex_stv",
        kind="raster",
        template="https://core-stv-renderer.maps.yandex.net/?x={x}&y={y}&z={z}&v={version}&l={layer}",
        options={
            "config_kind": "yandex_stv_renderer",
            "frontend_page_url": "https://example.invalid/yandex",
            "layer": "stv",
            "version_fallback": "fallback-version",
        },
    )
    request = FetchAreaRequest(
        provider="test",
        bbox=BoundingBox(min_lon=0.0, min_lat=0.0, max_lon=1.0, max_lat=1.0),
        output_root=tmp_path,
        timeout_seconds=1,
    )

    runtime_options = build_runtime_options(source, request)

    assert runtime_options["format_values"]["version"] == "fallback-version"
    assert runtime_options["frontend_config"]["config_source"] == "fallback"
    assert "config_error" in runtime_options["frontend_config"]
