# Acquisition notebooks

This folder contains operational examples for the shareable acquisition layer,
not scientific analysis from the parent project.

- `0001_provider_acquisition_smoke_cases.ipynb` compares providers over shared
  case-study bounds and audits the same provider across requested levels. It
  covers all 14 registry providers plus Tencent PMTiles and Mappls RealView.
- `build_0001_provider_comparison_cases.py` regenerates the notebook structure
  without copying local data or credentials.

The notebook defaults to no network access. Enable a guarded acquisition cell
only after checking authorization, credentials, rate limits, target extent and
output location.
