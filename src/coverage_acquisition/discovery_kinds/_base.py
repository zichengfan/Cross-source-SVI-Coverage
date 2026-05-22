"""Discovery-kind plugin contract.

A *discovery kind* enumerates fetch jobs for a provider/request pair. Each kind
lives in its own module (`discovery_kinds/<kind>.py`) and calls
`register_discovery_kind("<kind>", handler)` at import time.
"""

from __future__ import annotations

from collections.abc import Callable

from coverage_acquisition.models import FetchAreaRequest, ProviderDefinition

DiscoveryHandler = Callable[[ProviderDefinition, FetchAreaRequest], list[dict]]

DISCOVERY_KIND_HANDLERS: dict[str, DiscoveryHandler] = {}


def register_discovery_kind(kind: str, handler: DiscoveryHandler) -> None:
    if kind in DISCOVERY_KIND_HANDLERS:
        raise ValueError(f"Discovery kind already registered: {kind!r}")
    DISCOVERY_KIND_HANDLERS[kind] = handler


def get_discovery_kind_handler(kind: str) -> DiscoveryHandler:
    if kind not in DISCOVERY_KIND_HANDLERS:
        known = ", ".join(sorted(DISCOVERY_KIND_HANDLERS)) or "<none>"
        raise ValueError(f"Unsupported discovery kind: {kind!r}. Registered: {known}.")
    return DISCOVERY_KIND_HANDLERS[kind]
