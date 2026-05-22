"""Runtime-config plugin contract.

Runtime config handlers discover live provider values needed to build tile URLs.
Each provider-specific config lives in its own module (`runtime_config/<kind>.py`)
and calls `register_runtime_config("<kind>", handler)` at import time.
"""

from __future__ import annotations

from collections.abc import Callable

from coverage_acquisition.models import FetchAreaRequest, SourceDefinition

RuntimeConfigHandler = Callable[[SourceDefinition, FetchAreaRequest], dict]

RUNTIME_CONFIG_HANDLERS: dict[str, RuntimeConfigHandler] = {}


def register_runtime_config(kind: str, handler: RuntimeConfigHandler) -> None:
    if kind in RUNTIME_CONFIG_HANDLERS:
        raise ValueError(f"Runtime config already registered: {kind!r}")
    RUNTIME_CONFIG_HANDLERS[kind] = handler
