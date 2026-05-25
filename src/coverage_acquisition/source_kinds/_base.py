"""Source-kind plugin contract.

A *source kind* decodes one fetched tile payload into stored files + summary
fields. Each kind lives in its own module (`source_kinds/<kind>.py`) and calls
`register_source_kind("<kind>", handler)` at import time, so adding a kind never
edits a shared file (`runners.py` only dispatches).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from coverage_acquisition.models import ProviderDefinition, SourceDefinition


@dataclass(frozen=True)
class DecodeContext:
    """Everything a handler needs about one fetched tile."""

    source: SourceDefinition
    provider: ProviderDefinition
    job: dict
    x: int
    y: int
    tile_url: str
    fetched_at: str
    output_dir: Path
    wire_payload: bytes
    content_type: str
    http_status: int


@dataclass
class DecodeResult:
    """Outcome of decoding one tile. Field names mirror the tile_summary row."""

    tile_path: Path | None = None
    stored_payload: bytes = b""
    was_gzip_compressed: bool = False
    is_empty: bool | str = ""
    width: int | str = ""
    height: int | str = ""
    coverage_pixel_count: int | str = ""
    total_pixel_count: int | str = ""
    coverage_ratio: float | str = ""
    record_count: int | str = ""
    pano_count: int | str = ""
    feature_count: int | str = ""
    layer_counts_json: str = ""
    last_modified: str = ""
    pano_records: list[dict] = field(default_factory=list)
    vector_feature_records: list[dict] = field(default_factory=list)
    # When skipped, the tile is dropped from the summary; skip_record (if any)
    # is appended to skipped_tiles.json.
    skipped: bool = False
    skip_record: dict | None = None


SourceKindHandler = Callable[[DecodeContext], DecodeResult]

SOURCE_KIND_HANDLERS: dict[str, SourceKindHandler] = {}


def register_source_kind(kind: str, handler: SourceKindHandler) -> None:
    if kind in SOURCE_KIND_HANDLERS:
        raise ValueError(f"Source kind already registered: {kind!r}")
    SOURCE_KIND_HANDLERS[kind] = handler


def tile_storage_path(ctx: DecodeContext, suffix: str) -> Path:
    """Standard on-disk path for a decoded tile: <subdir>/<z>/<x>/<y><suffix>."""
    return (
        ctx.output_dir
        / ctx.source.effective_storage_subdir
        / str(ctx.job["source_zoom"])
        / str(ctx.x)
        / f"{ctx.y}{suffix}"
    )
