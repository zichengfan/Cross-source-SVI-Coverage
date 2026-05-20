"""Provider registry.

Each provider lives in its own module (`providers/<key>.py`) and calls
`register_provider(PROVIDER)` at import time. The package `__init__` auto-imports
every provider module, so adding a provider never edits a shared file.
"""

from __future__ import annotations

from coverage_acquisition.models import ProviderDefinition

PROVIDERS: dict[str, ProviderDefinition] = {}

# Curated default set for the `fetch-multi` Amsterdam comparison.
DEFAULT_MULTI_SOURCE_PROVIDERS: tuple[str, ...] = (
    "apple_lookaround",
    "svmap_google",
    "kartaview",
    "panoramax",
    "mapillary",
    "yandex",
)


def register_provider(definition: ProviderDefinition) -> ProviderDefinition:
    """Register a provider. Call once at module level in each provider module."""
    if definition.key in PROVIDERS:
        raise ValueError(f"Provider already registered: {definition.key!r}")
    PROVIDERS[definition.key] = definition
    return definition


def get_provider(provider_key: str) -> ProviderDefinition:
    if provider_key not in PROVIDERS:
        raise KeyError(f"Unknown provider: {provider_key}")
    return PROVIDERS[provider_key]
