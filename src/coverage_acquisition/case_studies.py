from __future__ import annotations

from dataclasses import dataclass

from pyproj import Transformer

from coverage_acquisition.geo import tile_range_for_bbox
from coverage_acquisition.models import BoundingBox
from coverage_acquisition.providers import PROVIDERS
from coverage_acquisition.runners import resolve_source_for_display_zoom

TENCENT_KEY = "tencent_pmtiles_sv"
MAPPLS_KEY = "mappls"
DEDICATED_PROVIDER_KEYS = frozenset({TENCENT_KEY, MAPPLS_KEY})
MULTISCALE_LEVELS = tuple(range(10, 19))
KAKAO_MULTISCALE_LEVELS = tuple(range(10, 1, -1))


@dataclass(frozen=True)
class ProviderLevel:
    provider: str
    requested_level: int


@dataclass(frozen=True)
class AreaComparisonCase:
    key: str
    label: str
    bbox: BoundingBox
    providers: tuple[ProviderLevel, ...]


@dataclass(frozen=True)
class MultiscaleCase:
    provider: str
    label: str
    area: str
    anchor_lon: float
    anchor_lat: float


def _bbox(west: float, south: float, east: float, north: float) -> BoundingBox:
    return BoundingBox(min_lon=west, min_lat=south, max_lon=east, max_lat=north)


AREA_COMPARISON_CASES = (
    AreaComparisonCase(
        "shenzhen_futian",
        "Shenzhen Futian",
        _bbox(114.02, 22.50, 114.08, 22.56),
        (ProviderLevel("baidu", 18), ProviderLevel(TENCENT_KEY, 12)),
    ),
    AreaComparisonCase(
        "hong_kong_core",
        "Hong Kong Island + Kowloon",
        _bbox(114.10, 22.25, 114.25, 22.35),
        (
            ProviderLevel("svmap_google", 13),
            ProviderLevel("apple_lookaround", 13),
            ProviderLevel("baidu", 13),
            ProviderLevel(TENCENT_KEY, 12),
        ),
    ),
    AreaComparisonCase(
        "seoul_center",
        "Central Seoul",
        _bbox(126.965, 37.555, 127.005, 37.585),
        (ProviderLevel("svmap_google", 15), ProviderLevel("naver", 15), ProviderLevel("kakao", 5)),
    ),
    AreaComparisonCase(
        "chiang_mai",
        "Chiang Mai",
        _bbox(98.899549, 18.697236, 99.073957, 18.864633),
        (ProviderLevel("svmap_google", 14), ProviderLevel("mapjack", 14)),
    ),
    AreaComparisonCase(
        "hanoi_core",
        "Hanoi Old Quarter",
        _bbox(105.820, 21.015, 105.860, 21.045),
        (
            ProviderLevel("svmap_google", 16),
            ProviderLevel("kartaview", 13),
            ProviderLevel("mapillary", 13),
            ProviderLevel("streetview_vn", 13),
        ),
    ),
    AreaComparisonCase(
        "moscow_center",
        "Central Moscow",
        _bbox(37.53, 55.73, 37.60, 55.76),
        (ProviderLevel("svmap_google", 16), ProviderLevel("yandex", 16)),
    ),
    AreaComparisonCase(
        "new_delhi",
        "New Delhi",
        _bbox(77.205, 28.625, 77.228, 28.642),
        (ProviderLevel(MAPPLS_KEY, 16), ProviderLevel("svmap_google", 16)),
    ),
    AreaComparisonCase(
        "dhaka",
        "Dhaka",
        _bbox(90.396, 23.806, 90.417, 23.825),
        (ProviderLevel("barikoi", 16), ProviderLevel("svmap_google", 16)),
    ),
    AreaComparisonCase(
        "istanbul_beyoglu",
        "Istanbul Beyoglu",
        _bbox(28.96, 41.00, 29.00, 41.03),
        (
            ProviderLevel("svmap_google", 14),
            ProviderLevel("mapilio", 14),
            ProviderLevel("mapillary", 14),
            ProviderLevel("panoramax", 14),
            ProviderLevel("kartaview", 14),
            ProviderLevel("yandex", 14),
        ),
    ),
    AreaComparisonCase(
        "prague_center",
        "Prague city centre",
        _bbox(14.40, 50.075, 14.44, 50.095),
        (
            ProviderLevel("svmap_google", 14),
            ProviderLevel("apple_lookaround", 14),
            ProviderLevel("mapillary", 14),
            ProviderLevel("kartaview", 14),
            ProviderLevel("panoramax", 14),
            ProviderLevel("mapilio", 14),
            ProviderLevel("mapy", 14),
        ),
    ),
)


