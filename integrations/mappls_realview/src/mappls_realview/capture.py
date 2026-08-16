from __future__ import annotations

import base64
import math
import re
import urllib.parse
from dataclasses import asdict, dataclass

# Mapping observed in the capture used to build the original toolkit.
DIGITS = {
    "rz": "0",
    "no": "1",
    "wt": "2",
    "xs": "3",
    "rf": "4",
    "vf": "5",
    "ht": "6",
    "vs": "7",
    "nn": "8",
    "te": "9",
}

# The Mappls SDK served on 2026-08-03 used a different substitution for four
# digits.  The change is observable by comparing signed request payloads with
# the MapLibre source cache's canonical tile IDs.  Keep profiles explicit:
# signed HAR files do not contain the original /{z}/{x}/{y}.pbf URL.
DIGIT_PROFILES = {
    "current_2026_08": {
        "rz": "0",
        "no": "1",
        "wt": "2",
        "ht": "3",
        "rf": "4",
        "vf": "5",
        "xs": "6",
        "vs": "7",
        "te": "8",
        "nn": "9",
    },
    "legacy": DIGITS,
}
DEFAULT_DIGIT_PROFILE = "auto"
REALVIEW_BOUNDS = (67.7856, 5.6597, 101.5796, 37.1957)
REALVIEW_MARKER = "lrlelalllvlilelwl"  # observed obfuscated "realview"
PBF_MARKER = "tdlplblflqlvl="  # observed obfuscated ".pbf?v=" boundary


@dataclass
class RealViewRequest:
    z: int
    x: int
    y: int
    url: str
    source: str
    ordinal: int = 0
    opaque_key: str | None = None
    payload: str | None = None
    digit_profile: str | None = None

    def to_dict(self, include_url: bool = True) -> dict:
        d = asdict(self)
        if not include_url:
            d.pop("url", None)
        return d


def b64decode_loose(s: str) -> str:
    s = urllib.parse.unquote(s)
    s += "=" * (-len(s) % 4)
    return base64.b64decode(s).decode("utf-8", errors="ignore")


def decode_xyz(payload: str, digits: dict[str, str] | None = None) -> tuple[int, int, int] | None:
    digits = DIGITS if digits is None else digits
    if PBF_MARKER not in payload:
        return None
    prefix = payload.split(PBF_MARKER, 1)[0]
    tokens = prefix.split("l")
    chars: list[str] = []
    for token in tokens:
        if token == "s":
            chars.append("/")
        elif token in digits:
            chars.append(digits[token])
        elif token:
            return None
    decoded = "".join(chars)
    m = re.fullmatch(r"(\d+)/(\d+)/(\d+)", decoded)
    return tuple(map(int, m.groups())) if m else None


def _plausible_realview_xyz(xyz: tuple[int, int, int]) -> bool:
    z, x, y = xyz
    if not (0 <= z <= 24 and 0 <= x < 2**z and 0 <= y < 2**z):
        return False
    n = 2**z
    west = x / n * 360.0 - 180.0
    east = (x + 1) / n * 360.0 - 180.0
    north = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    south = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n))))
    rw, rs, re, rn = REALVIEW_BOUNDS
    return east > rw and west < re and north > rs and south < rn


def _decode_profiled_xyz(payload: str, digit_profile: str) -> tuple[tuple[int, int, int], str] | None:
    if digit_profile != "auto":
        if digit_profile not in DIGIT_PROFILES:
            raise ValueError(f"Unknown digit profile: {digit_profile}")
        xyz = decode_xyz(payload, DIGIT_PROFILES[digit_profile])
        return (xyz, digit_profile) if xyz else None

    # Prefer the live profile, but reject candidates outside the RealView
    # source bounds. An explicit profile remains available for archived HARs.
    for name, digits in DIGIT_PROFILES.items():
        xyz = decode_xyz(payload, digits)
        if xyz and _plausible_realview_xyz(xyz):
            return xyz, name
    return None


def decode_request_url(
    url: str,
    source: str = "capture",
    ordinal: int = 0,
    digit_profile: str = DEFAULT_DIGIT_PROFILE,
) -> RealViewRequest | None:
    if "advancedmaps/" not in url or "/vector_tile/pbf?" not in url:
        return None
    parsed = urllib.parse.urlsplit(url)
    qs = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    fixed = {"b", "x-sec2", "rg", "t"}

    for key, vals in qs.items():
        if key in fixed or not vals:
            continue
        try:
            payload = b64decode_loose(vals[0])
        except Exception:
            continue
        if REALVIEW_MARKER not in payload:
            continue
        decoded = _decode_profiled_xyz(payload, digit_profile)
        if not decoded:
            continue
        xyz, used_profile = decoded
        z, x, y = xyz
        return RealViewRequest(z, x, y, url, source, ordinal, key, payload, used_profile)
    return None
