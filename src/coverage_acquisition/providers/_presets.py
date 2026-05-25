"""Shared named area presets.

Legacy presets used by the already-working providers. New providers should
declare their own pilot/area bbox inside their own provider module instead of
adding rows here, to keep this file conflict-free.
"""

from __future__ import annotations

from coverage_acquisition.models import BoundingBox

COMMON_AREA_PRESETS: dict[str, BoundingBox] = {
    "amsterdam_city_bbox_approx": BoundingBox(
        min_lon=4.728,
        min_lat=52.278,
        max_lon=5.079,
        max_lat=52.431,
    ),
    "hong_kong_urban_bbox_approx": BoundingBox(
        min_lon=113.87,
        min_lat=22.19,
        max_lon=114.33,
        max_lat=22.45,
    ),
    "moscow_center_stv_bbox": BoundingBox(
        min_lon=37.53,
        min_lat=55.73,
        max_lon=37.60,
        max_lat=55.76,
    ),
    "abakan_bbox": BoundingBox(
        min_lon=91.54,
        min_lat=53.66,
        max_lon=91.72,
        max_lat=53.79,
    ),
}


def get_area_preset(preset_name: str) -> BoundingBox:
    if preset_name not in COMMON_AREA_PRESETS:
        raise KeyError(f"Unknown area preset: {preset_name}")
    return COMMON_AREA_PRESETS[preset_name]
