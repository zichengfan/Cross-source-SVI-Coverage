"""Mapy.com streetlevel coverage provider.

Mapy Panorama coverage is discovered through the undocumented Seznam FRPC API
wrapped by ``streetlevel.mapy``. This provider stores only coverage presence,
returned panorama locations, and capture dates; it never downloads or stores
panorama imagery. The underlying client must send ``Referer: https://en.mapy.cz/``
for 2020+ Cyclomedia panoramas, which ``streetlevel.mapy`` handles internally.

Coverage discovery uses WGS84 point probes over the standard Web Mercator z14
raster grid. Defaults use a 200 m probe spacing and 125 m search radius for the
pilot/fine pass; full-extent runs should stay inside the Czech Republic bbox.
"""

from __future__ import annotations

import streetlevel.mapy as streetlevel_mapy

from coverage_acquisition.models import BoundingBox, ProviderDefinition, SourceDefinition
from coverage_acquisition.providers._registry import register_provider
from coverage_acquisition.source_kinds.streetlevel import ProbeBlockedError, register_streetlevel_probe

PROVIDER = ProviderDefinition(
    key="mapy",
    output_namespace="mapy_panorama_points",
    run_label_prefix="mapy_panorama",
    default_display_zoom=14,
    coordinate_scheme="web_mercator",
    area_presets={
        "prague_old_town_pilot_bbox": BoundingBox(
            min_lon=14.40,
            min_lat=50.075,
            max_lon=14.44,
            max_lat=50.095,
        ),
        "czech_republic_bbox": BoundingBox(
            min_lon=12.09,
            min_lat=48.55,
            max_lon=18.86,
            max_lat=51.06,
        ),
    },
    sources=(
        SourceDefinition(
            id="mapy_panorama_streetlevel",
            kind="streetlevel",
            template="streetlevel://mapy/find_panorama",
            storage_subdir="panorama_points",
            options={
                "streetlevel_module": "mapy",
                "probe_radius_m": "125",
                "probe_spacing_m": "200",
                "requests_per_second": "1",
                "links": "false",
                "historical": "false",
            },
            notes=(
                "Discovers Mapy Panorama coverage with streetlevel.mapy.find_panorama, which wraps "
                "Seznam's undocumented FRPC getbest API. Coverage is Czech-only in practice; use the "
                "returned panorama lat/lon rather than the probe point."
            ),
        ),
    ),
)


def probe_mapy(lat: float, lon: float, radius_m: float) -> list[dict]:
    """Probe Mapy Panorama coverage near a WGS84 point."""
    try:
        pano = streetlevel_mapy.find_panorama(lat, lon, radius_m, links=False, historical=False)
    except Exception as exc:  # noqa: BLE001 - normalize streetlevel/pyfrpc failures for the probe runner.
        raise ProbeBlockedError("Mapy streetlevel probe failed; FRPC transport or decoding was unsuccessful.") from exc

    if pano is None:
        return []

    try:
        date = pano.date.date().isoformat()
        return [
            {
                "panoid": str(pano.id),
                "lat": float(pano.lat),
                "lon": float(pano.lon),
                "date": date,
                "raw": {
                    "id": pano.id,
                    "provider": pano.provider,
                    "date": pano.date.isoformat(),
                    "elevation": pano.elevation,
                },
            }
        ]
    except Exception as exc:  # noqa: BLE001 - malformed decoded panorama is a blocked/undecodable probe.
        raise ProbeBlockedError("Mapy streetlevel probe failed; FRPC transport or decoding was unsuccessful.") from exc


register_provider(PROVIDER)
register_streetlevel_probe("mapy", probe_mapy)
