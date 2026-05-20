# Cross-source SVI Coverage

Scrape and harmonize **coverage maps** from street-level imagery (SVI) providers
worldwide, building toward a global street-level image availability database.

The preferred output format is **raster** (coverage rasters) rather than vector
points, for efficient global-scale storage.

## Environment

This project uses [uv](https://docs.astral.sh/uv/):

```bash
uv sync --extra notebook --extra dev   # create .venv and install deps
uv run coverage-acquisition list-providers
```

## Layout

- `src/coverage_acquisition/` — acquisition library and CLI.
- `data/external/street_view_providers.xlsx` — worldwide provider inventory.
- `0001_*.ipynb`, `0002_*.ipynb` — exploratory and call-script notebooks.
