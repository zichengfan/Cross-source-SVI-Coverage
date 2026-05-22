from __future__ import annotations

import math
from dataclasses import dataclass

from pyproj import Transformer

from coverage_acquisition.models import BoundingBox, TileRange


def lonlat_to_tile(lon: float, lat: float, zoom: int) -> tuple[int, int]:
    lat_rad = math.radians(lat)
    n = 2**zoom
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return x, y


def bbox_to_tile_range(bbox: BoundingBox, zoom: int) -> TileRange:
    x1, y2 = lonlat_to_tile(bbox.min_lon, bbox.min_lat, zoom)
    x2, y1 = lonlat_to_tile(bbox.max_lon, bbox.max_lat, zoom)
    return TileRange(
        x_min=min(x1, x2),
        x_max=max(x1, x2),
        y_min=min(y1, y2),
        y_max=max(y1, y2),
    )


def tile_to_lonlat_bounds(x: int, y: int, zoom: int) -> tuple[float, float, float, float]:
    n = 2**zoom
    lon_min = x / n * 360.0 - 180.0
    lon_max = (x + 1) / n * 360.0 - 180.0
    lat_max = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    lat_min = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n))))
    return lon_min, lat_min, lon_max, lat_max


YANDEX_WGS84_MERCATOR_ECCENTRICITY = 0.0818191908426
YANDEX_WGS84_MERCATOR_LAT_LIMIT = 85.08405905


def yandex_clamp_lat(lat: float) -> float:
    return max(min(lat, YANDEX_WGS84_MERCATOR_LAT_LIMIT), -YANDEX_WGS84_MERCATOR_LAT_LIMIT)


def yandex_elliptic_mercator_lat_to_y_fraction(lat: float) -> float:
    lat_rad = math.radians(yandex_clamp_lat(lat))
    eccentricity = YANDEX_WGS84_MERCATOR_ECCENTRICITY
    sin_lat = math.sin(lat_rad)
    mercator_y = math.log(
        math.tan(math.pi / 4.0 + lat_rad / 2.0)
        * ((1.0 - eccentricity * sin_lat) / (1.0 + eccentricity * sin_lat)) ** (eccentricity / 2.0)
    )
    return (1.0 - mercator_y / math.pi) / 2.0


def yandex_elliptic_mercator_y_fraction_to_lat(y_fraction: float, iterations: int = 12) -> float:
    mercator_y = math.pi * (1.0 - 2.0 * y_fraction)
    eccentricity = YANDEX_WGS84_MERCATOR_ECCENTRICITY
    lat_rad = 2.0 * math.atan(math.exp(mercator_y)) - math.pi / 2.0

    for _ in range(iterations):
        sin_lat = math.sin(lat_rad)
        correction = ((1.0 + eccentricity * sin_lat) / (1.0 - eccentricity * sin_lat)) ** (eccentricity / 2.0)
        lat_rad = 2.0 * math.atan(math.exp(mercator_y) * correction) - math.pi / 2.0

    return math.degrees(lat_rad)


def yandex_lonlat_to_tile(lon: float, lat: float, zoom: int) -> tuple[int, int]:
    n = 2**zoom
    x = int(math.floor((lon + 180.0) / 360.0 * n))
    y = int(math.floor(yandex_elliptic_mercator_lat_to_y_fraction(lat) * n))
    return x, y


def yandex_bbox_to_tile_range(bbox: BoundingBox, zoom: int) -> TileRange:
    x1, y2 = yandex_lonlat_to_tile(bbox.min_lon, bbox.min_lat, zoom)
    x2, y1 = yandex_lonlat_to_tile(bbox.max_lon, bbox.max_lat, zoom)
    return TileRange(
        x_min=min(x1, x2),
        x_max=max(x1, x2),
        y_min=min(y1, y2),
        y_max=max(y1, y2),
    )


