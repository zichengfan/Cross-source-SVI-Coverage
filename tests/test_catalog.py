"""Tests for STAC catalog maintenance."""

from __future__ import annotations

from datetime import date

from coverage_acquisition.catalog import load_catalog, upsert_provider_item


def test_upsert_provider_item_creates_catalog_with_item(tmp_path) -> None:
    catalog_root = tmp_path / "stac"
    cog_path = tmp_path / "provider.tif"
    cog_path.write_bytes(b"fake cog")

    item = upsert_provider_item(
        catalog_root,
        "provider",
        cog_path,
        bbox=(-1.0, 2.0, 3.0, 4.0),
        scrape_date=date(2026, 5, 20),
        tier="official",
        source_endpoint="https://example.test/tiles/{z}/{x}/{y}.png",
    )

    catalog = load_catalog(catalog_root)
    assert item.id == "provider"
    assert catalog.get_item("provider") is not None


def test_upsert_provider_item_replaces_existing_item(tmp_path) -> None:
    catalog_root = tmp_path / "stac"
    first_cog = tmp_path / "first.tif"
    second_cog = tmp_path / "second.tif"
    first_cog.write_bytes(b"first")
    second_cog.write_bytes(b"second")

    upsert_provider_item(
        catalog_root,
        "provider",
        first_cog,
        bbox=(-1.0, 2.0, 3.0, 4.0),
        scrape_date="2026-05-19",
        tier="first",
        source_endpoint="https://example.test/first",
    )
    upsert_provider_item(
        catalog_root,
        "provider",
        second_cog,
        bbox=(10.0, 20.0, 30.0, 40.0),
        scrape_date="2026-05-20",
        tier="second",
        source_endpoint="https://example.test/second",
    )

    catalog = load_catalog(catalog_root)
    items = list(catalog.get_items())
    assert [item.id for item in items] == ["provider"]
    assert items[0].bbox == [10.0, 20.0, 30.0, 40.0]
    assert items[0].properties["tier"] == "second"


def test_upsert_provider_item_sets_properties_and_bbox(tmp_path) -> None:
    catalog_root = tmp_path / "stac"
    cog_path = tmp_path / "provider.tif"
    cog_path.write_bytes(b"fake cog")

    item = upsert_provider_item(
        catalog_root,
        "provider",
        cog_path,
        bbox=(-1.0, 2.0, 3.0, 4.0),
        scrape_date="2026-05-20",
        tier="community",
        source_endpoint="https://example.test/source",
        tos_notes="public viewer only",
    )

    assert item.bbox == [-1.0, 2.0, 3.0, 4.0]
    assert item.properties["tier"] == "community"
    assert item.properties["source_endpoint"] == "https://example.test/source"
    assert item.properties["tos_notes"] == "public viewer only"
