"""Coverage acquisition helpers for multi-source street-view experiments."""

from coverage_acquisition.compare import maybe_dataframe, summarize_many_bundles
from coverage_acquisition.models import BoundingBox, FetchAreaRequest
from coverage_acquisition.notebook import bbox_from_preset, fetch_multi_source_coverage, fetch_single_source
from coverage_acquisition.providers import DEFAULT_MULTI_SOURCE_PROVIDERS, PROVIDERS
from coverage_acquisition.runners import build_jobs, fetch_provider_coverage
from coverage_acquisition.visualization import load_result_from_manifest, load_results_from_manifest_paths, plot_multi_provider_comparison, summarize_results

__all__ = [
    "BoundingBox",
    "DEFAULT_MULTI_SOURCE_PROVIDERS",
    "FetchAreaRequest",
    "PROVIDERS",
    "bbox_from_preset",
    "build_jobs",
    "fetch_multi_source_coverage",
    "fetch_provider_coverage",
    "fetch_single_source",
    "load_result_from_manifest",
    "load_results_from_manifest_paths",
    "maybe_dataframe",
    "plot_multi_provider_comparison",
    "summarize_many_bundles",
    "summarize_results",
]