MULTISCALE_CASES = (
    MultiscaleCase("svmap_google", "Google Street View", "Prague", 14.425020, 50.085362),
    MultiscaleCase("apple_lookaround", "Apple Look Around", "Prague", 14.415076, 50.087141),
    MultiscaleCase("baidu", "Baidu", "Shenzhen", 114.066504, 22.525611),
    MultiscaleCase(TENCENT_KEY, "Tencent Street View", "Shenzhen", 114.020026, 22.559943),
    MultiscaleCase("naver", "Naver", "Seoul", 126.996438, 37.566368),
    MultiscaleCase("kakao", "Kakao", "Seoul", 126.987129, 37.572159),
    MultiscaleCase("mapjack", "MapJack", "Chiang Mai", 98.997760, 18.781313),
    MultiscaleCase("kartaview", "KartaView", "Prague", 14.403827, 50.075003),
    MultiscaleCase("mapillary", "Mapillary", "Prague", 14.409825, 50.082095),
    MultiscaleCase("streetview_vn", "Streetview.vn", "Hanoi", 105.821300, 21.015541),
    MultiscaleCase("yandex", "Yandex", "Moscow", 37.537526, 55.749706),
    MultiscaleCase(MAPPLS_KEY, "Mappls RealView", "New Delhi", 77.216530, 28.633350),
    MultiscaleCase("barikoi", "Barikoi ThirdEye360", "Dhaka", 90.396020, 23.819705),
    MultiscaleCase("panoramax", "Panoramax", "Prague", 14.420521, 50.075024),
    MultiscaleCase("mapilio", "Mapilio", "Istanbul", 28.960444, 41.003108),
    MultiscaleCase("mapy", "Mapy.com", "Prague", 14.425435, 50.075017),
)

PROVIDER_LABELS = {case.provider: case.label for case in MULTISCALE_CASES}
PROVIDER_LABELS.update({TENCENT_KEY: "Tencent Street View", MAPPLS_KEY: "Mappls RealView"})


def area_case(case_key: str) -> AreaComparisonCase:
    for case in AREA_COMPARISON_CASES:
        if case.key == case_key:
            return case
    raise KeyError(f"Unknown area comparison case: {case_key}")


def multiscale_case(provider_key: str) -> MultiscaleCase:
    for case in MULTISCALE_CASES:
        if case.provider == provider_key:
            return case
    raise KeyError(f"Unknown multiscale provider: {provider_key}")


def multiscale_probe_bbox(case: MultiscaleCase, half_span_degrees: float = 0.0004) -> BoundingBox:
    if half_span_degrees <= 0:
        raise ValueError("half_span_degrees must be positive")
    return _bbox(
        case.anchor_lon - half_span_degrees,
        case.anchor_lat - half_span_degrees,
        case.anchor_lon + half_span_degrees,
        case.anchor_lat + half_span_degrees,
    )


