"""Direct-download sources and restricted-frontend notes.

Legacy central tables kept for the already-working providers. New providers that
need a direct-download source should add it to their own provider module and
expose it via the provider definition rather than editing this file.
"""

from __future__ import annotations

from coverage_acquisition.models import DownloadSource

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
