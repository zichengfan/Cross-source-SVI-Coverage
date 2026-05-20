"""Shared test fixtures.

Unit tests never hit the network — they decode synthetic payloads built here.
"""

from __future__ import annotations

import io

import pytest
from PIL import Image

from coverage_acquisition.models import ProviderDefinition, SourceDefinition
from coverage_acquisition.source_kinds._base import DecodeContext


@pytest.fixture
def make_png():
    """Factory: build a tiny RGBA PNG, fully opaque or fully transparent."""

    def _make(width: int = 4, height: int = 4, opaque: bool = True) -> bytes:
        color = (12, 34, 56, 255) if opaque else (0, 0, 0, 0)
        image = Image.new("RGBA", (width, height), color)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    return _make


@pytest.fixture
def make_source():
    """Factory: build a SourceDefinition for a given kind."""

    def _make(kind: str = "raster", **overrides) -> SourceDefinition:
        params = {
            "id": f"test_{kind}",
            "kind": kind,
            "template": "https://example.test/{z}/{x}/{y}",
        }
        params.update(overrides)
        return SourceDefinition(**params)

    return _make


@pytest.fixture
def make_decode_context(tmp_path):
    """Factory: build a DecodeContext writing into the test's tmp_path."""

    def _make(
        source: SourceDefinition,
        *,
        payload: bytes = b"",
        content_type: str = "image/png",
        http_status: int = 200,
        x: int = 1,
        y: int = 2,
    ) -> DecodeContext:
        provider = ProviderDefinition(
            key="test_provider",
            output_namespace="test_provider_ns",
            run_label_prefix="test_provider",
            default_display_zoom=14,
            sources=(source,),
        )
        return DecodeContext(
            source=source,
            provider=provider,
            job={"display_zoom": 14, "source_zoom": 14},
            x=x,
            y=y,
            tile_url="https://example.test/14/1/2",
            fetched_at="2026-05-20T00:00:00+00:00",
            output_dir=tmp_path,
            wire_payload=payload,
            content_type=content_type,
            http_status=http_status,
        )

    return _make
