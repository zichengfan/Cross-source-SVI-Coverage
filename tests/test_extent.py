"""Tests for low-zoom extent discovery."""

from __future__ import annotations

from coverage_acquisition.extent import child_tiles, discover_coverage_tiles
from coverage_acquisition.models import BoundingBox, ProviderDefinition, SourceDefinition


def test_child_tiles_expands_to_descendants() -> None:
    descendants = child_tiles((1, 1), 1, 3)

    assert len(descendants) == 16
    assert set(descendants) == {(x, y) for x in range(4, 8) for y in range(4, 8)}


def test_discover_coverage_tiles_uses_fetch_and_predicate(monkeypatch, tmp_path) -> None:
    source = SourceDefinition(
        id="coverage",
        kind="raster",
        template="https://example.test/{z}/{x}/{y}.png",
    )
    provider = ProviderDefinition(
        key="test_provider",
        output_namespace="test_provider",
        run_label_prefix="test",
        default_display_zoom=1,
        sources=(source,),
    )

    monkeypatch.setattr("coverage_acquisition.extent.get_provider", lambda key: provider)

    def fake_fetch(url: str, headers=None, policy=None):
        return url.encode("utf-8"), "image/png", 200

    monkeypatch.setattr("coverage_acquisition.extent.polite.polite_fetch", fake_fetch)

    covered = discover_coverage_tiles(
        "test_provider",
        BoundingBox(min_lon=-0.1, min_lat=-0.1, max_lon=0.1, max_lat=0.1),
        1,
        output_root=tmp_path,
        has_coverage=lambda payload, *_args, **_kwargs: b"/1/1.png" in payload,
    )

    assert covered == [(1, 1)]