def yandex_tile_to_lonlat_bounds(x: int, y: int, zoom: int) -> tuple[float, float, float, float]:
    n = 2**zoom
    lon_min = x / n * 360.0 - 180.0
    lon_max = (x + 1) / n * 360.0 - 180.0
    lat_max = yandex_elliptic_mercator_y_fraction_to_lat(y / n)
    lat_min = yandex_elliptic_mercator_y_fraction_to_lat((y + 1) / n)
    return lon_min, lat_min, lon_max, lat_max


def tile_to_lonlat_bounds_for_scheme(
    x: int,
    y: int,
    zoom: int,
    coordinate_scheme: str = "web_mercator",
) -> tuple[float, float, float, float]:
    if coordinate_scheme == "yandex_wgs84_mercator":
        return yandex_tile_to_lonlat_bounds(x, y, zoom)
    if coordinate_scheme == "kakao_epsg5181":
        return kakao_tile_to_lonlat_bounds(x, y, zoom)
    return tile_to_lonlat_bounds(x, y, zoom)


def split_bbox_into_grid(bbox: BoundingBox, rows: int, cols: int) -> list[dict]:
    lon_step = (bbox.max_lon - bbox.min_lon) / cols
    lat_step = (bbox.max_lat - bbox.min_lat) / rows
    subboxes = []
    index = 0
    for row in range(rows):
        for col in range(cols):
            subboxes.append(
                {
                    "index": index,
                    "row": row,
                    "col": col,
                    "bbox": BoundingBox(
                        min_lon=bbox.min_lon + col * lon_step,
                        max_lon=bbox.min_lon + (col + 1) * lon_step,
                        min_lat=bbox.min_lat + row * lat_step,
                        max_lat=bbox.min_lat + (row + 1) * lat_step,
                    ),
                }
            )
            index += 1
    return subboxes


def select_subboxes(subboxes: list[dict], selector: tuple[int, ...] | None) -> list[dict]:
    if selector is None:
        return subboxes
    wanted = set(selector)
    return [subbox for subbox in subboxes if subbox["index"] in wanted]


def iter_tile_coords(tile_range: TileRange):
    for x in range(tile_range.x_min, tile_range.x_max + 1):
        for y in range(tile_range.y_min, tile_range.y_max + 1):
            yield x, y


BAIDU_LLBAND = [75, 60, 45, 30, 15, 0]
BAIDU_LL2MC = [
    [-0.0015702102444, 111320.7020616939, 1704480524535203, -10338987376042340, 26112667856603880, -35149669176653700, 26595700718403920, -10725012454188240, 1800819912950474, 82.5],
    [0.0008277824516172526, 111320.7020463578, 647795574.6671607, -4082003173.641316, 10774905663.51142, -15171875531.51559, 12053065338.62167, -5124939663.577472, 913311935.9512032, 67.5],
    [0.00337398766765, 111320.7020202162, 4481351.045890365, -23393751.19931662, 79682215.47186455, -115964993.2797253, 97236711.15602145, -43661946.33752821, 8477230.501135234, 52.5],
    [0.00220636496208, 111320.7020209128, 51751.86112841131, 3796837.749470245, 992013.7397791013, -1221952.21711287, 1340652.697009075, -620943.6990984312, 144416.9293806241, 37.5],
    [-0.0003441963504368392, 111320.7020576856, 278.2353980772752, 2485758.690035394, 6070.750963243378, 54821.18345352118, 9540.606633304236, -2710.55326746645, 1405.483844121726, 22.5],
    [-0.0003218135878613132, 111320.7020701615, 0.00369383431289, 823725.6402795718, 0.46104986909093, 2351.343141331292, 1.58060784298199, 8.77738589078284, 0.37238884252424, 7.45],
]


def baidu_out_of_china(lon: float, lat: float) -> bool:
    return not (72.004 <= lon <= 137.8347 and 0.8293 <= lat <= 55.8271)


