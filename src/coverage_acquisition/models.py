from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class BoundingBox:
    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float

    @classmethod
    def from_mapping(cls, payload: dict[str, float]) -> "BoundingBox":
        return cls(
            min_lon=float(payload["min_lon"]),
            min_lat=float(payload["min_lat"]),
            max_lon=float(payload["max_lon"]),
            max_lat=float(payload["max_lat"]),
        )

    @classmethod
    def from_sequence(cls, values: list[float] | tuple[float, float, float, float]) -> "BoundingBox":
        if len(values) != 4:
            raise ValueError("Bounding box sequence must contain 4 values.")
        return cls(
            min_lon=float(values[0]),
            min_lat=float(values[1]),
            max_lon=float(values[2]),
            max_lat=float(values[3]),
        )

    def as_dict(self) -> dict[str, float]:
        return {
            "min_lon": self.min_lon,
            "min_lat": self.min_lat,
            "max_lon": self.max_lon,
            "max_lat": self.max_lat,
        }


@dataclass(frozen=True)
class TileRange:
    x_min: int
    x_max: int
    y_min: int
    y_max: int

    @property
    def count(self) -> int:
        return (self.x_max - self.x_min + 1) * (self.y_max - self.y_min + 1)

    def as_dict(self) -> dict[str, int]:
        return {
            "x_min": self.x_min,
            "x_max": self.x_max,
            "y_min": self.y_min,
            "y_max": self.y_max,
        }


@dataclass(frozen=True)
class DownloadSource:
    provider: str
    url: str
    filename: str
    notes: str = ""


@dataclass(frozen=True)
class TileFetchRequest:
    provider: str
    template: str
    zoom: int
    x_min: int
    x_max: int
    y_min: int
    y_max: int
    output_dir: Path
    headers: dict[str, str] = field(default_factory=dict)
    timeout_seconds: int = 60


@dataclass(frozen=True)
class TileCoordinate:
    z: int
    x: int
    y: int

    @property
    def relative_path(self) -> Path:
        return Path(str(self.z)) / str(self.x) / f"{self.y}.bin"


@dataclass(frozen=True)
class SourceDefinition:
    id: str
    kind: str
    template: str
    headers: dict[str, str] = field(default_factory=dict)
    display_zoom_min: int = 0
    display_zoom_max: int = 22
    query_zoom: int | None = None
    layer_names: tuple[str, ...] = ()
    notes: str = ""
    storage_subdir: str | None = None
    token_query_param: str | None = None
    expect_content_type_prefix: str | None = None
    vector_decoder: str = "ogr2ogr"
    options: dict[str, str] = field(default_factory=dict)

    @property
    def effective_storage_subdir(self) -> str:
        if self.storage_subdir:
            return self.storage_subdir
        return self.kind


@dataclass(frozen=True)
class ProviderDefinition:
    key: str
    output_namespace: str
    run_label_prefix: str
    default_display_zoom: int
    request_timeout_seconds: int = 60
    coordinate_scheme: str = "web_mercator"
    supports_auto_zoom: bool = False
    area_presets: dict[str, BoundingBox] = field(default_factory=dict)
    sources: tuple[SourceDefinition, ...] = field(default_factory=tuple)
    notes: str = ""


@dataclass(frozen=True)
class FetchAreaRequest:
    provider: str
    bbox: BoundingBox
    output_root: Path
    display_zoom: int | None = None
    auto_zoom: bool = False
    min_display_zoom: int | None = None
    max_display_zoom: int | None = None
    max_source_tile_count: int = 16
    grid_rows: int = 1
    grid_cols: int = 1
    target_subboxes: tuple[int, ...] | None = None
    run_label: str | None = None
    skip_404: bool = True
    stop_on_error: bool = True
    timeout_seconds: int | None = None
    dry_run: bool = False
    access_token: str | None = None
    extra_headers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ProbeFetchRequest:
    """Request for streetlevel-native point-probe coverage acquisition."""

    provider: str
    bbox: BoundingBox
    output_root: Path
    coarse_spacing_m: float = 1500.0
    fine_spacing_m: float = 150.0
    radius_m: float = 100.0
    requests_per_second: float = 1.0
    two_pass: bool = True
    run_label: str | None = None
    dry_run: bool = False
