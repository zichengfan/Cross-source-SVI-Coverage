from __future__ import annotations

import csv
import gzip
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

# Some providers' vector feature rows carry very large geometry_wkt values
# (e.g. Mapillary sequence MultiLineStrings in dense urban areas can exceed
# 100KB per field), well past Python's 131072-byte csv default.
csv.field_size_limit(10_000_000)


def ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def suffix_from_url(url: str, default: str = ".bin") -> str:
    suffix = Path(urlparse(url).path).suffix
    return suffix or default


def suffix_for_content_type(content_type: str, url: str, default: str = ".bin") -> str:
    mapping = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
        "application/json": ".json",
        "application/vnd.mapbox-vector-tile": ".mvt",
        "application/x-protobuf": ".mvt",
        "application/octet-stream": suffix_from_url(url, default),
    }
    return mapping.get(content_type.split(";")[0].strip(), suffix_from_url(url, default))


def write_json(path: Path, payload: dict | list) -> None:
    ensure_directory(path.parent)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def load_json(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8"))


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    ensure_directory(path.parent)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fieldnames})


def read_csv_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def maybe_gzip_decompress(payload: bytes) -> tuple[bytes, bool]:
    if payload[:2] == bytes([0x1F, 0x8B]):
        return gzip.decompress(payload), True
    return payload, False
