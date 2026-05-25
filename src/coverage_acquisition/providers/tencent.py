"""Tencent Maps Street View coverage (`mobile_street` TXVN tiles).

Tencent Maps Street View coverage is exposed through the proprietary
`mapvectors.map.qq.com/mobile_street` binary vector layer, not a rendered raster
overlay and not standard Mapbox Vector Tiles. The layer uses Tencent's custom
pixel grid, a GCJ-02 datum, and per-region `bl` tile indexes derived from the
street-view region table that Tencent ships as `streetcfg.dat`; this project
uses the committed community-derived `data/external/tencent/streetcfg.json`
region list for reproducible discovery.

This provider crawls only `mapvectors.map.qq.com`. Scouting found no usable
robots.txt there, while `sv.map.qq.com` and `map.qq.com` disallow crawling and
are not fetched by the provider. Tencent's map terms restrict bulk reuse of map
data; this project stores only a derived binary coverage raster and never
Tencent imagery or rendered tiles. Coverage is concentrated in Chinese cities,
with imagery mostly from 2013-2016. No auth or `.env` key is required.
"""

from __future__ import annotations

from coverage_acquisition.models import BoundingBox, ProviderDefinition, SourceDefinition
from coverage_acquisition.providers._registry import register_provider

PROVIDER = ProviderDefinition(
    key="tencent",
    output_namespace="tencent_streetview_coverage",
    run_label_prefix="tencent_streetview",
    default_display_zoom=14,
    coordinate_scheme="tencent_px",
    discovery_kind="tencent_city_bl",
    area_presets={
        "shenzhen_futian_pilot_bbox": BoundingBox(
            min_lon=114.04,
            min_lat=22.52,
            max_lon=114.08,
            max_lat=22.56,
        ),
    },
    sources=(
        SourceDefinition(
            id="tencent_mobile_street",
            kind="tencent_mobile_street",
            # idx and bl are carried as the tile (x, y); lv is the Tencent data
            # level, supplied by the runner as the job's source_zoom ({z}).
            template="https://mapvectors.map.qq.com/mobile_street?df=1&idx={x}&lv={z}&dth=20&bn=1&bl={y}",
            headers={
                "User-Agent": "global-svi-coverage-observatory/0.3",
                "Referer": "https://map.qq.com/",
            },
            expect_content_type_prefix=None,
            storage_subdir="tiles",
            options={
                "data_level": "14",
                "px_scale": "268435456",
                "lat_const_a": "114.59155902616465",
                "streetcfg_path": "data/external/tencent/streetcfg.json",
                "valid_levels": "11,12,13,14,18",
            },
            notes=(
                "Tencent Street View coverage -- proprietary `TXVN` binary vector layer "
                "(`mobile_street`), per-city `bl` enumeration over `streetcfg` regions, "
                "GCJ-02 datum. Presence = >=1 decoded LineString (`body_size>7`)."
            ),
        ),
    ),
)

register_provider(PROVIDER)
