from __future__ import annotations

import math
from functools import lru_cache

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
    if coordinate_scheme == "baidu":
        return baidu_tile_to_lonlat_bounds(x, y, zoom)
    if coordinate_scheme == "kakao":
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
    [
        -0.0015702102444,
        111320.7020616939,
        1704480524535203,
        -10338987376042340,
        26112667856603880,
        -35149669176653700,
        26595700718403920,
        -10725012454188240,
        1800819912950474,
        82.5,
    ],
    [
        0.0008277824516172526,
        111320.7020463578,
        647795574.6671607,
        -4082003173.641316,
        10774905663.51142,
        -15171875531.51559,
        12053065338.62167,
        -5124939663.577472,
        913311935.9512032,
        67.5,
    ],
    [
        0.00337398766765,
        111320.7020202162,
        4481351.045890365,
        -23393751.19931662,
        79682215.47186455,
        -115964993.2797253,
        97236711.15602145,
        -43661946.33752821,
        8477230.501135234,
        52.5,
    ],
    [
        0.00220636496208,
        111320.7020209128,
        51751.86112841131,
        3796837.749470245,
        992013.7397791013,
        -1221952.21711287,
        1340652.697009075,
        -620943.6990984312,
        144416.9293806241,
        37.5,
    ],
    [
        -0.0003441963504368392,
        111320.7020576856,
        278.2353980772752,
        2485758.690035394,
        6070.750963243378,
        54821.18345352118,
        9540.606633304236,
        -2710.55326746645,
        1405.483844121726,
        22.5,
    ],
    [
        -0.0003218135878613132,
        111320.7020701615,
        0.00369383431289,
        823725.6402795718,
        0.46104986909093,
        2351.343141331292,
        1.58060784298199,
        8.77738589078284,
        0.37238884252424,
        7.45,
    ],
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
    y_temp = (
        coeffs[2]
        + coeffs[3] * cc
        + coeffs[4] * cc**2
        + coeffs[5] * cc**3
        + coeffs[6] * cc**4
        + coeffs[7] * cc**5
        + coeffs[8] * cc**6
    )
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


# Inverse of BAIDU_LLBAND / BAIDU_LL2MC: bands keyed by projected-Y magnitude
# instead of latitude, and each row is [inverse polynomial coeffs..., unused].
BAIDU_MCBAND = [12890594.86, 8362377.87, 5591021.0, 3481989.83, 1678043.12, 0.0]
BAIDU_MC2LL = [
    [
        1.410526172116255e-8,
        0.00000898305509648872,
        -1.9939833816331,
        200.9824383106796,
        -187.2403703815547,
        91.6087516669843,
        -23.38765649603339,
        2.57121317296198,
        -0.03801003308653,
        17337981.2,
    ],
    [
        -7.435856389565537e-9,
        0.000008983055097726239,
        -0.78625201886289,
        96.32687599759846,
        -1.85204757529826,
        -59.36935905485877,
        47.40033549296737,
        -16.50741931063887,
        2.28786674699375,
        10260144.86,
    ],
    [
        -3.030883460898826e-8,
        0.00000898305509983578,
        0.30071316287616,
        59.74293618442277,
        7.357984074871,
        -25.38371002664745,
        13.45380521110908,
        -3.29883767235584,
        0.32710905363475,
        6856817.37,
    ],
    [
        -1.981981304930552e-8,
        0.000008983055099779535,
        0.03278182852591,
        40.31678527705744,
        0.65659298677277,
        -4.44255534477492,
        0.85341911805263,
        0.12923347998204,
        -0.04625736007561,
        4482777.06,
    ],
    [
        3.09191371068437e-9,
        0.000008983055096812155,
        0.00006995724062,
        23.10934304144901,
        -0.00023663490511,
        -0.6321817810242,
        -0.00663494467273,
        0.03430082397953,
        -0.00466043876332,
        2555164.4,
    ],
    [
        2.890871144776878e-9,
        0.000008983055095805407,
        -3.068298e-8,
        7.47137025468032,
        -0.00000353937994,
        -0.02145144861037,
        -0.00001234426596,
        0.00010322952773,
        -0.00000323890364,
        826088.5,
    ],
]


def _baidu_mc_convertor(x: float, y: float, coeffs: list[float]) -> tuple[float, float]:
    lon = coeffs[0] + coeffs[1] * abs(x)
    cc = abs(y) / coeffs[9]
    lat = (
        coeffs[2]
        + coeffs[3] * cc
        + coeffs[4] * cc**2
        + coeffs[5] * cc**3
        + coeffs[6] * cc**4
        + coeffs[7] * cc**5
        + coeffs[8] * cc**6
    )
    lon *= -1 if x < 0 else 1
    lat *= -1 if y < 0 else 1
    return lon, lat


def bd09mc_to_bd09ll(mc_x: float, mc_y: float) -> tuple[float, float]:
    abs_y = abs(mc_y)
    coeffs = None
    for index, band in enumerate(BAIDU_MCBAND):
        if abs_y >= band:
            coeffs = BAIDU_MC2LL[index]
            break
    if coeffs is None:
        raise ValueError(f"Could not choose BAIDU_MC2LL coeffs for mc x/y: {(mc_x, mc_y)}")
    return _baidu_mc_convertor(mc_x, mc_y, coeffs)


