"""Provider package.

Public surface is unchanged from the old single-file `providers.py`:
`PROVIDERS`, `get_provider`, `COMMON_AREA_PRESETS`, `get_area_preset`,
`DIRECT_DOWNLOADS`, `FRONTEND_NOTES`, `DEFAULT_MULTI_SOURCE_PROVIDERS`.

Every non-underscore module in this package is auto-imported on first import so
its `register_provider(...)` call runs. Add a provider by dropping a new
`providers/<key>.py` file in — no shared file needs editing.
"""

from __future__ import annotations

import importlib
import pkgutil

from coverage_acquisition.providers._downloads import DIRECT_DOWNLOADS, FRONTEND_NOTES
from coverage_acquisition.providers._presets import COMMON_AREA_PRESETS, get_area_preset
from coverage_acquisition.providers._registry import (
    DEFAULT_MULTI_SOURCE_PROVIDERS,
    PROVIDERS,
    get_provider,
    register_provider,
)


def _discover_providers() -> None:
    """Import every provider module so it self-registers."""
    for module_info in pkgutil.iter_modules(__path__):
        if module_info.name.startswith("_"):
            continue
        importlib.import_module(f"{__name__}.{module_info.name}")


_discover_providers()


__all__ = [
    "COMMON_AREA_PRESETS",
    "DEFAULT_MULTI_SOURCE_PROVIDERS",
    "DIRECT_DOWNLOADS",
    "FRONTEND_NOTES",
    "PROVIDERS",
    "get_area_preset",
    "get_provider",
    "register_provider",
]
