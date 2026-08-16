from __future__ import annotations

import io
import json
import threading
from pathlib import Path

import pytest
from PIL import Image
from shapely.geometry import box

from coverage_acquisition import bounded_raster
from coverage_acquisition.bounded_raster import (
    RasterPassConfig,
    build_polygon_tile_manifest,
    deterministic_roi_sample_manifest,
    download_file_with_manifest,
    download_un_m49_csv,
    fetch_raster_manifest_pass,
    manifest_sha256,
    resolve_raster_runtime_config,
    run_provider_passes_concurrently,
    safe_extract_zip,
)


def _png(*, empty: bool) -> bytes:
    buffer = io.BytesIO()
    alpha = 0 if empty else 255
    Image.new("RGBA", (8, 8), (20, 90, 160, alpha)).save(buffer, format="PNG")
    return buffer.getvalue()


def _manifest(provider: str = "mapy", tile_count: int = 4) -> dict:
    rows = [
        {
            "provider": provider,
            "source_id": f"{provider}_source",
            "coordinate_scheme": "web_mercator",
            "level": 13,
            "x": 4300 + index,
            "y": 2800,
        }
        for index in range(tile_count)
    ]
    manifest = {
        "schema_version": 1,
        "provider": provider,
        "source_id": f"{provider}_source",
        "region_id": "test_region",
        "coordinate_scheme": "web_mercator",
        "level": 13,
        "halo_tiles": 0,
        "tile_count": len(rows),
        "tiles": rows,
    }
    manifest["manifest_sha256"] = manifest_sha256(manifest)
    return manifest


def test_polygon_manifest_is_deterministic_and_includes_halo():
    geometry = box(14.40, 50.07, 14.45, 50.10)
    first = build_polygon_tile_manifest(
        provider="mapy",
        region_id="prague",
        geometry_wgs84=geometry,
        level=13,
        halo_tiles=1,
    )
    second = build_polygon_tile_manifest(
        provider="mapy",
        region_id="prague",
        geometry_wgs84=geometry,
        level=13,
        halo_tiles=1,
    )

    assert first == second
    assert first["tile_count"] > first["intersecting_tile_count"]
    assert first["manifest_sha256"] == manifest_sha256(first)


def test_kakao_polygon_manifest_uses_native_grid():
    manifest = build_polygon_tile_manifest(
        provider="kakao",
        region_id="seoul",
        geometry_wgs84=box(126.96, 37.54, 127.02, 37.59),
        level=5,
        halo_tiles=1,
    )

    assert manifest["coordinate_scheme"] == "kakao"
    assert manifest["tile_count"] > 0
    assert all(row["level"] == 5 for row in manifest["tiles"])


def test_deterministic_sample_has_three_disjoint_hundred_tile_strata(monkeypatch):
    manifest = _manifest(tile_count=360)
    monkeypatch.setattr(bounded_raster, "_tile_polygon", lambda *_args: box(0, 0, 1, 1))
    sample = deterministic_roi_sample_manifest(
        manifest,
        rois=[("city", box(0, 0, 1, 1)), ("other", box(0, 0, 1, 1)), ("rural", box(0, 0, 1, 1))],
        per_roi=100,
    )

    assert sample["tile_count"] == 300
    assert {row["sample_stratum"] for row in sample["tiles"]} == {"city", "other", "rural"}
    assert len({(row["level"], row["x"], row["y"]) for row in sample["tiles"]}) == 300


class _Response:
    def __init__(self, payload: bytes):
        self.status_code = 200
        self.content = payload
        self.headers = {"Content-Type": "image/png", "ETag": "test"}

    def raise_for_status(self):
        return None


class _Session:
    def __init__(self, payload: bytes, calls: list, sessions: list):
        self.payload = payload
        self.calls = calls
        self.trust_env = True
        self.closed = False
        sessions.append(self)

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs, self.trust_env))
        return _Response(self.payload)

    def close(self):
        self.closed = True


class _InstantLimiter:
    def __init__(self, interval_seconds):
        self.interval_seconds = interval_seconds
        self.value = -1.0
        self.lock = threading.Lock()

    def wait(self):
        with self.lock:
            self.value += self.interval_seconds
            return self.value


@pytest.mark.parametrize(("empty", "expected"), [(False, "present"), (True, "decoded_empty")])
def test_fetch_pass_closes_two_direct_sessions_and_resumes(monkeypatch, tmp_path, empty, expected):
    calls = []
    sessions = []
    progress_events = []
    payload = _png(empty=empty)
    monkeypatch.setattr(bounded_raster, "GlobalStartLimiter", _InstantLimiter)

    def factory():
        return _Session(payload, calls, sessions)

    manifest = _manifest(tile_count=4)
    runtime = {
        "provider": "mapy",
        "source_id": "mapy_source",
        "template": "https://example.test/{z}-{x}-{y}",
        "headers": {"Referer": "https://mapy.com/"},
        "frontend": {"config_source": "test"},
    }
    result = fetch_raster_manifest_pass(
        manifest,
        output_root=tmp_path,
        runtime_config=runtime,
        session_factory=factory,
        progress_callback=progress_events.append,
    )

    assert result["summary"]["worker_count"] == 2
    assert result["summary"]["provider_start_interval_seconds"] == 1.0
    assert result["summary"]["minimum_request_start_interval_seconds"] == 1.0
    assert len(calls) == 4
    assert all(call[2] is False for call in calls)
    assert len(sessions) == 2 and all(session.closed for session in sessions)
    assert {row["status"] for row in result["records"]} == {expected}
    assert progress_events[0]["event"] == "start"
    assert progress_events[-1]["event"] == "finish"
    assert progress_events[-1]["completed"] == progress_events[-1]["total"] == 4
    assert progress_events[-1]["status_counts"][expected] == 4

    for row in manifest["tiles"]:
        path = tmp_path / "mapy" / "test_region" / "13" / str(row["x"]) / f"{row['y']}.png.metadata.json"
        assert json.loads(path.read_text())["status"] == expected

    calls_before_resume = len(calls)
    fetch_raster_manifest_pass(
        manifest,
        output_root=tmp_path,
        runtime_config=runtime,
        session_factory=factory,
    )
    assert len(calls) == calls_before_resume