def bd09_to_gcj02(bd_lon: float, bd_lat: float) -> tuple[float, float]:
    x = bd_lon - 0.0065
    y = bd_lat - 0.006
    z = math.sqrt(x * x + y * y) - 0.00002 * math.sin(y * math.pi * 3000.0 / 180.0)
    theta = math.atan2(y, x) - 0.000003 * math.cos(x * math.pi * 3000.0 / 180.0)
    return z * math.cos(theta), z * math.sin(theta)


def gcj02_to_wgs84(gcj_lon: float, gcj_lat: float) -> tuple[float, float]:
    if baidu_out_of_china(gcj_lon, gcj_lat):
        return gcj_lon, gcj_lat

    a = 6378245.0
    ee = 0.00669342162296594323
    dlat = baidu_transform_lat(gcj_lon - 105.0, gcj_lat - 35.0)
    dlon = baidu_transform_lon(gcj_lon - 105.0, gcj_lat - 35.0)
    radlat = gcj_lat / 180.0 * math.pi
    magic = math.sin(radlat)
    magic = 1 - ee * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((a * (1 - ee)) / (magic * sqrtmagic) * math.pi)
    dlon = (dlon * 180.0) / (a / sqrtmagic * math.cos(radlat) * math.pi)
    return gcj_lon - dlon, gcj_lat - dlat


def baidu_tile_to_lonlat_bounds(x: int, y: int, zoom: int) -> tuple[float, float, float, float]:
    tile_span = 256 * (2 ** (18 - zoom))
    corners_mc = [
        (x * tile_span, y * tile_span),
        ((x + 1) * tile_span, (y + 1) * tile_span),
    ]
    lons = []
    lats = []
    for mc_x, mc_y in corners_mc:
        bd_lon, bd_lat = bd09mc_to_bd09ll(mc_x, mc_y)
        gcj_lon, gcj_lat = bd09_to_gcj02(bd_lon, bd_lat)
        lon, lat = gcj02_to_wgs84(gcj_lon, gcj_lat)
        lons.append(lon)
        lats.append(lat)
    return min(lons), min(lats), max(lons), max(lats)


KAKAO_TILE_SIZE = 256
KAKAO_TM_TO_POINT_SCALE = 8.0
KAKAO_POINT_X_OFFSET = 240000.0
KAKAO_POINT_Y_OFFSET = 480000.0


@lru_cache(maxsize=1)
def _kakao_coordinate_transformers():
    try:
        from pyproj import Transformer
    except ImportError as exc:
        raise RuntimeError("pyproj is required for the Kakao EPSG:5181 tile grid.") from exc
    return (
        Transformer.from_crs(4326, 5181, always_xy=True),
        Transformer.from_crs(5181, 4326, always_xy=True),
    )


def kakao_lonlat_to_tile(lon: float, lat: float, level: int) -> tuple[int, int]:
    lonlat_to_tm, _ = _kakao_coordinate_transformers()
    tm_x, tm_y = lonlat_to_tm.transform(lon, lat)
    point_x = KAKAO_TM_TO_POINT_SCALE * tm_x + KAKAO_POINT_X_OFFSET
    point_y = KAKAO_TM_TO_POINT_SCALE * tm_y + KAKAO_POINT_Y_OFFSET
    tile_span = KAKAO_TILE_SIZE * (2**level)
    return int(math.floor(point_x / tile_span)), int(math.floor(point_y / tile_span))


def kakao_bbox_to_tile_range(bbox: BoundingBox, level: int) -> TileRange:
    corner_tiles = [
        kakao_lonlat_to_tile(bbox.min_lon, bbox.min_lat, level),
        kakao_lonlat_to_tile(bbox.min_lon, bbox.max_lat, level),
        kakao_lonlat_to_tile(bbox.max_lon, bbox.min_lat, level),
        kakao_lonlat_to_tile(bbox.max_lon, bbox.max_lat, level),
    ]
    xs = [tile[0] for tile in corner_tiles]
    ys = [tile[1] for tile in corner_tiles]
    return TileRange(x_min=min(xs), x_max=max(xs), y_min=min(ys), y_max=max(ys))


def kakao_tile_to_lonlat_bounds(x: int, y: int, level: int) -> tuple[float, float, float, float]:
    _, tm_to_lonlat = _kakao_coordinate_transformers()
    tile_span = KAKAO_TILE_SIZE * (2**level)
    point_corners = [
        (x * tile_span, y * tile_span),
        (x * tile_span, (y + 1) * tile_span),
        ((x + 1) * tile_span, y * tile_span),
        ((x + 1) * tile_span, (y + 1) * tile_span),
    ]
    lonlat_corners = [
        tm_to_lonlat.transform(
            (point_x - KAKAO_POINT_X_OFFSET) / KAKAO_TM_TO_POINT_SCALE,
            (point_y - KAKAO_POINT_Y_OFFSET) / KAKAO_TM_TO_POINT_SCALE,
        )
        for point_x, point_y in point_corners
    ]
    lons = [lon for lon, _ in lonlat_corners]
    lats = [lat for _, lat in lonlat_corners]
    return min(lons), min(lats), max(lons), max(lats)


def tile_range_for_bbox(bbox: BoundingBox, zoom: int, coordinate_scheme: str) -> TileRange:
    if coordinate_scheme == "baidu":
        return baidu_bbox_to_tile_range(bbox, zoom)
    if coordinate_scheme == "yandex_wgs84_mercator":
        return yandex_bbox_to_tile_range(bbox, zoom)
    if coordinate_scheme == "kakao":
        return kakao_bbox_to_tile_range(bbox, zoom)
    return bbox_to_tile_range(bbox, zoom)
