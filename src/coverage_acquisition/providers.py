from __future__ import annotations

from coverage_acquisition.models import BoundingBox, DownloadSource, ProviderDefinition, SourceDefinition


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


DIRECT_DOWNLOADS: dict[str, DownloadSource] = {
    "panoramax": DownloadSource(
        provider="panoramax",
        url="https://api.panoramax.xyz/data/geoparquet/panoramax.parquet",
        filename="panoramax.parquet",
        notes=(
            "Weekly GeoParquet export from the Panoramax federated catalog. "
            "Preferred direct-download source for the first Amsterdam pilot."
        ),
    ),
    "panoramax_pg_dump": DownloadSource(
        provider="panoramax_pg_dump",
        url="https://api.panoramax.xyz/data/pg_dump/panoramax.dump",
        filename="panoramax.dump",
        notes=(
            "Heavier fallback than GeoParquet. Only use if the pilot later needs "
            "fields or structure not available in the parquet export."
        ),
    ),
    "svmap_google_index": DownloadSource(
        provider="svmap_google_index",
        url="https://d3q761cy2sygif.cloudfront.net/index.json",
        filename="index.json",
        notes=(
            "Semi-stable archive index for sv-map PMTiles coverage archives. "
            "Use this to locate date-specific coverage packages."
        ),
    ),
}


FRONTEND_NOTES: dict[str, str] = {
    "apple_lookaround": (
        "Use only against a self-hosted or carefully throttled setup. Public lookmap "
        "instance asks users not to automate requests at scale."
    ),
    "mapillary": (
        "Public Mapillary vector tiles still require an access token. Keep token handling "
        "explicit in CLI or notebook calls."
    ),
}