def test_only_approved_worker_and_interval_configuration_is_accepted():
    RasterPassConfig().validate()
    with pytest.raises(ValueError, match="exactly 2 workers"):
        RasterPassConfig(max_workers=3).validate()
    with pytest.raises(ValueError, match="1.0 second"):
        RasterPassConfig(start_interval_seconds=0.5).validate()


def test_three_provider_supervisors_start_concurrently(monkeypatch, tmp_path):
    barrier = threading.Barrier(3)

    def fake_pass(**kwargs):
        barrier.wait(timeout=2)
        provider = kwargs["manifest_or_path"]["provider"]
        return {"summary": {"provider": provider}, "records": []}

    monkeypatch.setattr(bounded_raster, "fetch_raster_manifest_pass", fake_pass)
    jobs = {
        provider: {"manifest_or_path": _manifest(provider), "output_root": tmp_path}
        for provider in ("naver", "kakao", "mapy")
    }
    results = run_provider_passes_concurrently(jobs, notebook_lock_path=tmp_path / ".notebook.lock")

    assert set(results) == {"naver", "kakao", "mapy"}


class _ContextResponse:
    def __init__(self, payload: bytes, content_type: str = "text/html"):
        self.content = payload
        self.text = payload.decode("utf-8")
        self.url = "https://example.test/final"
        self.headers = {"Content-Type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size):
        assert chunk_size == 1024 * 1024
        yield self.content


class _ContextSession:
    def __init__(self, response: _ContextResponse):
        self.response = response
        self.trust_env = True
        self.closed = False

    def get(self, _url, **_kwargs):
        return self.response

    def close(self):
        self.closed = True


def test_context_download_rejects_html_before_atomic_replace(tmp_path):
    response = _ContextResponse(b"<!DOCTYPE html><html><title>Product page</title></html>")
    session = _ContextSession(response)
    output = tmp_path / "population.zip"

    with pytest.raises(ValueError, match="HTML.*direct distribution URL"):
        download_file_with_manifest(
            url="https://example.test/product",
            output_path=output,
            source_page="https://example.test/product",
            license_name="test",
            session_factory=lambda: session,
            expected_kind="zip",
        )

    assert not output.exists()
    assert not Path(str(output) + ".download.json").exists()
    assert session.trust_env is False
    assert session.closed


def test_safe_extract_zip_reports_mislabeled_html(tmp_path):
    archive = tmp_path / "not-a-real.zip"
    archive.write_text("<!DOCTYPE html><html></html>", encoding="utf-8")

    with pytest.raises(ValueError, match="not a valid ZIP.*HTML"):
        safe_extract_zip(archive, tmp_path / "extracted")


def test_un_m49_html_table_is_cached_as_csv_with_provenance(tmp_path):
    html = b"""
    <table>
      <tr><th>Global Name</th><th>ISO-alpha3 Code</th><th>Region Name</th><th>Sub-region Name</th></tr>
      <tr><td>World</td><td>DZA</td><td>Africa</td><td>Northern Africa</td></tr>
      <tr><td>World</td><td>KOR</td><td>Asia</td><td>Eastern Asia</td></tr>
    </table>
    <table>
      <tr><th>Global Name</th><th>ISO-alpha3 Code</th><th>Region Name</th><th>Sub-region Name</th></tr>
      <tr><td>\xe4\xb8\x96\xe7\x95\x8c</td><td>DZA</td><td>\xe9\x9d\x9e\xe6\xb4\xb2</td><td>\xe5\x8c\x97\xe9\x9d\x9e</td></tr>
    </table>
    """
    session = _ContextSession(_ContextResponse(html))
    output = tmp_path / "m49.csv"

    record = download_un_m49_csv(
        url="https://example.test/m49",
        output_path=output,
        source_page="https://example.test/m49",
        license_name="test",
        session_factory=lambda: session,
    )

    assert "World,KOR,Asia,Eastern Asia" in output.read_text(encoding="utf-8")
    assert "\u4e16\u754c" not in output.read_text(encoding="utf-8")
    assert record["transformation"].startswith("standard-library HTML table parse")
    assert json.loads(Path(str(output) + ".download.json").read_text())["sha256"]
    assert session.trust_env is False
    assert session.closed


def test_naver_runtime_uses_street_only_ps_overlay():
    payload = b'__naver_maps_callback__0({"version":"123","tiles":["https://map.test/basic/123/{z}/{x}/{y}.png"]});'
    session = _ContextSession(_ContextResponse(payload, "application/javascript"))

    runtime = resolve_raster_runtime_config("naver", session_factory=lambda: session)

    assert runtime["template"].endswith("?mt=ps")
    assert runtime["evidence_scope"] == "street_panorama_lines_only"
    assert runtime["frontend"]["air_water_icons_visible"] is False
    assert session.trust_env is False
    assert session.closed
