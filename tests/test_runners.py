"""Tests for fetch-runner runtime option discovery."""

from __future__ import annotations

from pathlib import Path

from coverage_acquisition.models import BoundingBox, FetchAreaRequest, SourceDefinition
from coverage_acquisition.runners import _build_runtime_options


def _request(tmp_path: Path) -> FetchAreaRequest:
    return FetchAreaRequest(
        provider="test",
        bbox=BoundingBox(min_lon=0.0, min_lat=0.0, max_lon=1.0, max_lat=1.0),
        output_root=tmp_path,
    )


def test_build_runtime_options_discovers_naver_pstatic_version(monkeypatch, tmp_path):
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
        assert url == "https://map.pstatic.net/nrb/styles/basic.json?fmt=png&mt=ps"
        return b'{"version":"1732841753","tiles":["https://map.pstatic.net/nrb/styles/basic/1732841753/{z}/{x}/{y}.png"]}', "application/json", 200

    monkeypatch.setattr("coverage_acquisition.polite.polite_fetch", fake_polite_fetch)

    runtime_options = _build_runtime_options(source, _request(tmp_path))

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

    runtime_options = _build_runtime_options(source, _request(tmp_path))

    assert runtime_options["format_values"]["version"] == "fallback-version"
    assert runtime_options["frontend_config"]["config_source"] == "fallback"
    assert "config_error" in runtime_options["frontend_config"]
