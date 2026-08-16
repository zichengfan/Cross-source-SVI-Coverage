# Acquisition notebooks

This folder contains operational examples for the shareable acquisition layer,
not scientific analysis from the parent project.

- `0001_provider_acquisition_smoke_cases.ipynb` compares providers over shared
  case-study bounds and audits the same provider across requested levels. It
  covers all 14 registry providers plus Tencent PMTiles and Mappls RealView.
  Validated same-area and provider-level maps are embedded, so they remain
  visible without the excluded raw acquisition data.
- `build_0001_provider_comparison_cases.py` regenerates the notebook structure
  without copying local data or credentials. Regeneration intentionally clears
  cell outputs; execute the reference-build workflow before publishing a new
  notebook snapshot.

The notebook defaults to no network access. Enable a guarded acquisition cell
only after checking authorization, credentials, rate limits, target extent and
output location. The Barikoi reference workflow permits every declared level
from z7 through z17, processes one tile at a time, draws at most 50,000
deterministically sampled symbols while reporting the full count, and deletes
each raw run directory immediately after rendering.