def fixed_extent_bbox(case: MultiscaleCase, size_m: float = 1_000.0) -> BoundingBox:
    if size_m <= 0:
        raise ValueError("size_m must be positive")
    zone = int((case.anchor_lon + 180.0) // 6.0) + 1
    epsg = 32600 + zone if case.anchor_lat >= 0 else 32700 + zone
    to_local = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
    to_wgs84 = Transformer.from_crs(f"EPSG:{epsg}", "EPSG:4326", always_xy=True)
    center_x, center_y = to_local.transform(case.anchor_lon, case.anchor_lat)
    half_size = size_m / 2.0
    west, south = to_wgs84.transform(center_x - half_size, center_y - half_size)
    east, north = to_wgs84.transform(center_x + half_size, center_y + half_size)
    return _bbox(west, south, east, north)


def provider_multiscale_levels(provider_key: str) -> tuple[int, ...]:
    multiscale_case(provider_key)
    return KAKAO_MULTISCALE_LEVELS if provider_key == "kakao" else MULTISCALE_LEVELS


def multiscale_plan(levels: tuple[int, ...] | None = None) -> list[dict]:
    rows: list[dict] = []
    for case in MULTISCALE_CASES:
        requested_levels = provider_multiscale_levels(case.provider) if levels is None else levels
        for requested_level in requested_levels:
            rows.append(_multiscale_plan_row(case, int(requested_level)))
    return rows


def _multiscale_plan_row(case: MultiscaleCase, requested_level: int) -> dict:
    base = {
        "provider": case.provider,
        "display_name": case.label,
        "area": case.area,
        "requested_level": requested_level,
        "level_semantics": "native_level" if case.provider == "kakao" else "xyz_zoom",
        "effective_source_level": None,
        "source_id": None,
        "source_kind": None,
        "planned_tiles": None,
        "plan_status": "planned",
        "note": "",
    }

    if case.provider == TENCENT_KEY:
        if requested_level != 12:
            return {**base, "plan_status": "unsupported", "note": "The retained PMTiles baseline is native z12 only."}
        return {
            **base,
            "effective_source_level": 12,
            "source_id": "qq_map_lines_pmtiles_sv",
            "source_kind": "vector_mvt",
            "planned_tiles": 1,
            "plan_status": "native_archive",
        }

    if case.provider == MAPPLS_KEY:
        return {
            **base,
            "effective_source_level": requested_level,
            "source_id": "mappls_realview_sdk",
            "source_kind": "vector_mvt",
            "plan_status": "access_gated",
            "note": "Requires an authorized local Web SDK configuration.",
        }

    provider = PROVIDERS[case.provider]
    try:
        source = resolve_source_for_display_zoom(provider, requested_level)
    except ValueError:
        return {**base, "plan_status": "unsupported", "note": "Outside the declared source level range."}

    source_level = int(source.query_zoom or requested_level)
    roi = fixed_extent_bbox(case)
    tile_count = tile_range_for_bbox(roi, source_level, provider.coordinate_scheme).count
    row = {
        **base,
        "effective_source_level": source_level,
        "source_id": source.id,
        "source_kind": source.kind,
        "planned_tiles": tile_count,
    }

    if case.provider == "mapillary":
        return {**row, "plan_status": "requires_token", "note": "Set MAPILLARY_ACCESS_TOKEN."}
    if case.provider == "apple_lookaround":
        return {**row, "plan_status": "access_gated", "note": "Use only an authorized or self-hosted endpoint."}
    return row


def validate_multiscale_probe(provider_key: str, requested_level: int) -> dict:
    case = multiscale_case(provider_key)
    row = _multiscale_plan_row(case, requested_level)
    if row["plan_status"] == "unsupported":
        raise ValueError(
            f"Unsupported multiscale probe: {provider_key} level {requested_level} "
            f"({row['plan_status']}): {row['note']}"
        )
    return row


def validate_case_contract() -> None:
    registry_keys = set(PROVIDERS)
    compared = {level.provider for case in AREA_COMPARISON_CASES for level in case.providers}
    audited = {case.provider for case in MULTISCALE_CASES}
    expected = registry_keys | set(DEDICATED_PROVIDER_KEYS)
    if compared != expected:
        raise AssertionError(f"Area comparison providers differ from the implemented set: {compared ^ expected}")
    if audited != expected:
        raise AssertionError(f"Multiscale providers differ from the implemented set: {audited ^ expected}")


validate_case_contract()
