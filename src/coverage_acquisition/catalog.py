"""Maintain the STAC catalog for processed provider coverage COGs."""

from __future__ import annotations

from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Sequence

import pystac


def upsert_provider_item(
    catalog_root: str | Path,
    provider_key: str,
    cog_path: str | Path,
    *,
    bbox: Sequence[float],
    scrape_date: str | date | datetime,
    tier: str,
    source_endpoint: str,
    tos_notes: str = "",
) -> pystac.Item:
    """Add or replace a provider Item in a self-contained STAC catalog."""
    root = Path(catalog_root)
    root.mkdir(parents=True, exist_ok=True)
    catalog = load_catalog(root) if (root / "catalog.json").exists() else _new_catalog(root)
    bbox_values = [float(value) for value in bbox]
    item = pystac.Item(
        id=provider_key,
        geometry=_bbox_geometry(bbox_values),
        bbox=bbox_values,
        datetime=_scrape_datetime(scrape_date),
        properties={
            "tier": tier,
            "source_endpoint": source_endpoint,
            "tos_notes": tos_notes,
        },
    )
    item.add_asset(
        "coverage",
        pystac.Asset(
            href=str(Path(cog_path)),
            media_type=pystac.MediaType.COG,
            roles=["data"],
            title=f"{provider_key} coverage COG",
        ),
    )

    existing = next(catalog.get_items(provider_key), None)
    if existing is not None:
        catalog.remove_item(provider_key)
    catalog.add_item(item)
    catalog.normalize_hrefs(str(root))
    catalog.save(catalog_type=pystac.CatalogType.SELF_CONTAINED)
    return item


def load_catalog(catalog_root: str | Path) -> pystac.Catalog:
    """Load a STAC catalog rooted at `catalog_root`."""
    return pystac.Catalog.from_file(str(Path(catalog_root) / "catalog.json"))


def _new_catalog(root: Path) -> pystac.Catalog:
    catalog = pystac.Catalog(
        id="cross-source-svi-coverage",
        description="Cross-source street-level imagery coverage rasters.",
    )
    catalog.set_self_href(str(root / "catalog.json"))
    return catalog


def _bbox_geometry(bbox: Sequence[float]) -> dict[str, object]:
    west, south, east, north = bbox
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [west, south],
                [east, south],
                [east, north],
                [west, north],
                [west, south],
            ]
        ],
    }


def _scrape_datetime(value: str | date | datetime) -> datetime:
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, date):
        result = datetime.combine(value, time.min)
    else:
        result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        return result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)
