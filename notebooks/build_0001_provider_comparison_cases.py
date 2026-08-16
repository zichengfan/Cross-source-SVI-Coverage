# ruff: noqa: E501
from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent


def markdown(cell_id: str, source: str) -> dict:
    return {
        "cell_type": "markdown",
        "id": cell_id,
        "metadata": {},
        "source": dedent(source).strip() + "\n",
    }


def code(cell_id: str, source: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "id": cell_id,
        "metadata": {},
        "outputs": [],
        "source": dedent(source).strip() + "\n",
    }


cells = [
    markdown(
        "title",
        """
        # Same-area and multiscale provider acquisition checks

        This notebook asks two operational questions: how coverage differs between providers over identical WGS84 bounds, and which levels remain usable for the same provider at a fixed covered location. It covers all 16 implemented paths. Network access is disabled by default; raw responses and figures stay under the ignored `local/` directory.
        """,
    ),
    code(
        "setup",
        """
        import math
        import os
        import sys
        from pathlib import Path

        import matplotlib as mpl
        import matplotlib.pyplot as plt
        import numpy as np
        import pandas as pd
        from IPython.display import display
        from matplotlib.colors import BoundaryNorm, ListedColormap
        from matplotlib.patches import Patch, Rectangle


        def find_project_root(start: Path) -> Path:
            for candidate in (start, *start.parents):
                if (candidate / "pyproject.toml").exists() and (candidate / "src" / "coverage_acquisition").is_dir():
                    return candidate
            raise RuntimeError("Run this notebook from inside the shared-dev repository.")


        PROJECT_ROOT = find_project_root(Path.cwd().resolve())
        sys.path.insert(0, str(PROJECT_ROOT / "src"))
        sys.path.insert(0, str(PROJECT_ROOT / "integrations" / "mappls_realview" / "src"))

        from mappls_realview.bbox import BBox as MapplsBBox
        from mappls_realview.bbox import tiles_for_bbox as mappls_tiles_for_bbox
        from mappls_realview.sdk_capture import capture_sdk_bbox_async

        from coverage_acquisition.case_studies import (
            AREA_COMPARISON_CASES,
            MAPPLS_KEY,
            MULTISCALE_CASES,
            MULTISCALE_LEVELS,
            PROVIDER_LABELS,
            TENCENT_KEY,
            area_case,
            multiscale_case,
            multiscale_plan,
            multiscale_probe_bbox,
            validate_case_contract,
            validate_multiscale_probe,
        )
        from coverage_acquisition.geo import tile_range_for_bbox
        from coverage_acquisition.models import FetchAreaRequest
        from coverage_acquisition.providers import PROVIDERS
        from coverage_acquisition.runners import fetch_provider_coverage
        from coverage_acquisition.tencent_pmtiles import (
            DEFAULT_TENCENT_PMTILES_URL,
            fetch_tencent_pmtiles_sv_coverage,
        )
        from coverage_acquisition.visualization import (
            load_mappls_segments,
            load_result_from_manifest,
            plot_mappls_segments,
            plot_result,
            style_geo_axis,
        )
        mpl.rcParams.update(
            {
                "font.family": "sans-serif",
                "font.sans-serif": ["Arial", "DejaVu Sans", "Liberation Sans"],
                "font.size": 7,
                "axes.linewidth": 0.8,
                "axes.spines.top": False,
                "axes.spines.right": False,
                "legend.frameon": False,
                "svg.fonttype": "none",
                "pdf.fonttype": 42,
            }
        )
        """,
    ),
    markdown(
        "controls-title",
        """
        ## Controls

        Add individual `(case, provider)` or `(provider, level)` pairs only after reviewing authorization and request size. Access-gated providers also require explicit authorization below.
        """,
    ),
    code(
        "controls",
        """
        ALLOW_NETWORK = False
        RUN_ACQUISITIONS: set[tuple[str, str]] = set()
        RUN_MULTISCALE_PROBES: set[tuple[str, int]] = set()
        AUTHORIZED_ACCESS_GATED: set[str] = set()
        RENDER_CASES: tuple[str, ...] = ()
        FOCAL_MULTISCALE_PROVIDER = "barikoi"

        OUTPUT_ROOT = PROJECT_ROOT / "local" / "provider_comparison_cases"
        FIGURE_ROOT = OUTPUT_ROOT / "figures"
        MAPILLARY_ACCESS_TOKEN = os.getenv("MAPILLARY_ACCESS_TOKEN")
        TENCENT_PMTILES_URL = os.getenv("TENCENT_PMTILES_URL", DEFAULT_TENCENT_PMTILES_URL)
        """,
    ),
    markdown(
        "same-area-title",
        """
        ## 1. Same-area, cross-provider comparison

        The case contract retains the existing bounds and source selections. Requested and effective source levels are kept separate; Kakao uses native L-level semantics.
        """,
    ),
    code(
        "case-table",
        """
        validate_case_contract()
        case_rows = []
        for case in AREA_COMPARISON_CASES:
            for item in case.providers:
                semantics = "native L" if item.provider == "kakao" else "z"
                case_rows.append(
                    {
                        "case": case.key,
                        "area": case.label,
                        "provider": PROVIDER_LABELS[item.provider],
                        "provider_key": item.provider,
                        "requested_level": f"{semantics}{item.requested_level}",
                        "bbox_wgs84": tuple(case.bbox.as_dict().values()),
                    }
                )

        case_df = pd.DataFrame(case_rows)
        assert case_df["provider_key"].nunique() == 16
        display(case_df)
        """,
    ),
    code(
        "case-matrix",
        """
        provider_order = [case.provider for case in MULTISCALE_CASES]
        provider_index = {provider: index for index, provider in enumerate(provider_order)}
        matrix = np.zeros((len(AREA_COMPARISON_CASES), len(provider_order)), dtype=int)
        labels = np.full(matrix.shape, "", dtype=object)
        for row_index, case in enumerate(AREA_COMPARISON_CASES):
            for item in case.providers:
                column_index = provider_index[item.provider]
                matrix[row_index, column_index] = 1
                prefix = "L" if item.provider == "kakao" else "z"
                labels[row_index, column_index] = f"{prefix}{item.requested_level}"

        fig, ax = plt.subplots(figsize=(13.2, 5.8))
        ax.imshow(matrix, cmap=ListedColormap(["#F4F6F8", "#9EC7D8"]), vmin=0, vmax=1, aspect="auto")
        for row_index in range(matrix.shape[0]):
            for column_index in range(matrix.shape[1]):
                if labels[row_index, column_index]:
                    ax.text(column_index, row_index, labels[row_index, column_index], ha="center", va="center", fontsize=6.2)
        ax.set_xticks(range(len(provider_order)), [PROVIDER_LABELS[key] for key in provider_order], rotation=48, ha="right")
        ax.set_yticks(range(len(AREA_COMPARISON_CASES)), [case.label for case in AREA_COMPARISON_CASES])
        ax.set_title("Same-area comparison contract: providers and requested levels", fontsize=10, pad=10)
        ax.tick_params(length=0)
        fig.tight_layout()
        plt.show()
        """,
    ),
    code(
        "area-plan",
        """
        def plan_area_request(case, item):
            if item.provider in PROVIDERS:
                result = fetch_provider_coverage(
                    FetchAreaRequest(
                        provider=item.provider,
                        bbox=case.bbox,
                        output_root=OUTPUT_ROOT,
                        display_zoom=item.requested_level,
                        dry_run=True,
                    )
                )
                job = result["jobs"][0]
                return {
                    "case": case.key,
                    "provider": item.provider,
                    "requested_level": item.requested_level,
                    "effective_source_level": job["source_zoom"],
                    "source_id": job["source"].id,
                    "source_kind": job["source"].kind,
                    "planned_tiles": job["source_tile_count"],
                    "plan_status": "dry_run",
                }
            if item.provider == TENCENT_KEY:
                tile_range = tile_range_for_bbox(case.bbox, item.requested_level, "web_mercator")
                return {
                    "case": case.key,
                    "provider": item.provider,
                    "requested_level": item.requested_level,
                    "effective_source_level": item.requested_level,
                    "source_id": "qq_map_lines_pmtiles_sv",
                    "source_kind": "vector_mvt",
                    "planned_tiles": tile_range.count,
                    "plan_status": "archive_plan",
                }
            west, south, east, north = case.bbox.as_dict().values()
            count = len(mappls_tiles_for_bbox(MapplsBBox(west, south, east, north), item.requested_level))
            return {
                "case": case.key,
                "provider": item.provider,
                "requested_level": item.requested_level,
                "effective_source_level": item.requested_level,
                "source_id": "mappls_realview_sdk",
                "source_kind": "vector_mvt",
                "planned_tiles": count,
                "plan_status": "access_gated",
            }


        area_plan_df = pd.DataFrame(
            [plan_area_request(case, item) for case in AREA_COMPARISON_CASES for item in case.providers]
        )
        display(area_plan_df)
        """,
    ),
    code(
        "area-acquisition",
        """
        def provider_level_for_case(case_key: str, provider_key: str):
            case = area_case(case_key)
            for item in case.providers:
                if item.provider == provider_key:
                    return case, item
            raise KeyError(f"{provider_key} is not configured for {case_key}")


        async def acquire_area_case(case_key: str, provider_key: str):
            if not ALLOW_NETWORK:
                raise RuntimeError("Set ALLOW_NETWORK=True before running an acquisition.")
            case, item = provider_level_for_case(case_key, provider_key)
            if provider_key in {"apple_lookaround", MAPPLS_KEY} and provider_key not in AUTHORIZED_ACCESS_GATED:
                raise PermissionError(f"Add {provider_key!r} to AUTHORIZED_ACCESS_GATED after authorization review.")
            run_label = f"{case.key}_{provider_key}"
            if provider_key in PROVIDERS:
                if provider_key == "mapillary" and not MAPILLARY_ACCESS_TOKEN:
                    raise RuntimeError("Set MAPILLARY_ACCESS_TOKEN in the environment.")
                return fetch_provider_coverage(
                    FetchAreaRequest(
                        provider=provider_key,
                        bbox=case.bbox,
                        output_root=OUTPUT_ROOT,
                        display_zoom=item.requested_level,
                        stop_on_error=False,
                        timeout_seconds=30,
                        run_label=run_label,
                        access_token=MAPILLARY_ACCESS_TOKEN if provider_key == "mapillary" else None,
                    )
                )
            if provider_key == TENCENT_KEY:
                return fetch_tencent_pmtiles_sv_coverage(
                    case.bbox,
                    output_root=OUTPUT_ROOT,
                    cache_dir=OUTPUT_ROOT / "tencent_pmtiles_cache",
                    source_url=TENCENT_PMTILES_URL,
                    source_zoom=item.requested_level,
                    run_label=f"{run_label}_subbox_00",
                )
            bbox = MapplsBBox(case.bbox.min_lon, case.bbox.min_lat, case.bbox.max_lon, case.bbox.max_lat)
            return await capture_sdk_bbox_async(
                web_dir=PROJECT_ROOT / "integrations" / "mappls_realview" / "web",
                bbox=bbox,
                zoom=item.requested_level,
                out_dir=OUTPUT_ROOT / "mappls_realview",
                output_mode="production",
                run_id=f"{case.key}_mappls_z{item.requested_level}",
                headless=True,
            )


        live_area_results = {}
        for case_key, provider_key in sorted(RUN_ACQUISITIONS):
            live_area_results[(case_key, provider_key)] = await acquire_area_case(case_key, provider_key)
        print(f"Live area acquisitions executed: {len(live_area_results)}")
        """,
    ),
    code(
        "area-render",
        """
        def registry_manifest_path(case, provider_key):
            namespace = PROVIDERS[provider_key].output_namespace
            return OUTPUT_ROOT / namespace / f"{case.key}_{provider_key}_subbox_00" / "manifest.json"


        def tencent_manifest_path(case):
            return OUTPUT_ROOT / TENCENT_KEY / f"{case.key}_{TENCENT_KEY}_subbox_00" / "manifest.json"


        def mappls_summary_path(case, level):
            return OUTPUT_ROOT / "mappls_realview" / "production" / "runs" / f"{case.key}_mappls_z{level}.json"


        def render_area_comparison(case_key: str):
            case = area_case(case_key)
            ncols = min(4, len(case.providers))
            nrows = math.ceil(len(case.providers) / ncols)
            fig, axes = plt.subplots(nrows, ncols, figsize=(3.2 * ncols, 3.0 * nrows), squeeze=False)
            for ax, item in zip(axes.flat, case.providers):
                prefix = "L" if item.provider == "kakao" else "z"
                level_label = f"requested {prefix}{item.requested_level}"
                try:
                    if item.provider in PROVIDERS:
                        path = registry_manifest_path(case, item.provider)
                        if not path.exists():
                            raise FileNotFoundError(path)
                        plot_result(
                            ax,
                            load_result_from_manifest(path),
                            bbox=case.bbox,
                            label=PROVIDER_LABELS[item.provider],
                            level_label=level_label,
                        )
                    elif item.provider == TENCENT_KEY:
                        path = tencent_manifest_path(case)
                        if not path.exists():
                            raise FileNotFoundError(path)
                        plot_result(
                            ax,
                            load_result_from_manifest(path),
                            bbox=case.bbox,
                            label=PROVIDER_LABELS[item.provider],
                            level_label=level_label,
                        )
                    else:
                        path = mappls_summary_path(case, item.requested_level)
                        if not path.exists():
                            raise FileNotFoundError(path)
                        returned_bbox, segments = load_mappls_segments(path)
                        if returned_bbox.as_dict() != case.bbox.as_dict():
                            raise RuntimeError("Mappls returned different bounds.")
                        plot_mappls_segments(
                            ax,
                            segments,
                            bbox=case.bbox,
                            label=PROVIDER_LABELS[item.provider],
                            level_label=level_label,
                        )
                except FileNotFoundError:
                    style_geo_axis(ax, case.bbox, f"{PROVIDER_LABELS[item.provider]}\\n{level_label}; not acquired")
                    ax.text(0.5, 0.5, "not acquired", transform=ax.transAxes, ha="center", va="center", color="#7A8793")
            for ax in axes.flat[len(case.providers) :]:
                ax.axis("off")
            fig.suptitle(f"{case.label}: provider coverage over identical WGS84 bounds", fontsize=10, fontweight="bold")
            fig.tight_layout(rect=(0, 0, 1, 0.94))
            return fig


        for case_key in RENDER_CASES:
            render_area_comparison(case_key)
            plt.show()
        if not RENDER_CASES:
            print("No map panels rendered. Add a case key to RENDER_CASES after acquisition or cache review.")
        """,
    ),
    markdown(
        "multiscale-title",
        """
        ## 2. Same-provider, multiscale comparison

        Each provider keeps its existing case location and deterministic covered anchor. The audit distinguishes requested level from effective source level and never interprets an access or safety gate as absence of coverage.
        """,
    ),
    code(
        "multiscale-plan",
        """
        zoom_plan_df = pd.DataFrame(multiscale_plan())
        display(
            zoom_plan_df.groupby(["provider", "plan_status"], as_index=False)
            .size()
            .sort_values(["provider", "plan_status"])
        )

        barikoi_plan = zoom_plan_df.loc[
            zoom_plan_df["provider"].eq("barikoi"),
            ["requested_level", "effective_source_level", "source_id", "planned_tiles", "plan_status", "note"],
        ]
        display(barikoi_plan)
        """,
    ),
    code(
        "multiscale-matrix",
        """
        status_order = ["unsupported", "safety_skip", "access_gated", "requires_token", "native_archive", "planned"]
        status_colors = ["#E5E7EB", "#D8A45D", "#B79AC8", "#E7C97B", "#79AFC3", "#6FAF8E"]
        status_index = {status: index for index, status in enumerate(status_order)}
        provider_order = [case.provider for case in MULTISCALE_CASES]
        matrix = np.zeros((len(provider_order), len(MULTISCALE_LEVELS)), dtype=int)
        for row_index, provider_key in enumerate(provider_order):
            provider_rows = zoom_plan_df.loc[zoom_plan_df["provider"].eq(provider_key)].set_index("requested_level")
            for column_index, level in enumerate(MULTISCALE_LEVELS):
                matrix[row_index, column_index] = status_index[provider_rows.loc[level, "plan_status"]]

        cmap = ListedColormap(status_colors)
        norm = BoundaryNorm(np.arange(-0.5, len(status_order) + 0.5), cmap.N)
        fig, ax = plt.subplots(figsize=(10.8, 6.4))
        ax.imshow(matrix, cmap=cmap, norm=norm, aspect="auto")
        ax.set_xticks(range(len(MULTISCALE_LEVELS)), [f"z{level}" for level in MULTISCALE_LEVELS])
        ax.set_yticks(range(len(provider_order)), [PROVIDER_LABELS[key] for key in provider_order])
        ax.set_xlabel("Requested level (Kakao row uses native L-levels)")
        ax.set_title("Multiscale acquisition plan and safety gates", fontsize=10, pad=10)
        barikoi_index = provider_order.index("barikoi")
        ax.add_patch(Rectangle((-0.5, barikoi_index - 0.5), len(MULTISCALE_LEVELS), 1, fill=False, edgecolor="#8A4B08", linewidth=1.4))
        ax.legend(
            handles=[Patch(facecolor=color, label=status.replace("_", " ")) for status, color in zip(status_order, status_colors)],
            loc="upper center",
            bbox_to_anchor=(0.5, -0.10),
            ncol=3,
        )
        fig.tight_layout()
        plt.show()
        """,
    ),
    markdown(
        "barikoi-note",
        """
        ### Barikoi correction

        The earlier multiscale failure came from notebook-local registration: the comparison cell registered Barikoi, but the later audit could run without that state and returned `Provider registration missing`. Barikoi is now a permanent shared registry provider. Levels z7–z13 are additionally blocked before network access because low-level ThirdEye360 MVT responses can exceed 100 MiB; z14–z17 remain available for controlled probes. An end-to-end check on 2026-08-16 returned one tile with 3,156 features at z14 and one tile with 572 features at z16, with zero tile errors.
        """,
    ),
    code(
        "multiscale-acquisition",
        """
        try:
            validate_multiscale_probe("barikoi", 13)
        except ValueError as exc:
            print("Barikoi pre-network guard:", exc)
        assert validate_multiscale_probe("barikoi", 14)["source_id"] == "barikoi_thirdeye360_mvt"


        async def acquire_multiscale_probe(provider_key: str, requested_level: int):
            plan = validate_multiscale_probe(provider_key, requested_level)
            if not ALLOW_NETWORK:
                raise RuntimeError("Set ALLOW_NETWORK=True before running a multiscale probe.")
            if provider_key in {"apple_lookaround", MAPPLS_KEY} and provider_key not in AUTHORIZED_ACCESS_GATED:
                raise PermissionError(f"Add {provider_key!r} to AUTHORIZED_ACCESS_GATED after authorization review.")
            case = multiscale_case(provider_key)
            bbox = multiscale_probe_bbox(case)
            run_label = f"multiscale_{provider_key}_l{requested_level}"
            if provider_key in PROVIDERS:
                if provider_key == "mapillary" and not MAPILLARY_ACCESS_TOKEN:
                    raise RuntimeError("Set MAPILLARY_ACCESS_TOKEN in the environment.")
                return fetch_provider_coverage(
                    FetchAreaRequest(
                        provider=provider_key,
                        bbox=bbox,
                        output_root=OUTPUT_ROOT,
                        display_zoom=requested_level,
                        stop_on_error=False,
                        timeout_seconds=30,
                        run_label=run_label,
                        access_token=MAPILLARY_ACCESS_TOKEN if provider_key == "mapillary" else None,
                    )
                )
            if provider_key == TENCENT_KEY:
                return fetch_tencent_pmtiles_sv_coverage(
                    bbox,
                    output_root=OUTPUT_ROOT,
                    cache_dir=OUTPUT_ROOT / "tencent_pmtiles_cache",
                    source_url=TENCENT_PMTILES_URL,
                    source_zoom=int(plan["effective_source_level"]),
                    run_label=f"{run_label}_subbox_00",
                )
            sdk_bbox = MapplsBBox(bbox.min_lon, bbox.min_lat, bbox.max_lon, bbox.max_lat)
            return await capture_sdk_bbox_async(
                web_dir=PROJECT_ROOT / "integrations" / "mappls_realview" / "web",
                bbox=sdk_bbox,
                zoom=requested_level,
                out_dir=OUTPUT_ROOT / "mappls_realview",
                output_mode="production",
                run_id=f"{run_label}_mappls",
                headless=True,
            )


        live_multiscale_results = {}
        for provider_key, requested_level in sorted(RUN_MULTISCALE_PROBES):
            live_multiscale_results[(provider_key, requested_level)] = await acquire_multiscale_probe(
                provider_key, requested_level
            )
        print(f"Live multiscale probes executed: {len(live_multiscale_results)}")
        """,
    ),
    code(
        "multiscale-render",
        """
        def multiscale_registry_manifest(provider_key, requested_level):
            namespace = PROVIDERS[provider_key].output_namespace
            run_label = f"multiscale_{provider_key}_l{requested_level}_subbox_00"
            return OUTPUT_ROOT / namespace / run_label / "manifest.json"


        def multiscale_tencent_manifest(provider_key, requested_level):
            run_label = f"multiscale_{provider_key}_l{requested_level}_subbox_00"
            return OUTPUT_ROOT / provider_key / run_label / "manifest.json"


        def render_multiscale_provider(provider_key: str):
            case = multiscale_case(provider_key)
            bbox = multiscale_probe_bbox(case)
            rows = zoom_plan_df.loc[zoom_plan_df["provider"].eq(provider_key)].set_index("requested_level")
            fig, axes = plt.subplots(4, 4, figsize=(9.2, 8.2), squeeze=False)
            for ax, requested_level in zip(axes.flat, MULTISCALE_LEVELS):
                row = rows.loc[requested_level]
                prefix = "L" if provider_key == "kakao" else "z"
                level_label = f"requested {prefix}{requested_level}"
                rendered = False
                if provider_key in PROVIDERS:
                    path = multiscale_registry_manifest(provider_key, requested_level)
                    if path.exists():
                        plot_result(
                            ax,
                            load_result_from_manifest(path),
                            bbox=bbox,
                            label=PROVIDER_LABELS[provider_key],
                            level_label=level_label,
                        )
                        rendered = True
                elif provider_key == TENCENT_KEY:
                    path = multiscale_tencent_manifest(provider_key, requested_level)
                    if path.exists():
                        plot_result(
                            ax,
                            load_result_from_manifest(path),
                            bbox=bbox,
                            label=PROVIDER_LABELS[provider_key],
                            level_label=level_label,
                        )
                        rendered = True
                if not rendered:
                    status = row["plan_status"].replace("_", " ")
                    status_color = status_colors[status_index[row["plan_status"]]]
                    ax.set_facecolor(status_color)
                    ax.set_title(f"{level_label}\\n{status}", fontsize=8, pad=4)
                    ax.text(0.5, 0.5, status, transform=ax.transAxes, ha="center", va="center", color="#3F4B55")
                    ax.set_xticks([])
                    ax.set_yticks([])
                    for spine in ax.spines.values():
                        spine.set_visible(False)
            for ax in axes.flat[len(MULTISCALE_LEVELS) :]:
                ax.axis("off")
            fig.suptitle(
                f"{PROVIDER_LABELS[provider_key]} in {case.area}: fixed-ROI multiscale comparison",
                fontsize=10,
                fontweight="bold",
            )
            fig.tight_layout(rect=(0, 0, 1, 0.95))
            return fig


        render_multiscale_provider(FOCAL_MULTISCALE_PROVIDER)
        plt.show()
        """,
    ),
    code(
        "qa",
        """
        implemented = set(PROVIDERS) | {TENCENT_KEY, MAPPLS_KEY}
        compared = set(case_df["provider_key"])
        audited = set(zoom_plan_df["provider"])
        assert implemented == compared == audited
        assert len(area_plan_df) == len(case_df)
        assert len(zoom_plan_df) == 16 * len(MULTISCALE_LEVELS)
        assert not RUN_ACQUISITIONS and not RUN_MULTISCALE_PROBES
        print(
            f"Validated {len(compared)} providers, {len(AREA_COMPARISON_CASES)} same-area cases, "
            f"and {len(zoom_plan_df)} multiscale plan rows. Provider network calls: 0."
        )
        """,
    ),
]

notebook = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3 (ipykernel)", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.11"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

output_path = Path(__file__).with_name("0001_provider_acquisition_smoke_cases.ipynb")
output_path.write_text(json.dumps(notebook, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
print(output_path)
