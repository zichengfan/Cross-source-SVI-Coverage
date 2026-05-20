"""<Provider name> coverage.

Stub created by the `add-provider` skill. The implementer fills this in
test-first, following `docs/providers/<key>.md`. Replace every <placeholder>.

ToS / robots.txt notes: <record any caveats from the subplan here>.
"""

from __future__ import annotations

from coverage_acquisition.models import ProviderDefinition, SourceDefinition
from coverage_acquisition.providers._registry import register_provider

PROVIDER = ProviderDefinition(
    key="<key>",
    output_namespace="<key>_coverage",
    run_label_prefix="<key>_coverage",
    default_display_zoom=14,
    coordinate_scheme="web_mercator",  # or yandex_wgs84_mercator / baidu / ...
    area_presets={},  # optional pilot bbox(es)
    sources=(
        SourceDefinition(
            id="<key>_source",
            kind="raster",  # raster | vector_mvt | coverage_json | streetlevel | ...
            template="https://<endpoint>/{z}/{x}/{y}",
            headers={
                "User-Agent": "global-svi-coverage-observatory/0.3",
                # Referer / Accept as the provider requires
            },
            storage_subdir="tiles",
            # expect_content_type_prefix / layer_names / token_query_param / options
            # as the source kind requires — see an existing provider module.
        ),
    ),
)

register_provider(PROVIDER)
