from __future__ import annotations

import pytest

from coverage_acquisition.case_studies import (
    AREA_COMPARISON_CASES,
    MULTISCALE_CASES,
    multiscale_plan,
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

    assert rows[5]["plan_status"] == "unsupported"
    assert rows[6]["plan_status"] == "unsupported"
    assert all(rows[level]["plan_status"] == "planned" for level in range(7, 18))
    assert all(rows[level]["source_id"] == "barikoi_thirdeye360_mvt" for level in range(7, 18))


def test_barikoi_declared_multiscale_levels_are_allowed():
    with pytest.raises(ValueError, match="unsupported"):
        validate_multiscale_probe("barikoi", 6)

    allowed = validate_multiscale_probe("barikoi", 7)
    assert allowed["plan_status"] == "planned"
    assert allowed["effective_source_level"] == 7


def test_multiscale_plan_is_complete_and_deterministic():
    rows = multiscale_plan()
    assert len(rows) == 16 * 13
    assert len({(row["provider"], row["requested_level"]) for row in rows}) == len(rows)
