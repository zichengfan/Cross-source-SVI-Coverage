from __future__ import annotations

from coverage_acquisition.models import BoundingBox, FetchAreaRequest, ProviderDefinition, SourceDefinition


def test_register_discovery_kind_round_trip() -> None:
    from coverage_acquisition.discovery_kinds._base import (
        DISCOVERY_KIND_HANDLERS,
        get_discovery_kind_handler,
        register_discovery_kind,
    )

    def sample_handler(provider: ProviderDefinition, request: FetchAreaRequest) -> list[dict]:
        return [{"provider": provider.key, "request_provider": request.provider}]

    kind = "test_round_trip"
    DISCOVERY_KIND_HANDLERS.pop(kind, None)
    register_discovery_kind(kind, sample_handler)

    assert get_discovery_kind_handler(kind) is sample_handler

    DISCOVERY_KIND_HANDLERS.pop(kind, None)


def test_discovery_kinds_auto_registers_default() -> None:
    import coverage_acquisition.discovery_kinds
    from coverage_acquisition.discovery_kinds._base import DISCOVERY_KIND_HANDLERS

    assert "default" in DISCOVERY_KIND_HANDLERS
    assert coverage_acquisition.discovery_kinds.get_discovery_kind_handler("default") is DISCOVERY_KIND_HANDLERS["default"]


def test_default_discovery_matches_build_jobs(tmp_path) -> None:
    import coverage_acquisition.discovery_kinds
    from coverage_acquisition.runners import build_jobs

    source = SourceDefinition(
        id="coverage",
        kind="raster",
        template="https://example.test/{z}/{x}/{y}.png",
        display_zoom_min=4,
        display_zoom_max=8,
        query_zoom=6,
    )
    provider = ProviderDefinition(
        key="test_provider",
        output_namespace="test_provider",
        run_label_prefix="test",
        default_display_zoom=5,
        coordinate_scheme="web_mercator",
        supports_auto_zoom=True,
        sources=(source,),
    )
    request = FetchAreaRequest(
        provider="test_provider",
        bbox=BoundingBox(min_lon=-122.5, min_lat=37.7, max_lon=-122.3, max_lat=37.9),
        output_root=tmp_path,
        auto_zoom=True,
        min_display_zoom=4,
        max_display_zoom=6,
        max_source_tile_count=8,
        grid_rows=2,
        grid_cols=2,
        target_subboxes=(1, 3),
        run_label="sample",
    )

    handler = coverage_acquisition.discovery_kinds.get_discovery_kind_handler("default")

    assert handler(provider, request) == build_jobs(provider, request)