def baidu_transform_lat(lon: float, lat: float) -> float:
    ret = -100.0 + 2.0 * lon + 3.0 * lat + 0.2 * lat * lat + 0.1 * lon * lat + 0.2 * math.sqrt(abs(lon))
    ret += (20.0 * math.sin(6.0 * lon * math.pi) + 20.0 * math.sin(2.0 * lon * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lat * math.pi) + 40.0 * math.sin(lat / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (160.0 * math.sin(lat / 12.0 * math.pi) + 320 * math.sin(lat * math.pi / 30.0)) * 2.0 / 3.0
    return ret


def baidu_transform_lon(lon: float, lat: float) -> float:
    ret = 300.0 + lon + 2.0 * lat + 0.1 * lon * lon + 0.1 * lon * lat + 0.1 * math.sqrt(abs(lon))
    ret += (20.0 * math.sin(6.0 * lon * math.pi) + 20.0 * math.sin(2.0 * lon * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(lon * math.pi) + 40.0 * math.sin(lon / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (150.0 * math.sin(lon / 12.0 * math.pi) + 300.0 * math.sin(lon / 30.0 * math.pi)) * 2.0 / 3.0
    return ret


def wgs84_to_gcj02(lon: float, lat: float) -> tuple[float, float]:
    if baidu_out_of_china(lon, lat):
        return lon, lat

    a = 6378245.0
    ee = 0.00669342162296594323
    dlat = baidu_transform_lat(lon - 105.0, lat - 35.0)
    dlon = baidu_transform_lon(lon - 105.0, lat - 35.0)
    radlat = lat / 180.0 * math.pi
    magic = math.sin(radlat)
    magic = 1 - ee * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((a * (1 - ee)) / (magic * sqrtmagic) * math.pi)
    dlon = (dlon * 180.0) / (a / sqrtmagic * math.cos(radlat) * math.pi)
    return lon + dlon, lat + dlat


TENCENT_PX_SCALE = 268435456
TENCENT_A = 114.59155902616465
TENCENT_COMPRESS_LEVELS = (7, 11, 11, 11, 11, 11, 11, 11, 11)


@dataclass(frozen=True)
class TencentBlTile:
    bl: int
    tile_x: int
    tile_y: int
    origin_px_x: int
    origin_px_y: int


def tencent_pixel_to_gcj02(px_x: float, px_y: float) -> tuple[float, float]:
    lon = 360.0 * px_x / TENCENT_PX_SCALE - 180.0
    lat = math.atan(math.exp(math.radians(180.0 - 360.0 * px_y / TENCENT_PX_SCALE))) * TENCENT_A - 90.0
    return lon, lat


def tencent_gcj02_to_pixel(lon: float, lat: float) -> tuple[float, float]:
    px_x = (lon + 180.0) * TENCENT_PX_SCALE / 360.0
    px_y = (TENCENT_PX_SCALE / 360.0) * (
        180.0 - math.degrees(math.log(math.tan((lat + 90.0) / TENCENT_A)))
    )
    return px_x, px_y


def gcj02_to_wgs84(lon: float, lat: float, iterations: int = 8) -> tuple[float, float]:
    if baidu_out_of_china(lon, lat):
        return lon, lat

    wgs_lon = lon
    wgs_lat = lat
    for _ in range(iterations):
        gcj_lon, gcj_lat = wgs84_to_gcj02(wgs_lon, wgs_lat)
        wgs_lon -= gcj_lon - lon
        wgs_lat -= gcj_lat - lat
    return wgs_lon, wgs_lat


def tencent_tile_size(level: int) -> int:
    return TENCENT_PX_SCALE // (2**level)


def tencent_point_multiplier(level: int) -> int:
    index = level - 10
    if index < 0 or index >= len(TENCENT_COMPRESS_LEVELS):
        raise ValueError(f"Unsupported Tencent data level: {level}")
    compress_level = TENCENT_COMPRESS_LEVELS[index]
    return math.floor(tencent_tile_size(level) / (1 << compress_level))


def tencent_bl_tiles_for_gcj02_bbox(bbox: BoundingBox, level: int) -> list[TencentBlTile]:
    tile_size = tencent_tile_size(level)
    west_px, north_px = tencent_gcj02_to_pixel(bbox.min_lon, bbox.max_lat)
    east_px, south_px = tencent_gcj02_to_pixel(bbox.max_lon, bbox.min_lat)

    west = math.floor(west_px / tile_size)
    north = math.floor(north_px / tile_size)
    east = math.floor((east_px - 1) / tile_size)
    south = math.floor((south_px - 1) / tile_size)

    tiles = []
    bl = 0
    for tile_x in range(west, east + 1):
        for tile_y in range(north, south + 1):
            tiles.append(
                TencentBlTile(
                    bl=bl,
                    tile_x=tile_x,
                    tile_y=tile_y,
                    origin_px_x=tile_x * tile_size,
                    origin_px_y=tile_y * tile_size,
                )
            )
            bl += 1
    return tiles


def gcj02_to_bd09(lon: float, lat: float) -> tuple[float, float]:
    z = math.sqrt(lon * lon + lat * lat) + 0.00002 * math.sin(lat * math.pi * 3000.0 / 180.0)
    theta = math.atan2(lat, lon) + 0.000003 * math.cos(lon * math.pi * 3000.0 / 180.0)
    return z * math.cos(theta) + 0.0065, z * math.sin(theta) + 0.006


def baidu_get_range(value: float, minimum: float, maximum: float) -> float:
    return min(max(value, minimum), maximum)


def baidu_get_loop(value: float, minimum: float, maximum: float) -> float:
    while value > maximum:
        value -= maximum - minimum
    while value < minimum:
        value += maximum - minimum
    return value


def baidu_convertor(x: float, y: float, coeffs: list[float]) -> tuple[float, float]:
    x_temp = coeffs[0] + coeffs[1] * abs(x)
    cc = abs(y) / coeffs[9]
    y_temp = coeffs[2] + coeffs[3] * cc + coeffs[4] * cc**2 + coeffs[5] * cc**3 + coeffs[6] * cc**4 + coeffs[7] * cc**5 + coeffs[8] * cc**6
    x_temp *= -1 if x < 0 else 1
    y_temp *= -1 if y < 0 else 1
    return x_temp, y_temp


def bd09ll_to_bd09mc(lon: float, lat: float) -> tuple[float, float]:
    lon = baidu_get_loop(lon, -180, 180)
    lat = baidu_get_range(lat, -74, 74)

    coeffs = None
    for index, band in enumerate(BAIDU_LLBAND):
        if lat >= band:
            coeffs = BAIDU_LL2MC[index]
            break

    if coeffs is None:
        for index in range(len(BAIDU_LLBAND) - 1, -1, -1):
            if lat <= -BAIDU_LLBAND[index]:
                coeffs = BAIDU_LL2MC[index]
                break

    if coeffs is None:
        raise ValueError(f"Could not choose BAIDU_LL2MC coeffs for lon/lat: {(lon, lat)}")

    return baidu_convertor(lon, lat, coeffs)


def wgs84_to_baidu_tile(lon: float, lat: float, zoom: int) -> tuple[int, int]:
    gcj_lon, gcj_lat = wgs84_to_gcj02(lon, lat)
    bd_lon, bd_lat = gcj02_to_bd09(gcj_lon, gcj_lat)
    mc_x, mc_y = bd09ll_to_bd09mc(bd_lon, bd_lat)
    tile_span = 256 * (2 ** (18 - zoom))
    tile_x = int(math.floor(mc_x / tile_span))
    tile_y = int(math.floor(mc_y / tile_span))
    return tile_x, tile_y


def baidu_bbox_to_tile_range(bbox: BoundingBox, zoom: int) -> TileRange:
    corner_tiles = [
        wgs84_to_baidu_tile(bbox.min_lon, bbox.min_lat, zoom),
        wgs84_to_baidu_tile(bbox.min_lon, bbox.max_lat, zoom),
        wgs84_to_baidu_tile(bbox.max_lon, bbox.min_lat, zoom),
        wgs84_to_baidu_tile(bbox.max_lon, bbox.max_lat, zoom),
    ]
    xs = [tile[0] for tile in corner_tiles]
    ys = [tile[1] for tile in corner_tiles]
    return TileRange(x_min=min(xs), x_max=max(xs), y_min=min(ys), y_max=max(ys))


KAKAO_EPSG5181_ORIGIN_X = -30000.0
KAKAO_EPSG5181_ORIGIN_Y = -60000.0
KAKAO_EPSG5181_TILE_SIZE = 256
KAKAO_EPSG5181_RESOLUTIONS = (2048.0, 1024.0, 512.0, 256.0, 128.0, 64.0, 32.0, 16.0, 8.0, 4.0, 2.0, 1.0, 0.5, 0.25)
WGS84_TO_KAKAO_EPSG5181 = Transformer.from_crs("EPSG:4326", "EPSG:5181", always_xy=True)
KAKAO_EPSG5181_TO_WGS84 = Transformer.from_crs("EPSG:5181", "EPSG:4326", always_xy=True)


def kakao_epsg5181_resolution(zoom: int) -> float:
    try:
        return KAKAO_EPSG5181_RESOLUTIONS[zoom]
    except IndexError as exc:
        raise ValueError(f"Unsupported kakao_epsg5181 zoom: {zoom}") from exc


def wgs84_to_kakao_epsg5181_tile(lon: float, lat: float, zoom: int) -> tuple[int, int]:
    x_m, y_m = WGS84_TO_KAKAO_EPSG5181.transform(lon, lat)
    tile_span = KAKAO_EPSG5181_TILE_SIZE * kakao_epsg5181_resolution(zoom)
    tile_x = int(math.floor((x_m - KAKAO_EPSG5181_ORIGIN_X) / tile_span))
    tile_y = int(math.floor((y_m - KAKAO_EPSG5181_ORIGIN_Y) / tile_span))
    return tile_x, tile_y


def kakao_epsg5181_bbox_to_tile_range(bbox: BoundingBox, zoom: int) -> TileRange:
    corner_tiles = [
        wgs84_to_kakao_epsg5181_tile(bbox.min_lon, bbox.min_lat, zoom),
        wgs84_to_kakao_epsg5181_tile(bbox.min_lon, bbox.max_lat, zoom),
        wgs84_to_kakao_epsg5181_tile(bbox.max_lon, bbox.min_lat, zoom),
        wgs84_to_kakao_epsg5181_tile(bbox.max_lon, bbox.max_lat, zoom),
    ]
    xs = [tile[0] for tile in corner_tiles]
    ys = [tile[1] for tile in corner_tiles]
    return TileRange(x_min=min(xs), x_max=max(xs), y_min=min(ys), y_max=max(ys))


def kakao_tile_to_lonlat_bounds(x: int, y: int, zoom: int) -> tuple[float, float, float, float]:
    tile_span = KAKAO_EPSG5181_TILE_SIZE * kakao_epsg5181_resolution(zoom)
    x_min_m = KAKAO_EPSG5181_ORIGIN_X + x * tile_span
    x_max_m = KAKAO_EPSG5181_ORIGIN_X + (x + 1) * tile_span
    y_min_m = KAKAO_EPSG5181_ORIGIN_Y + y * tile_span
    y_max_m = KAKAO_EPSG5181_ORIGIN_Y + (y + 1) * tile_span
    lonlat_corners = [
        KAKAO_EPSG5181_TO_WGS84.transform(x_min_m, y_min_m),
        KAKAO_EPSG5181_TO_WGS84.transform(x_min_m, y_max_m),
        KAKAO_EPSG5181_TO_WGS84.transform(x_max_m, y_min_m),
        KAKAO_EPSG5181_TO_WGS84.transform(x_max_m, y_max_m),
    ]
    lons = [corner[0] for corner in lonlat_corners]
    lats = [corner[1] for corner in lonlat_corners]
    return min(lons), min(lats), max(lons), max(lats)


def tile_range_for_bbox(bbox: BoundingBox, zoom: int, coordinate_scheme: str) -> TileRange:
    if coordinate_scheme == "baidu":
        return baidu_bbox_to_tile_range(bbox, zoom)
    if coordinate_scheme == "yandex_wgs84_mercator":
        return yandex_bbox_to_tile_range(bbox, zoom)
    if coordinate_scheme == "kakao_epsg5181":
        return kakao_epsg5181_bbox_to_tile_range(bbox, zoom)
    return bbox_to_tile_range(bbox, zoom)
