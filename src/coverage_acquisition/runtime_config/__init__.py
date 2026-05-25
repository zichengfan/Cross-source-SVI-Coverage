"""Runtime-config plugin package.

Auto-imports every non-underscore module so each runtime-config kind
self-registers. A new provider runtime config is one new file
`runtime_config/<kind>.py` calling `register_runtime_config(...)`.
"""

from __future__ import annotations

import importlib
import pkgutil

from coverage_acquisition.models import FetchAreaRequest, SourceDefinition
from coverage_acquisition.runtime_config._base import (
    RUNTIME_CONFIG_HANDLERS,
    RuntimeConfigHandler,
    register_runtime_config,
)


def _discover_runtime_config_handlers() -> None:
    for module_info in pkgutil.iter_modules(__path__):
        if module_info.name.startswith("_"):
            continue
        importlib.import_module(f"{__name__}.{module_info.name}")


_discover_runtime_config_handlers()


def get_runtime_config_handler(kind: str) -> RuntimeConfigHandler:
    if kind not in RUNTIME_CONFIG_HANDLERS:
        known = ", ".join(sorted(RUNTIME_CONFIG_HANDLERS)) or "<none>"
        raise ValueError(f"Unsupported runtime config kind: {kind!r}. Registered: {known}.")
    return RUNTIME_CONFIG_HANDLERS[kind]


def build_runtime_options(source: SourceDefinition, request: FetchAreaRequest) -> dict:
    config_kind = source.options.get("config_kind")
    if not config_kind or config_kind not in RUNTIME_CONFIG_HANDLERS:
        return {}
    return RUNTIME_CONFIG_HANDLERS[config_kind](source, request)


__all__ = [
    "RUNTIME_CONFIG_HANDLERS",
    "RuntimeConfigHandler",
    "build_runtime_options",
    "get_runtime_config_handler",
    "register_runtime_config",
]
