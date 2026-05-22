"""Discovery-kind plugin package.

Auto-imports every non-underscore module so each kind self-registers. A new
discovery kind is one new file `discovery_kinds/<kind>.py` calling
`register_discovery_kind(...)` -- `runners.py` only dispatches and is never edited.
"""

from __future__ import annotations

import importlib
import pkgutil

from coverage_acquisition.discovery_kinds._base import (
    DISCOVERY_KIND_HANDLERS,
    DiscoveryHandler,
    get_discovery_kind_handler,
    register_discovery_kind,
)


def _discover_discovery_kinds() -> None:
    for module_info in pkgutil.iter_modules(__path__):
        if module_info.name.startswith("_"):
            continue
        importlib.import_module(f"{__name__}.{module_info.name}")


_discover_discovery_kinds()


__all__ = [
    "DISCOVERY_KIND_HANDLERS",
    "DiscoveryHandler",
    "get_discovery_kind_handler",
    "register_discovery_kind",
]
