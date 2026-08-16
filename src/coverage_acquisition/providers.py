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
    "seoul_center_bbox": BoundingBox(
        min_lon=126.965,
        min_lat=37.555,
        max_lon=127.005,
        max_lat=37.585,
    ),
    "chiang_mai_bbox": BoundingBox(
        min_lon=98.899549,
        min_lat=18.697236,
        max_lon=99.073957,
        max_lat=18.864633,
    ),
    "hanoi_center_bbox": BoundingBox(
        min_lon=105.820,
        min_lat=21.015,
        max_lon=105.860,
        max_lat=21.045,
    ),
    "istanbul_beyoglu_pilot_bbox": BoundingBox(
        min_lon=28.96,
        min_lat=41.00,
        max_lon=29.00,
        max_lat=41.03,
    ),
    "prague_centre_pilot_bbox": BoundingBox(
        min_lon=14.40,
        min_lat=50.075,
        max_lon=14.44,
        max_lat=50.095,
    ),
    "dhaka_thirdeye360_pilot_bbox": BoundingBox(
        min_lon=90.396,
        min_lat=23.806,
        max_lon=90.417,
        max_lat=23.825,
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
    "naver": ProviderDefinition(
        key="naver",
        output_namespace="naver_streetview_raster",
        run_label_prefix="naver_streetview",
        default_display_zoom=15,
        area_presets={"seoul_center_bbox": COMMON_AREA_PRESETS["seoul_center_bbox"]},
        sources=(
            SourceDefinition(
                id="naver_streetview_overlay_png",
                kind="raster",
                template=("https://map.pstatic.net/nrb/styles/basic/1778829614/{z}/{x}/{y}.png?mt=ps"),
                headers={
                    "User-Agent": "global-svi-coverage-observatory/0.2",
                    "Accept": "image/png, image/*;q=0.9, */*;q=0.1",
                    "Referer": "https://map.naver.com/",
                },
                storage_subdir="tiles",
                expect_content_type_prefix="image/",
                options={
                    "config_kind": "naver_panorama",
                    "version_fallback": "1778829614",
                },
                notes=("Naver street-only panorama coverage raster; mt=ps mirrors StreetLayer.setAirWaterView(false)."),
            ),
        ),
    ),
    "kakao": ProviderDefinition(
        key="kakao",
        output_namespace="kakao_roadview_overlay_raster",
        run_label_prefix="kakao_roadview",
        default_display_zoom=5,
        coordinate_scheme="kakao",
        area_presets={"seoul_center_bbox": COMMON_AREA_PRESETS["seoul_center_bbox"]},
        sources=(
            SourceDefinition(
                id="kakao_roadviewline",
                kind="raster",
                template=(
                    "https://mts.daumcdn.net/api/v1/tile/PNG_RV02/v17_ftuah/latest/{level}/{tile_y}/{tile_x}.png"
                ),
                headers={
                    "User-Agent": "global-svi-coverage-observatory/0.2",
                    "Accept": "image/png, image/*;q=0.9, */*;q=0.1",
                    "Referer": "https://map.kakao.com/",
                },
                storage_subdir="tiles",
                expect_content_type_prefix="image/",
                options={"config_kind": "kakao_roadview"},
                notes="Kakao Roadview raster on the native EPSG:5181-derived tile grid.",
            ),
        ),
    ),
    "streetview_vn": ProviderDefinition(
        key="streetview_vn",
        output_namespace="streetview_vn_mvt_coverage",
        run_label_prefix="streetview_vn_coverage",
        default_display_zoom=13,
        coordinate_scheme="web_mercator",
        area_presets={"hanoi_center_bbox": COMMON_AREA_PRESETS["hanoi_center_bbox"]},
        sources=(
            SourceDefinition(
                id="streetview_vn_snap_mvt",
                kind="vector_mvt",
                template="https://gpx-view.ndamaps.vn/snap/{z}/{x}/{y}.mvt",
                headers={
                    "User-Agent": "global-svi-coverage-observatory/0.3",
                    "Accept": "application/vnd.mapbox-vector-tile, application/octet-stream;q=0.9, */*;q=0.1",
                    "Referer": "https://view.ndamaps.vn/",
                },
                layer_names=("sequences",),
                storage_subdir="vector_mvt",
                vector_decoder="custom_mvt",
                display_zoom_min=6,
                display_zoom_max=18,
                notes=(
                    "NDAVIEW / Streetview.vn panorama-coverage MVT -- `sequences` "
                    "MultiLineString capture traces. Empty tiles return HTTP 404. "
                    "Vietnam only; carries a per-feature `date`. Endpoint confirmed live "
                    "(z12-z14 tested) on 2026-08-02; z12 tiles are large (~500KB) since "
                    "the tileset has no feature/tile-size limits, so prefer z13+ for "
                    "fetches."
                ),
            ),
        ),
    ),
    "mapjack": ProviderDefinition(
        key="mapjack",
        output_namespace="mapjack_dots_r5_raster",
        run_label_prefix="mapjack_dots_r5",
        default_display_zoom=14,
        coordinate_scheme="web_mercator",
        area_presets={"chiang_mai_bbox": COMMON_AREA_PRESETS["chiang_mai_bbox"]},
        sources=(
            SourceDefinition(
                id="mapjack_dots_r5",
                kind="raster",
                template="https://www.mapjack.com/dots_r5/{z}/{x}/{z}_{x}_{y}.gif",
                headers={
                    "User-Agent": "global-svi-coverage-observatory/0.3 (MapJack coverage alpha raster)",
                    "Accept": "image/gif,image/*;q=0.9,*/*;q=0.1",
                    "Referer": "https://www.mapjack.com/",
                },
                display_zoom_min=12,
                display_zoom_max=17,
                expect_content_type_prefix="image/",
                storage_subdir="tiles",
                options={
                    "coverage_from": "alpha",
                    "absent_tile_status": "404",
                    "overlay_folder": "dots_r5",
                },
                notes=(
                    "MapJack dots_r5 street-view coverage overlay GIF tiles. "
                    "Live overlay config (dots_r5 folder, zoom range) confirmed against "
                    "mapjack.com/config.js and index_min.js on 2026-07-31: tiles are a "
                    "standard z0-z17 web-mercator XYZ pyramid with real coverage data "
                    "present at every zoom (not just z16), so display_zoom directly "
                    "controls the fetch resolution -- no fixed query_zoom override. "
                    "The origin (openresty + a WAF/CDN layer) 403s on rapid bursts of "
                    "consecutive requests; keep request rates low (this runner has no "
                    "built-in throttling) and prefer a low display zoom for pilot runs "
                    "to keep tile counts small. "
                    "Presence = non-transparent pixels (alpha>0); the project stores "
                    "only the derived binary-presence raster, not MapJack imagery or "
                    "dot coordinates. MapJack Terms forbid bulk downloads of imagery/"
                    "numerical data; robots.txt is 404; fetches are anonymous over HTTPS."
                ),
            ),
        ),
    ),
    "mapilio": ProviderDefinition(
        key="mapilio",
        output_namespace="mapilio_mvt_coverage",
        run_label_prefix="mapilio_coverage",
        default_display_zoom=14,
        coordinate_scheme="web_mercator",
        request_timeout_seconds=60,
        area_presets={
            "istanbul_beyoglu_pilot_bbox": COMMON_AREA_PRESETS["istanbul_beyoglu_pilot_bbox"],
        },
        sources=(
            SourceDefinition(
                id="mapilio_map_roads_line_vtp",
                kind="vector_mvt",
                template="https://geo.mapilio.com/map/{x}/{y}/{z}",
                headers={
                    "User-Agent": "global-svi-coverage-observatory/0.3",
                    "Accept": "application/vnd.mapbox-vector-tile, application/octet-stream;q=0.9, */*;q=0.1",
                    "Referer": "https://mapilio.com/",
                },
                layer_names=("map_roads_line",),
                storage_subdir="vector_mvt",
                vector_decoder="custom_mvt",
                notes=(
                    "Mapilio public coverage MVT layer `map_roads_line`; this is coverage, "
                    "not panorama imagery. The endpoint uses non-standard `{x}/{y}/{z}` "
                    "path order. Zero-byte HTTP 200 responses are checked-empty tiles. "
                    "Dense tiles can time out at the origin, so callers must keep "
                    "stop_on_error=False and retain failed tiles as unresolved."
                ),
            ),
        ),
    ),
    "mapy": ProviderDefinition(
        key="mapy",
        output_namespace="mapy_panorama_raster",
        run_label_prefix="mapy_panorama",
        default_display_zoom=14,
        coordinate_scheme="web_mercator",
        area_presets={
            "prague_centre_pilot_bbox": COMMON_AREA_PRESETS["prague_centre_pilot_bbox"],
        },
        sources=(
            SourceDefinition(
                id="mapy_panorama_lines",
                kind="raster",
                template="https://mapserver.mapy.cz/panorama_ln_hybrid-m/{z}-{x}-{y}",
                headers={
                    "User-Agent": "global-svi-coverage-observatory/0.3",
                    "Accept": "image/png, image/*;q=0.9, */*;q=0.1",
                    "Referer": "https://mapy.com/",
                },
                storage_subdir="tiles",
                expect_content_type_prefix="image/",
                options={
                    "coverage_from": "alpha",
                    "empty_tile_rule": "transparent_png",
                },
                notes=(
                    "Mapy.com Panorama line-coverage overlay, not imagery. The endpoint "
                    "uses a hyphen-joined `{z}-{x}-{y}` path. Empty tiles redirect to a "
                    "fully transparent default PNG; the Mapy Referer must be retained "
                    "or the empty-tile path may return HTTP 403. Coverage is Czech-only "
                    "in current observations."
                ),
            ),
        ),
    ),
    "barikoi": ProviderDefinition(
        key="barikoi",
        output_namespace="barikoi_mvt_coverage",
        run_label_prefix="barikoi_coverage",
        default_display_zoom=14,
        coordinate_scheme="web_mercator",
        area_presets={
            "dhaka_thirdeye360_pilot_bbox": COMMON_AREA_PRESETS["dhaka_thirdeye360_pilot_bbox"],
        },
        sources=(
            SourceDefinition(
                id="barikoi_thirdeye360_mvt",
                kind="vector_mvt",
                template="https://tiles.bmapsbd.com/ThirdEye360/{z}/{x}/{y}",
                headers={
                    "User-Agent": "global-svi-coverage-observatory/0.3",
                    "Referer": "https://streetview.bmapsbd.com/",
                    "Accept": "application/vnd.mapbox-vector-tile, application/octet-stream;q=0.9, */*;q=0.1",
                },
                display_zoom_min=7,
                display_zoom_max=18,
                layer_names=("ThirdEye360",),
                storage_subdir="vector_mvt",
                vector_decoder="custom_mvt",
                notes=(
                    "Barikoi ThirdEye360 coverage points from the public viewer's MVT "
                    "source; one Point represents one captured panorama. Empty tiles "
                    "return HTTP 204. Low-zoom tiles can exceed 100 MiB, so acquisition "
                    "should use z14 over known service bounds rather than a Bangladesh "
                    "low-zoom sweep. No token is required by the currently observed endpoint."
                ),
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
                    "Yandex street-view coverage raster tiles (`l=stv`, `format=png`). Tile "
                    "selection and bounds use Yandex's WGS84 elliptic Mercator grid. The "
                    "rendered overlay draws covered streets with a mix of a thin road-following "
                    "line and denser dot markers baked into the same pixels -- there is no "
                    "clean way to split them from this raster alone. "
                    "Investigated on 2026-08-02 for a genuine point-vs-line data split: "
                    "`l=stj` (`staHotspotTiles`) is a real but unrelated, much sparser "
                    "endpoint (~20 features across all of central Moscow) of UI click-target "
                    "hotspots, not per-capture points -- dropped, wrong data. The frontend also "
                    "references a proper vector tile source, `vector3StvTiles` "
                    "(`https://vec0{N}.core-stv-renderer.maps.yandex.net/3.x/tiles?"
                    "l=sta,stv&x={x}&y={y}&z={z}&v={version}&format=protobuf`, found in the "
                    "`base` JS chunk, confirmed live/200 with real content), which returns ~600 "
                    "point-feature IDs per tile (field 5, matching the raster's dot density far "
                    "better than `stj`) plus a separate geometry blob (field 2) -- but that "
                    "blob is raw packed binary in an undocumented Yandex-proprietary encoding, "
                    "not a nested protobuf message or standard MVT, so real point/line "
                    "coordinates could not be safely extracted without guessing the codec "
                    "against no ground truth. Left unimplemented rather than risk silently "
                    "wrong point locations; revisit if the encoding is ever documented."
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
