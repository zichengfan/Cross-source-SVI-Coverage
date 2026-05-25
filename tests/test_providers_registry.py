"""Tests for the auto-discovering provider registry."""

from __future__ import annotations

import pytest

from coverage_acquisition.models import ProviderDefinition
from coverage_acquisition.providers import PROVIDERS, get_provider
from coverage_acquisition.providers._registry import register_provider

ALREADY_WORKING = {
    "apple_lookaround",
    "baidu",
    "kartaview",
    "mapillary",
    "panoramax",
    "svmap_google",
    "yandex",
}


def test_all_working_providers_auto_registered():
    assert ALREADY_WORKING.issubset(set(PROVIDERS))


def test_get_provider_returns_definition():
    provider = get_provider("yandex")
    assert isinstance(provider, ProviderDefinition)
    assert provider.key == "yandex"


def test_get_provider_unknown_raises():
    with pytest.raises(KeyError):
        get_provider("does_not_exist")


def test_every_provider_has_at_least_one_source():
    for key, provider in PROVIDERS.items():
        assert provider.sources, f"{key} has no sources"


def test_register_duplicate_provider_rejected():
    existing = get_provider("yandex")
    with pytest.raises(ValueError):
        register_provider(existing)


def test_provider_keys_match_registry_keys():
    for key, provider in PROVIDERS.items():
        assert provider.key == key
