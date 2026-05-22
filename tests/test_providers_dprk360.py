from __future__ import annotations

import json
from pathlib import Path

from coverage_acquisition.models import BoundingBox, FetchAreaRequest, ProviderDefinition
from coverage_acquisition.providers import PROVIDERS, get_provider
from coverage_acquisition.providers.dprk360 import extract_tour_slugs, parse_inside_north_korea_posts
from coverage_acquisition.runners import build_jobs
from coverage_acquisition.source_kinds import DecodeContext, get_source_kind_handler

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "dprk360"
POINTS_FIXTURE = FIXTURE_DIR / "points.json"


def test_dprk360_registers() -> None:
    assert "dprk360" in PROVIDERS
    provider = get_provider("dprk360")
    assert provider.key == "dprk360"
    assert len(provider.sources) == 1


def test_dprk360_source_is_single_tile_coverage_json(tmp_path: Path) -> None:
    provider = get_provider("dprk360")
    source = provider.sources[0]

    assert source.kind == "coverage_json"
    assert provider.default_display_zoom == 0
    assert source.display_zoom_min == 0
    assert source.display_zoom_max == 0
    assert source.query_zoom is None
    assert source.token_query_param is None

    request = FetchAreaRequest(
        provider="dprk360",
        bbox=BoundingBox(min_lon=124.0, min_lat=37.0, max_lon=131.5, max_lat=43.5),
        output_root=tmp_path,
    )
    job = build_jobs(provider, request)[0]
    assert job["source_tile_range"] == {"x_min": 0, "x_max": 0, "y_min": 0, "y_max": 0}
    assert job["source_tile_count"] == 1


def test_dprk360_coordinate_scheme() -> None:
    assert get_provider("dprk360").coordinate_scheme == "web_mercator"


def test_dprk360_point_table_loads() -> None:
    payload = json.loads(POINTS_FIXTURE.read_text(encoding="utf-8"))
    panos = payload["panos"]

    assert len(panos) == 31
    for pano in panos:
        assert pano["panoid"]
        assert pano["site_name"]
        assert 37.0 <= float(pano["lat"]) <= 43.5
        assert 124.0 <= float(pano["lon"]) <= 131.5
        assert pano["country"] in {"KP", "CN"}


def test_dprk360_point_table_no_dupes() -> None:
    panos = json.loads(POINTS_FIXTURE.read_text(encoding="utf-8"))["panos"]
    coordinates = {(round(float(pano["lat"]), 4), round(float(pano["lon"]), 4)) for pano in panos}
    assert len(coordinates) == len(panos)


def test_dprk360_decode_pano_records(tmp_path: Path) -> None:
    provider = ProviderDefinition(
        key="dprk360",
        output_namespace="dprk360_panorama_points",
        run_label_prefix="dprk360_panorama",
        default_display_zoom=14,
    )
    source = get_provider("dprk360").sources[0]
    ctx = DecodeContext(
        source=source,
        provider=provider,
        job={"display_zoom": 14, "source_zoom": 0},
        x=0,
        y=0,
        tile_url=POINTS_FIXTURE.as_uri(),
        fetched_at="2026-05-22T00:00:00+00:00",
        output_dir=tmp_path,
        wire_payload=POINTS_FIXTURE.read_bytes(),
        content_type="application/json",
        http_status=200,
    )

    result = get_source_kind_handler("coverage_json")(ctx)

    assert result.pano_count == 31
    assert len(result.pano_records) == 31
    assert all(record["provider"] == "dprk360" for record in result.pano_records)
    assert all(record["panoid"] for record in result.pano_records)
    assert all(isinstance(record["lat"], float) for record in result.pano_records)
    assert all(isinstance(record["lon"], float) for record in result.pano_records)


def test_dprk360_post_tour_extraction() -> None:
    html = (FIXTURE_DIR / "post_with_tours.html").read_text(encoding="utf-8")

    assert extract_tour_slugs(html) == ("air_koryo_il-18", "air_koryo_il-76", "kpaaf_mi-17")


def test_dprk360_wp_posts_parse() -> None:
    posts = json.loads((FIXTURE_DIR / "wp_posts.json").read_text(encoding="utf-8"))

    inside_posts = parse_inside_north_korea_posts(posts)

    assert len(inside_posts) == 44
    assert all(post.category_ids == (2,) for post in inside_posts)
    assert all("/inside-north-korea/" in post.link for post in inside_posts)
