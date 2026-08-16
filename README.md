# Cross-source SVI coverage acquisition

This repository contains the shareable acquisition layer of the global
street-view coverage project. It discovers, downloads, decodes and validates
**coverage metadata and coverage overlays**. It does not download panorama
imagery and does not contain the parent project's demographic analysis,
figures, research notebooks or local datasets. The one notebook retained here
is an operational, offline-by-default smoke test for the acquisition APIs.

## Supported acquisition paths

The core registry currently covers Google Street View, Apple Look Around,
Baidu, Naver, Kakao, KartaView, Mapillary, Streetview.vn, Yandex, MapJack,
Mapilio, Mapy.com, Barikoi and Panoramax. Tencent is handled through a dedicated
PMTiles reader. Mappls RealView is retained as a separate authorization-gated
integration under `integrations/mappls_realview/`.

An implemented path means that a coverage response has been acquired and
decoded in at least one validated case. It does not imply that an endpoint is
an official API, that bulk use is permitted, or that country/global acquisition
is complete. Consult `docs/provider_acquisition_status.md` before assigning a
job.

## Environment

```bash
uv sync --extra dev
uv run coverage-acquisition list-providers
uv run pytest
```

To run the provider smoke-case notebook locally:

```bash
uv sync --extra dev --extra notebook
uv run jupyter lab notebooks/
```

Equivalent editable installation with pip:

```bash
python -m pip install -e '.[dev]'
pytest
```

## Minimal examples

```bash
python examples/fetch_bbox.py \
  --provider mapy \
  --bbox 14.40 50.075 14.44 50.095 \
  --zoom 14 \
  --output-root local/example
```

Use `--dry-run` before any network acquisition. Provider terms, access
requirements and rate limits remain the operator's responsibility.

## Repository boundary

- `src/coverage_acquisition/`: provider registry, grids, decoders, runners,
  bounded acquisition and manifests.
- `integrations/mappls_realview/`: authorized Mappls Web SDK workflow.
- `tests/`: offline acquisition and decoding tests.
- `examples/`: small operator-facing entry points.
- `notebooks/`: offline-by-default provider call cases and acquisition-oriented
  visual checks; not scientific analysis.
- `docs/`: operational status and acquisition contracts.

Raw responses, credentials, data archives, derived coverage layers and analysis
outputs are intentionally excluded. No open-source licence has yet been
selected; distribution terms must be agreed before public release.
