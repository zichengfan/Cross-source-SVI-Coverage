from __future__ import annotations

import pytest
from pyproj import Transformer

from coverage_acquisition.case_studies import (
    AREA_COMPARISON_CASES,
    KAKAO_MULTISCALE_LEVELS,
    MULTISCALE_CASES,
    MULTISCALE_LEVELS,
    fixed_extent_bbox,
    multiscale_plan,
    provider_multiscale_levels,
    validate_case_contract,
    validate_multiscale_probe,
)
from coverage_acquisition.providers import PROVIDERS


def test_area_and_multiscale_contracts_cover_all_sixteen_paths():
    validate_case_contract()
    expected = set(PROVIDERS) | {"tencent_pmtiles_sv", "mappls"}
    assert len(expected) == 16
    assert {item.provider for case in AREA_COMPARISON_CASES for item in case.providers} == expected
    assert {case.provider for case in MULTISCALE_CASES} == expected


def test_barikoi_multiscale_policy_uses_every_declared_level():
    assert "barikoi" in PROVIDERS
    rows = {row["requested_level"]: row for row in multiscale_plan() if row["provider"] == "barikoi"}

    assert all(rows[level]["plan_status"] == "planned" for level in range(10, 19))
    assert all(rows[level]["source_id"] == "barikoi_thirdeye360_mvt" for level in range(10, 19))


def test_barikoi_declared_multiscale_levels_are_allowed():
    with pytest.raises(ValueError, match="unsupported"):
        validate_multiscale_probe("barikoi", 6)

    allowed = validate_multiscale_probe("barikoi", 10)
    assert allowed["plan_status"] == "planned"
    assert allowed["effective_source_level"] == 10


def test_multiscale_plan_is_complete_and_deterministic():
    rows = multiscale_plan()
    assert len(rows) == 16 * 9
    assert len({(row["provider"], row["requested_level"]) for row in rows}) == len(rows)


def test_kakao_levels_follow_the_native_reverse_direction():
    assert KAKAO_MULTISCALE_LEVELS == tuple(range(10, 1, -1))
    assert provider_multiscale_levels("kakao") == KAKAO_MULTISCALE_LEVELS
    assert provider_multiscale_levels("naver") == MULTISCALE_LEVELS
    assert [
        row["requested_level"] for row in multiscale_plan() if row["provider"] == "kakao"
    ] == list(KAKAO_MULTISCALE_LEVELS)


def test_fixed_extent_bbox_is_one_kilometre_around_existing_anchor():
    case = next(case for case in MULTISCALE_CASES if case.provider == "baidu")
    bbox = fixed_extent_bbox(case)
    assert bbox.min_lon < case.anchor_lon < bbox.max_lon
    assert bbox.min_lat < case.anchor_lat < bbox.max_lat

    zone = int((case.anchor_lon + 180.0) // 6.0) + 1
    transformer = Transformer.from_crs("EPSG:4326", f"EPSG:{32600 + zone}", always_xy=True)
    west, south = transformer.transform(bbox.min_lon, bbox.min_lat)
    east, north = transformer.transform(bbox.max_lon, bbox.max_lat)
    assert east - west == pytest.approx(1_000.0, abs=1.0)
    assert north - south == pytest.approx(1_000.0, abs=1.0)