PROVIDERS: dict[str, ProviderDefinition] = {
    "apple_lookaround": ProviderDefinition(
        key="apple_lookaround",
        output_namespace="apple_lookaround_bluelines_layered",
        run_label_prefix="apple_lookaround_layered",
        default_display_zoom=18,
        supports_auto_zoom=True,
        area_presets={"amsterdam_city_bbox_approx": COMMON_AREA_PRESETS["amsterdam_city_bbox_approx"]},
        sources=(
            SourceDefinition(
                id="apple_lookaround_bluelines_raster_2x",
                kind="raster",
                template="https://lookmap.eu.pythonanywhere.com/bluelines_raster_2x/{z}/{x}/{y}.png",
                headers={
                    "Referer": "https://lookmap.eu.pythonanywhere.com/",
                    "User-Agent": "global-svi-coverage-observatory/0.2",
                },
                display_zoom_min=3,
                display_zoom_max=7,
                storage_subdir="raster",
                expect_content_type_prefix="image/",
                notes="Low-zoom raster coverage tiles served directly as PNG.",
            ),
            SourceDefinition(
                id="apple_lookaround_cached_bluelines",
                kind="vector_mvt",
                template="https://lookmap.eu.pythonanywhere.com/bluelines2/{z}/{x}/{y}/",
                headers={
                    "Referer": "https://lookmap.eu.pythonanywhere.com/",
                    "User-Agent": "global-svi-coverage-observatory/0.2",
                },
                display_zoom_min=8,
                display_zoom_max=15,
                layer_names=("panos",),
                storage_subdir="vector_mvt",
                vector_decoder="ogr2ogr",
                notes="Cached vector blue lines. Response body is often gzip-compressed MVT bytes.",
            ),
            SourceDefinition(
                id="apple_lookaround_coverage_tiles",
                kind="coverage_json",
                template="https://lookmap.eu.pythonanywhere.com/tiles/coverage/{x}/{y}/",
                headers={
                    "Referer": "https://lookmap.eu.pythonanywhere.com/",
                    "User-Agent": "global-svi-coverage-observatory/0.2",
                },
                display_zoom_min=16,
                display_zoom_max=20,
                query_zoom=17,
                storage_subdir="coverage_json",
                expect_content_type_prefix="application/json",
                notes="High-zoom pano coverage tiles returned as JSON on a fixed z17 grid.",
            ),
        ),
    ),
    "svmap_google": ProviderDefinition(
        key="svmap_google",
        output_namespace="svmap_google_mts_raster",
        run_label_prefix="svmap_google_mts",
        default_display_zoom=13,
        area_presets={"amsterdam_city_bbox_approx": COMMON_AREA_PRESETS["amsterdam_city_bbox_approx"]},
        sources=(
            SourceDefinition(
                id="svmap_google_mts",
                kind="raster",
                template=(
                    "https://mts.googleapis.com/vt?pb="
                    "!1m4!1m3!1i{z}!2i{x}!3i{y}"
                    "!2m8!1e2!2ssvv"
                    "!4m2!1scc!2s*211m3*211e2*212b1*213e2*212b1*214b1"
                    "!4m2!1ssvl!2s*212b1"
                    "!3m11!2sen!3sUS"
                    "!12m4!1e68!2m2!1sset!2sRoadmap"
                    "!12m3!1e37!2m1!1ssmartmaps"
                    "!5m1!5f1.5"
                ),
                headers={
                    "User-Agent": "global-svi-coverage-observatory/0.2",
                    "Referer": "https://sv-map.netlify.app/",
                },
                storage_subdir="tiles",
                expect_content_type_prefix="image/",
            ),
        ),
    ),
    "kartaview": ProviderDefinition(
        key="kartaview",
        output_namespace="kartaview_coverage_raster",
        run_label_prefix="kartaview_coverage",
        default_display_zoom=13,
        area_presets={"amsterdam_city_bbox_approx": COMMON_AREA_PRESETS["amsterdam_city_bbox_approx"]},
        sources=(
            SourceDefinition(
                id="kartaview_sequence_tiles",
                kind="raster",
                template="https://api.openstreetcam.org/2.0/sequence/tiles/{x}/{y}/{z}.png",
                headers={
                    "User-Agent": "global-svi-coverage-observatory/0.2",
                    "Referer": "https://kartaview.org/",
                },
                storage_subdir="tiles",
                expect_content_type_prefix="image/",
            ),
        ),
    ),
    "panoramax": ProviderDefinition(
        key="panoramax",
        output_namespace="panoramax_mvt_coverage",
        run_label_prefix="panoramax_coverage",
        default_display_zoom=13,
        area_presets={"amsterdam_city_bbox_approx": COMMON_AREA_PRESETS["amsterdam_city_bbox_approx"]},
        sources=(
            SourceDefinition(
                id="panoramax_xyz_mvt",
                kind="vector_mvt",
                template="https://api.panoramax.xyz/api/map/{z}/{x}/{y}.mvt",
                headers={
                    "User-Agent": "global-svi-coverage-observatory/0.2",
                    "Accept": "application/vnd.mapbox-vector-tile, application/octet-stream;q=0.9, */*;q=0.1",
                    "Referer": "https://api.panoramax.xyz/en/index?focus=map",
                },
                layer_names=("sequences",),
                storage_subdir="vector_mvt",
                vector_decoder="custom_mvt",
            ),
        ),
    ),
    "mapillary": ProviderDefinition(
        key="mapillary",
        output_namespace="mapillary_mvt_coverage",
        run_label_prefix="mapillary_coverage",
        default_display_zoom=13,
        area_presets={"amsterdam_city_bbox_approx": COMMON_AREA_PRESETS["amsterdam_city_bbox_approx"]},
        sources=(
            SourceDefinition(
                id="mapillary_mly1_public_vtp",
                kind="vector_mvt",
                template="https://tiles.mapillary.com/maps/vtp/mly1_public/2/{z}/{x}/{y}",
                headers={
                    "User-Agent": "global-svi-coverage-observatory/0.2",
                    "Accept": "application/vnd.mapbox-vector-tile, application/octet-stream;q=0.9, */*;q=0.1",
                    "Referer": "https://www.mapillary.com/",
                },
                layer_names=("sequence",),
                storage_subdir="vector_mvt",
                token_query_param="access_token",
                vector_decoder="custom_mvt",
            ),
        ),
    ),
    "baidu": ProviderDefinition(
        key="baidu",
        output_namespace="baidu_mapsv_raster",
        run_label_prefix="baidu_mapsv",
        default_display_zoom=13,
        coordinate_scheme="baidu",
        area_presets={"hong_kong_urban_bbox_approx": COMMON_AREA_PRESETS["hong_kong_urban_bbox_approx"]},
        sources=(
            SourceDefinition(
                id="baidu_mapsv_tile",
                kind="raster",
                template="https://mapsv0.bdimg.com/tile/?udt=20200825&qt=tile&styles=pl&x={x}&y={y}&z={z}",
                headers={
                    "User-Agent": "global-svi-coverage-observatory/0.2",
                    "Referer": "https://map.baidu.com/",
                },
                storage_subdir="tiles",
                expect_content_type_prefix="image/",
            ),
        ),
    ),
    "yandex": ProviderDefinition(
        key="yandex",
        output_namespace="yandex_stv_raster",
        run_label_prefix="yandex_stv_raster",
        default_display_zoom=13,
        coordinate_scheme="yandex_wgs84_mercator",
        area_presets={
            "moscow_center_stv_bbox": COMMON_AREA_PRESETS["moscow_center_stv_bbox"],
            "abakan_bbox": COMMON_AREA_PRESETS["abakan_bbox"],
        },
        sources=(
            SourceDefinition(
                id="yandex_stv_tiles_png",
                kind="raster",
                template=(
                    "https://core-stv-renderer.maps.yandex.net/2.x/tiles?"
                    "l={layer}&x={x}&y={y}&z={z}&scale=1&v={version}&lang=en_US&format=png"
                ),
                headers={
                    "User-Agent": "global-svi-coverage-observatory/0.2",
                    "Accept": "image/png, image/*;q=0.9, */*;q=0.1",
                    "Referer": "https://yandex.com/maps/",
                },
                storage_subdir="tiles",
                expect_content_type_prefix="image/",
                options={
                    "config_kind": "yandex_stv_renderer",
                    "frontend_page_url": "https://yandex.com/maps/213/moscow/?l=stv&ll=37.565000%2C55.745000&z=13",
                    "layer": "stv",
                    "version_fallback": "2026.05.19.17.14-1_26.05.18-0-29389",
                },
                notes=(
                    "Yandex street-view coverage raster tiles. Tile selection and bounds use "
                    "Yandex's WGS84 elliptic Mercator grid."
                ),
            ),
        ),
    ),
}


DEFAULT_MULTI_SOURCE_PROVIDERS = (
    "apple_lookaround",
    "svmap_google",
    "kartaview",
    "panoramax",
    "mapillary",
    "yandex",
)


def get_provider(provider_key: str) -> ProviderDefinition:
    if provider_key not in PROVIDERS:
        raise KeyError(f"Unknown provider: {provider_key}")
    return PROVIDERS[provider_key]


def get_area_preset(preset_name: str) -> BoundingBox:
    if preset_name not in COMMON_AREA_PRESETS:
        raise KeyError(f"Unknown area preset: {preset_name}")
    return COMMON_AREA_PRESETS[preset_name]
