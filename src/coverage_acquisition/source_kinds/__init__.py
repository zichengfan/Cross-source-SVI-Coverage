"""Source-kind plugin package.

Auto-imports every non-underscore module so each kind self-registers. A new
source kind is one new file `source_kinds/<kind>.py` calling
`register_source_kind(...)` — `runners.py` only dispatches and is never edited.
"""

from __future__ import annotations

import importlib
import pkgutil

from coverage_acquisition.source_kinds._base import (
    SOURCE_KIND_HANDLERS,
    DecodeContext,
    DecodeResult,
    SourceKindHandler,
    register_source_kind,
)


def _discover_source_kinds() -> None:
    for module_info in pkgutil.iter_modules(__path__):
        if module_info.name.startswith("_"):
            continue
        importlib.import_module(f"{__name__}.{module_info.name}")


_discover_source_kinds()


def get_source_kind_handler(kind: str) -> SourceKindHandler:
    if kind not in SOURCE_KIND_HANDLERS:
        known = ", ".join(sorted(SOURCE_KIND_HANDLERS)) or "<none>"
        raise ValueError(f"Unsupported source kind: {kind!r}. Registered: {known}.")
    return SOURCE_KIND_HANDLERS[kind]


__all__ = [
    "DecodeContext",
    "DecodeResult",
    "SOURCE_KIND_HANDLERS",
    "SourceKindHandler",
    "get_source_kind_handler",
    "register_source_kind",
]
